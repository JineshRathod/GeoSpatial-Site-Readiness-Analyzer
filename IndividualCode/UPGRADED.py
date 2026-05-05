"""
Location Intelligence Tool — Full Multi-Layer Geospatial Analysis
=================================================================
Layers covered:
  1. Demographic Data      — population density, income proxy, age distribution
  2. Transportation Network — road density, transit proximity, drive-time isochrones
  3. Points of Interest    — competitors, complementary businesses, anchor tenants
  4. Land Use & Zoning     — OSM landuse, building footprints, zoning classification
  5. Environmental / Risk  — flood zones, earthquake risk, air quality (AQI)

Format support: GeoJSON, Shapefiles, GeoTIFF, WKT (ingest helpers included)
Output        : Folium HTML map  +  GeoJSON with all generated data
"""

import os
import json
import math
import warnings
from collections import defaultdict
from datetime import datetime, timedelta

import osmnx as ox
import networkx as nx
import rasterio
import requests
import folium
import geopandas as gpd
import pandas as pd
import numpy as np
from rasterio.windows import Window
from folium.plugins import MarkerCluster
from shapely.geometry import Point, mapping, shape
from shapely.wkt import loads as wkt_loads
from pyproj import Transformer

warnings.filterwarnings("ignore")


# ══════════════════════════════════════════════════════════════════
#  SHARED UTILITIES
# ══════════════════════════════════════════════════════════════════

def safe_str(val):
    if val is None:
        return "unknown"
    if isinstance(val, list):
        return val[0] if val else "unknown"
    s = str(val)
    return "unknown" if s in ("nan", "None", "") else s


def safe_unique(series):
    seen, result = set(), []
    for val in series:
        key = safe_str(val)
        if key not in seen:
            seen.add(key)
            result.append(key)
    return result


def haversine(lat1, lon1, lat2, lon2):
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def fmt(v, unit="", decimals=1):
    return f"{round(v, decimals)}{unit}" if v is not None else "N/A"


def date_range(start_str, end_str):
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end   = datetime.strptime(end_str,   "%Y-%m-%d")
    return [(start + timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range((end - start).days + 1)]


# ══════════════════════════════════════════════════════════════════
#  FORMAT INGESTION HELPERS  (GeoJSON / Shapefile / GeoTIFF / WKT)
# ══════════════════════════════════════════════════════════════════

def load_geojson(path: str) -> gpd.GeoDataFrame:
    """Load a GeoJSON file from disk into a GeoDataFrame."""
    gdf = gpd.read_file(path, driver="GeoJSON")
    if gdf.crs is None:
        gdf = gdf.set_crs("epsg:4326")
    else:
        gdf = gdf.to_crs("epsg:4326")
    print(f"  [GeoJSON] Loaded {len(gdf)} features from {os.path.basename(path)}")
    return gdf


def load_shapefile(path: str) -> gpd.GeoDataFrame:
    """Load a Shapefile (.shp) into a GeoDataFrame."""
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf = gdf.set_crs("epsg:4326")
    else:
        gdf = gdf.to_crs("epsg:4326")
    print(f"  [Shapefile] Loaded {len(gdf)} features from {os.path.basename(path)}")
    return gdf


def load_geotiff_sample(path: str, lat: float, lon: float, radius_px: int = 10):
    """Sample pixel values from a GeoTIFF around a point."""
    with rasterio.open(path) as ds:
        row, col = ds.index(lon, lat)
        size     = radius_px * 2
        window   = Window(col - radius_px, row - radius_px, size, size)
        data     = ds.read(1, window=window)
        nodata   = ds.nodata
    if nodata is not None:
        data = data[data != nodata]
    return data


def load_wkt(wkt_string: str) -> gpd.GeoDataFrame:
    """Parse a WKT geometry string and return a single-row GeoDataFrame."""
    geom = wkt_loads(wkt_string)
    gdf  = gpd.GeoDataFrame(geometry=[geom], crs="epsg:4326")
    print(f"  [WKT] Parsed geometry type: {geom.geom_type}")
    return gdf


# ══════════════════════════════════════════════════════════════════
#  MODULE 1 — ROAD NETWORK + ISOCHRONES (Transportation Layer)
# ══════════════════════════════════════════════════════════════════

def compute_isochrones(lat, lon, G_proj, trip_times_min=(5, 10, 15)):
    """
    Build drive-time isochrone polygons for given trip times (minutes).
    Returns a dict: {minutes: shapely Polygon or None}
    """
    from shapely.ops import unary_union
    import networkx as nx

    transformer_fwd = Transformer.from_crs("epsg:4326", G_proj.graph["crs"], always_xy=True)
    ox_x, ox_y = transformer_fwd.transform(lon, lat)
    center_node = ox.nearest_nodes(G_proj, ox_x, ox_y)

    # Average speed assumption: 30 km/h = 500 m/min
    speed_m_per_min = 500
    isochrones = {}

    for t in trip_times_min:
        max_dist = t * speed_m_per_min
        try:
            subgraph = nx.ego_graph(G_proj, center_node, radius=max_dist, distance="length")
            node_pts = [
                Point(data["x"], data["y"])
                for n, data in subgraph.nodes(data=True)
            ]
            if len(node_pts) < 3:
                isochrones[t] = None
                continue
            from shapely.ops import unary_union
            poly = unary_union(node_pts).convex_hull.buffer(200)
            # Reproject back to WGS84
            transformer_rev = Transformer.from_crs(G_proj.graph["crs"], "epsg:4326", always_xy=True)
            if hasattr(poly, "geoms"):
                isochrones[t] = None
            else:
                xs, ys = poly.exterior.xy
                coords_wgs = [transformer_rev.transform(x, y) for x, y in zip(xs, ys)]
                from shapely.geometry import Polygon
                isochrones[t] = Polygon([(lat2, lon2) for lon2, lat2 in coords_wgs])
        except Exception as e:
            isochrones[t] = None

    return isochrones


def get_landmark_distances(lat, lon, G_proj, dist):
    transformer = Transformer.from_crs("epsg:4326", G_proj.graph["crs"], always_xy=True)

    def to_proj(lon_, lat_):
        return transformer.transform(lon_, lat_)

    BATCH_TAGS = {
        "amenity"         : ["bus_station", "hospital", "school", "fuel",
                             "police", "bank", "pharmacy", "college", "market"],
        "highway"         : ["bus_stop"],
        "railway"         : ["station", "halt"],
        "shop"            : ["supermarket", "mall"],
        "public_transport": ["station", "stop_position"],
    }

    LABEL_MAP = {
        "bus_station"  : "🚌 Bus Stand",
        "hospital"     : "🏥 Hospital",
        "school"       : "🏫 School",
        "fuel"         : "⛽ Fuel Station",
        "police"       : "👮 Police Station",
        "bank"         : "🏦 Bank",
        "pharmacy"     : "💊 Pharmacy",
        "college"      : "🎓 College",
        "market"       : "🛒 Market",
        "bus_stop"     : "🚌 Bus Stop",
        "station"      : "🚉 Railway Station",
        "halt"         : "🚉 Railway Halt",
        "supermarket"  : "🛒 Supermarket",
        "mall"         : "🏬 Mall",
        "stop_position": "🚌 Transit Stop",
    }

    print(f"\n--- Distances to Nearby Landmarks ---")

    try:
        gdf = ox.features_from_point((lat, lon), tags=BATCH_TAGS, dist=dist)
    except Exception as e:
        print(f"  Could not fetch landmarks: {e}")
        return []

    if gdf.empty:
        print("  No landmarks found nearby.")
        return []

    ox_x, ox_y  = to_proj(lon, lat)
    origin_node = ox.nearest_nodes(G_proj, ox_x, ox_y)

    gdf              = gdf.copy()
    gdf["_centroid"] = gdf.geometry.centroid
    gdf["_lat"]      = gdf["_centroid"].y
    gdf["_lon"]      = gdf["_centroid"].x

    def get_label(row):
        for tag_key in ["amenity", "highway", "railway", "shop", "public_transport"]:
            val = safe_str(row.get(tag_key, None))
            if val in LABEL_MAP:
                return LABEL_MAP[val]
        return "📍 Other"

    def get_name(row):
        for col in ["name", "operator", "ref", "description"]:
            val = safe_str(row.get(col, None))
            if val not in ("unknown", "nan", "None", "none"):
                return val[:35]
        return "unnamed"

    results = []
    for _, row in gdf.iterrows():
        poi_lat = row["_lat"]
        poi_lon = row["_lon"]
        label   = get_label(row)
        name    = get_name(row)
        try:
            poi_x, poi_y = to_proj(poi_lon, poi_lat)
            dest_node    = ox.nearest_nodes(G_proj, poi_x, poi_y)
            road_dist    = nx.shortest_path_length(G_proj, origin_node, dest_node, weight="length")
            note         = "road"
        except Exception:
            road_dist    = haversine(lat, lon, poi_lat, poi_lon)
            note         = "straight*"

        results.append({
            "label"     : label,
            "name"      : name,
            "lat"       : poi_lat,
            "lon"       : poi_lon,
            "distance_m": round(road_dist, 1),
            "note"      : note,
        })

    grouped = defaultdict(list)
    for r in results:
        grouped[r["label"]].append(r)

    print(f"  {'Type':<22} {'Name':<35} {'Distance':>10}  {'Via'}")
    print(f"  {'─'*22} {'─'*35} {'─'*10}  {'─'*10}")

    all_shown = []
    for label in sorted(grouped.keys()):
        items = sorted(grouped[label], key=lambda x: x["distance_m"])
        for item in items[:2]:
            d     = item["distance_m"]
            d_str = f"{d:,.0f} m" if d < 1000 else f"{d/1000:.2f} km"
            print(f"  {label:<22} {item['name']:<35} {d_str:>10}  {item['note']}")
            all_shown.append(item)

    if all_shown:
        best  = min(all_shown, key=lambda x: x["distance_m"])
        d     = best["distance_m"]
        d_str = f"{d:,.0f} m" if d < 1000 else f"{d/1000:.2f} km"
        print(f"\n  ★ Nearest: {best['name']} ({best['label']}) → {d_str}")

    print(f"  * straight = not reachable via road graph")
    return results


def get_road_score(lat, lon, dist=2000):
    print(f"\nFetching road network within {dist}m of ({lat}, {lon})...")

    G      = ox.graph_from_point((lat, lon), dist=dist, network_type='drive')
    G_proj = ox.project_graph(G)
    nodes, edges = ox.graph_to_gdfs(G_proj)
    edges  = edges.copy()

    for col in edges.columns:
        if edges[col].dtype == object:
            edges[col] = edges[col].apply(safe_str)

    total_edges     = len(edges)
    total_nodes     = len(nodes)
    total_length_m  = edges.length.sum()
    total_length_km = total_length_m / 1000

    # Road DENSITY  = km of road per km² of search area
    area_km2      = math.pi * (dist / 1000) ** 2
    road_density  = round(total_length_km / area_km2, 2)

    dead_ends     = sum(1 for n in G.nodes() if G.degree(n) == 1)
    intersections = sum(1 for n in G.nodes() if G.degree(n) >= 3)
    oneway_count  = int(edges["oneway"].apply(lambda x: x == "True").sum()) if "oneway" in edges.columns else 0
    twoway_count  = total_edges - oneway_count

    road_types, length_by_type = {}, {}
    if "highway" in edges.columns:
        for rtype, group in edges.groupby("highway"):
            road_types[rtype]     = len(group)
            length_by_type[rtype] = group.length.sum()

    named_roads = []
    if "name" in edges.columns:
        for val in edges["name"].unique():
            if val not in ("unknown", "nan", "None"):
                named_roads.append(val)
    named_roads = sorted(set(named_roads))

    rating = (
        "Excellent ✅  (city center / commercial hub)" if total_length_km > 100 else
        "Good 🟢      (well connected area)"           if total_length_km > 60  else
        "Moderate 🟡  (average connectivity)"          if total_length_km > 30  else
        "Low 🔴       (poor road access)"
    )

    print(f"\n{'='*55}")
    print(f"  ROAD NETWORK REPORT")
    print(f"  Location : ({lat}, {lon})  |  Radius: {dist} m")
    print(f"{'='*55}")
    print(f"\n--- Core Score ---")
    print(f"  Total Road Length  : {total_length_m:>10,.1f} m  /  {total_length_km:>6.2f} km")
    print(f"  Road Density       : {road_density:>10.2f} km/km²")
    print(f"  Rating             : {rating}")
    print(f"\n--- Network Size ---")
    print(f"  Road segments      : {total_edges:>8,}")
    print(f"  Total nodes        : {total_nodes:>8,}")
    print(f"  Intersections      : {intersections:>8,}   (3+ roads meeting)")
    print(f"  Dead ends          : {dead_ends:>8,}")
    print(f"  One-way segments   : {oneway_count:>8,}")
    print(f"  Two-way segments   : {twoway_count:>8,}")
    print(f"\n--- Road Types ---")
    print(f"  {'Type':<25} {'Segments':>8}   {'Length':>10}")
    print(f"  {'─'*25} {'─'*8}   {'─'*10}")
    for rtype, count in sorted(road_types.items(), key=lambda x: -x[1]):
        km = length_by_type.get(rtype, 0) / 1000
        print(f"  {rtype:<25} {count:>8,}   {km:>8.2f} km")
    if named_roads:
        print(f"\n--- Named Roads ({len(named_roads)} found) ---")
        for name in named_roads[:25]:
            print(f"  - {name}")
        if len(named_roads) > 25:
            print(f"  ... and {len(named_roads) - 25} more")

    landmarks = get_landmark_distances(lat, lon, G_proj, dist)

    # Isochrones
    print("\n--- Computing Drive-Time Isochrones (5 / 10 / 15 min) ---")
    isochrones = {}
    try:
        isochrones = compute_isochrones(lat, lon, G_proj, trip_times_min=(5, 10, 15))
        for t, poly in isochrones.items():
            status = "✅ computed" if poly is not None else "⚠️  skipped (insufficient nodes)"
            print(f"  {t} min isochrone: {status}")
    except Exception as e:
        print(f"  Isochrone computation failed: {e}")

    print(f"\n{'='*55}\n")

    return {
        "road_score_m"      : round(total_length_m, 1),
        "road_score_km"     : round(total_length_km, 2),
        "road_density_km_km2": road_density,
        "rating"            : rating,
        "total_segments"    : total_edges,
        "total_nodes"       : total_nodes,
        "intersections"     : intersections,
        "dead_ends"         : dead_ends,
        "oneway_segments"   : oneway_count,
        "twoway_segments"   : twoway_count,
        "road_types"        : road_types,
        "length_by_type_km" : {k: round(v/1000, 2) for k, v in length_by_type.items()},
        "named_roads"       : named_roads,
        "landmarks"         : landmarks,
        "edges_gdf"         : edges,
        "nodes_gdf"         : nodes,
        "isochrones"        : isochrones,
    }


# ══════════════════════════════════════════════════════════════════
#  MODULE 2 — COMPETITOR + COMPLEMENTARY + ANCHOR ANALYSIS
# ══════════════════════════════════════════════════════════════════

BUSINESS_TAGS = {
    "restaurant"  : {"amenity": ["restaurant", "cafe", "fast_food", "food_court"]},
    "hardware"    : {"shop"   : ["hardware", "doityourself", "tools"]},
    "clothing"    : {"shop"   : ["clothes", "boutique", "fashion", "tailor"]},
    "supermarket" : {"shop"   : ["supermarket", "convenience", "grocery", "general"]},
    "pharmacy"    : {"amenity": ["pharmacy"], "shop": ["chemist", "medical"]},
    "hotel"       : {"tourism": ["hotel", "guest_house", "hostel", "motel"]},
    "bank"        : {"amenity": ["bank", "atm"]},
    "gym"         : {"leisure": ["fitness_centre", "sports_centre"], "amenity": ["gym"]},
    "school"      : {"amenity": ["school", "college", "university", "kindergarten"]},
    "hospital"    : {"amenity": ["hospital", "clinic", "doctors", "dentist"]},
    "petrol"      : {"amenity": ["fuel"]},
    "salon"       : {"shop"   : ["hairdresser", "beauty", "cosmetics"]},
    "electronics" : {"shop"   : ["electronics", "mobile_phone", "computer"]},
    "bakery"      : {"shop"   : ["bakery", "confectionery", "pastry"]},
    "jewellery"   : {"shop"   : ["jewellery", "jewelry", "goldsmith"]},
}

# Complementary business types per primary business
COMPLEMENTARY_TAGS = {
    "restaurant"  : {"amenity": ["parking"], "shop": ["supermarket", "bakery"]},
    "hardware"    : {"amenity": ["parking"], "shop": ["doityourself", "furniture"]},
    "clothing"    : {"shop"   : ["shoes", "accessories", "bag"], "amenity": ["atm"]},
    "supermarket" : {"amenity": ["parking", "atm", "pharmacy"]},
    "pharmacy"    : {"amenity": ["hospital", "doctors", "bank"]},
    "hotel"       : {"amenity": ["restaurant", "parking", "atm"], "tourism": ["attraction"]},
    "bank"        : {"amenity": ["atm", "parking"]},
    "gym"         : {"amenity": ["parking"], "shop": ["sports", "nutrition_supplements"]},
    "school"      : {"amenity": ["parking", "bus_station"], "shop": ["books", "stationery"]},
    "hospital"    : {"amenity": ["pharmacy", "parking", "bank"]},
    "petrol"      : {"shop"   : ["convenience"], "amenity": ["atm"]},
    "salon"       : {"shop"   : ["cosmetics", "beauty"], "amenity": ["atm"]},
    "electronics" : {"shop"   : ["mobile_phone", "computer"], "amenity": ["atm", "parking"]},
    "bakery"      : {"amenity": ["cafe"], "shop": ["confectionery"]},
    "jewellery"   : {"amenity": ["bank", "atm"], "shop": ["accessories"]},
}

# Anchor tenant tags — large footfall generators regardless of business type
ANCHOR_TAGS = {
    "shop"   : ["mall", "supermarket", "department_store"],
    "amenity": ["hospital", "university", "bus_station"],
    "tourism": ["attraction", "museum", "hotel"],
    "leisure": ["park", "sports_centre", "stadium"],
}


def _empty_comp(business_type):
    return {
        "total_count"       : 0,
        "named_count"       : 0,
        "unnamed_count"     : 0,
        "competition_level" : "Very Low ✅  — almost no competition",
        "category_breakdown": {},
        "competitors"       : [],
        "complementary"     : [],
        "anchor_tenants"    : [],
        "named_list"        : [],
        "business_type"     : business_type or "unknown",
    }


def _safe_str_comp(val):
    if val is None:
        return None
    if isinstance(val, list):
        return val[0] if val else None
    s = str(val)
    return None if s in ("nan", "None", "") else s


def fetch_pois_by_key(lat, lon, key, values, dist):
    all_pois = []
    for value in values:
        try:
            pois = ox.features_from_point((lat, lon), tags={key: value}, dist=dist)
            if not pois.empty:
                all_pois.append(pois)
        except Exception:
            pass
    return all_pois


def _parse_poi_row(row):
    name    = _safe_str_comp(row.get("name"))
    amenity = _safe_str_comp(row.get("amenity"))
    shop    = _safe_str_comp(row.get("shop"))
    tourism = _safe_str_comp(row.get("tourism"))
    leisure = _safe_str_comp(row.get("leisure"))
    phone   = _safe_str_comp(row.get("phone")) or _safe_str_comp(row.get("contact:phone"))
    website = _safe_str_comp(row.get("website")) or _safe_str_comp(row.get("contact:website"))
    hours   = _safe_str_comp(row.get("opening_hours"))
    brand   = _safe_str_comp(row.get("brand"))
    cuisine = _safe_str_comp(row.get("cuisine"))
    addr_h  = _safe_str_comp(row.get("addr:housenumber"))
    addr_s  = _safe_str_comp(row.get("addr:street"))
    addr_c  = _safe_str_comp(row.get("addr:city"))
    try:
        centroid = row.geometry.centroid
        c_lat    = centroid.y
        c_lon    = centroid.x
    except Exception:
        c_lat = c_lon = None
    addr_parts = [p for p in [addr_h, addr_s, addr_c] if p]
    category   = amenity or shop or tourism or leisure or "unknown"
    return {
        "name"    : name or "Unnamed",
        "category": category,
        "brand"   : brand,
        "cuisine" : cuisine,
        "address" : ", ".join(addr_parts) if addr_parts else None,
        "phone"   : phone,
        "website" : website,
        "hours"   : hours,
        "lat"     : c_lat,
        "lon"     : c_lon,
    }


def _fetch_multi_tags(lat, lon, tags_dict, dist, label="POIs"):
    all_dfs = []
    for key, values in tags_dict.items():
        if isinstance(values, list):
            all_dfs.extend(fetch_pois_by_key(lat, lon, key, values, dist))
        else:
            try:
                pois = ox.features_from_point((lat, lon), tags={key: values}, dist=dist)
                if not pois.empty:
                    all_dfs.append(pois)
            except Exception:
                pass
    if not all_dfs:
        return []
    try:
        combined = pd.concat(all_dfs)
        combined = combined[~combined.index.duplicated(keep="first")]
    except Exception:
        return []
    return [_parse_poi_row(row) for _, row in combined.iterrows()]


def get_competitors(lat, lon, business_type, dist=2000):
    tags = BUSINESS_TAGS.get(business_type.lower())
    if not tags:
        print(f"\n❌ Unknown business type: '{business_type}'")
        print(f"   Available types: {', '.join(BUSINESS_TAGS.keys())}")
        return _empty_comp(business_type)

    print(f"\nSearching competitors / complementary / anchors for '{business_type}' within {dist}m...")

    # --- Competitors ---
    competitors = _fetch_multi_tags(lat, lon, tags, dist, "Competitors")
    competitors.sort(key=lambda x: (x["name"] == "Unnamed", x["name"]))

    # --- Complementary businesses ---
    comp_tags = COMPLEMENTARY_TAGS.get(business_type.lower(), {})
    complementary = _fetch_multi_tags(lat, lon, comp_tags, dist, "Complementary") if comp_tags else []

    # --- Anchor tenants ---
    anchor_tenants = _fetch_multi_tags(lat, lon, ANCHOR_TAGS, dist, "Anchors")

    category_count = {}
    for c in competitors:
        cat = c["category"]
        category_count[cat] = category_count.get(cat, 0) + 1

    named   = [c for c in competitors if c["name"] != "Unnamed"]
    unnamed = [c for c in competitors if c["name"] == "Unnamed"]

    print(f"\n{'='*60}")
    print(f"  COMPETITOR ANALYSIS — {business_type}")
    print(f"{'='*60}")
    print(f"  Competitors : {len(competitors)}  |  Named: {len(named)}  |  Unnamed: {len(unnamed)}")
    print(f"  Complementary businesses : {len(complementary)}")
    print(f"  Anchor tenants nearby    : {len(anchor_tenants)}")

    print(f"\n--- Competitors by Category ---")
    for cat, count in sorted(category_count.items(), key=lambda x: -x[1]):
        print(f"  {cat:<25} : {count}")

    if named:
        print(f"\n--- Named Competitors ({len(named)}) ---")
        print(f"  {'#':<4} {'Name':<30} {'Category':<18} {'Extra Info'}")
        print(f"  {'─'*4} {'─'*30} {'─'*18} {'─'*20}")
        for i, c in enumerate(named, 1):
            extra_parts = []
            if c["cuisine"]: extra_parts.append(f"cuisine: {c['cuisine']}")
            if c["brand"]  : extra_parts.append(f"brand: {c['brand']}")
            extra = " | ".join(extra_parts) if extra_parts else ""
            print(f"  {i:<4} {c['name']:<30} {c['category']:<18} {extra}")

    if anchor_tenants:
        print(f"\n--- Anchor Tenants ({len(anchor_tenants)}) ---")
        for a in anchor_tenants[:10]:
            print(f"  ⚓ {a['name']}  [{a['category']}]")

    if complementary:
        print(f"\n--- Complementary Businesses ({len(complementary)}) ---")
        for c in complementary[:10]:
            print(f"  🤝 {c['name']}  [{c['category']}]")

    total = len(competitors)
    level = (
        "Very High 🔴 — extremely saturated market" if total > 50 else
        "High 🟠      — strong competition"          if total > 20 else
        "Moderate 🟡  — some competition"            if total > 10 else
        "Low 🟢       — good opportunity"            if total > 3  else
        "Very Low ✅  — almost no competition"
    )
    print(f"\n--- Competition Level ---\n  {level}")
    print(f"\n{'='*60}\n")

    return {
        "total_count"       : total,
        "named_count"       : len(named),
        "unnamed_count"     : len(unnamed),
        "competition_level" : level,
        "category_breakdown": category_count,
        "competitors"       : competitors,
        "complementary"     : complementary,
        "anchor_tenants"    : anchor_tenants,
        "named_list"        : [c["name"] for c in named],
        "business_type"     : business_type,
    }


# ══════════════════════════════════════════════════════════════════
#  MODULE 3 — WEATHER + AQI
# ══════════════════════════════════════════════════════════════════

WEATHER_URL = "https://archive-api.open-meteo.com/v1/archive"
AQI_URL     = "https://air-quality-api.open-meteo.com/v1/air-quality"


def fetch_weather(lat, lon, start_date, end_date):
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": start_date, "end_date": end_date,
        "daily": ["temperature_2m_max","temperature_2m_min","temperature_2m_mean",
                  "precipitation_sum","windspeed_10m_max",
                  "relative_humidity_2m_max","relative_humidity_2m_min","weathercode"],
        "timezone": "auto", "temperature_unit": "celsius", "windspeed_unit": "ms",
    }
    try:
        res  = requests.get(WEATHER_URL, params=params)
        data = res.json()
        if "error" in data:
            print(f"Weather API Error: {data['reason']}")
            return None
        return data["daily"]
    except Exception as e:
        print(f"Weather fetch error: {e}")
        return None


def fetch_aqi(lat, lon, start_date, end_date):
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": start_date, "end_date": end_date,
        "hourly": ["pm10","pm2_5","carbon_monoxide","nitrogen_dioxide","sulphur_dioxide",
                   "ozone","us_aqi","us_aqi_pm2_5","us_aqi_pm10","european_aqi","dust","uv_index"],
        "timezone": "auto",
    }
    try:
        res  = requests.get(AQI_URL, params=params)
        data = res.json()
        if "error" in data:
            print(f"AQI API Error: {data['reason']}")
            return None
        return data["hourly"]
    except Exception as e:
        print(f"AQI fetch error: {e}")
        return None


def aggregate_aqi_daily(hourly, dates):
    daily = {}
    for i, ts in enumerate(hourly["time"]):
        date = ts[:10]
        if date not in dates:
            continue
        if date not in daily:
            daily[date] = {k: [] for k in ["us_aqi","european_aqi","pm2_5","pm10",
                                            "no2","so2","ozone","co","dust","uv_index"]}
        field_map = {
            "us_aqi":"us_aqi","european_aqi":"european_aqi","pm2_5":"pm2_5","pm10":"pm10",
            "no2":"nitrogen_dioxide","so2":"sulphur_dioxide","ozone":"ozone",
            "co":"carbon_monoxide","dust":"dust","uv_index":"uv_index",
        }
        for key, field in field_map.items():
            v = hourly[field][i]
            if v is not None:
                daily[date][key].append(v)
    return {
        date: {k: round(sum(v)/len(v), 1) if v else None for k, v in fields.items()}
        for date, fields in daily.items()
    }


def us_aqi_label(aqi):
    if aqi is None: return "N/A"
    if aqi <= 50:   return "Good ✅"
    if aqi <= 100:  return "Moderate 🟡"
    if aqi <= 150:  return "Sensitive 🟠"
    if aqi <= 200:  return "Unhealthy 🔴"
    if aqi <= 300:  return "Very Unhealthy 🟣"
    return "Hazardous ☠️"


def eu_aqi_label(aqi):
    if aqi is None: return "N/A"
    if aqi <= 20:   return "Good ✅"
    if aqi <= 40:   return "Fair 🟢"
    if aqi <= 60:   return "Moderate 🟡"
    if aqi <= 80:   return "Poor 🟠"
    if aqi <= 100:  return "Very Poor 🔴"
    return "Extremely Poor ☠️"


def weather_label(code):
    codes = {
        0:"Clear ☀️",1:"Mainly clear 🌤️",2:"Partly cloudy ⛅",3:"Overcast ☁️",
        45:"Fog 🌫️",48:"Icy fog 🌫️",51:"Light drizzle 🌦️",53:"Drizzle 🌦️",
        55:"Heavy drizzle 🌧️",61:"Light rain 🌧️",63:"Rain 🌧️",65:"Heavy rain 🌧️",
        71:"Light snow 🌨️",73:"Snow 🌨️",75:"Heavy snow ❄️",80:"Showers 🌦️",
        81:"Heavy showers 🌧️",82:"Violent showers ⛈️",95:"Thunderstorm ⛈️",96:"Thunderstorm+hail ⛈️",
    }
    return codes.get(code, f"Code {code}")


def get_weather_aqi(lat, lon, start_date, end_date):
    dates = date_range(start_date, end_date)
    total = len(dates)

    print(f"\n{'='*70}")
    print(f"  Weather + AQI  |  {start_date} → {end_date}  ({total} days)")
    print(f"{'='*70}")
    print("\n[Fetching weather data...]")
    weather = fetch_weather(lat, lon, start_date, end_date)
    print("[Fetching AQI data...]")
    aqi_hourly = fetch_aqi(lat, lon, start_date, end_date)

    if not weather or not aqi_hourly:
        print("Failed to fetch data.")
        return None

    aqi_daily = aggregate_aqi_daily(aqi_hourly, set(dates))

    print(f"\n{'─'*70}")
    print(f"{'Date':<12} {'Condition':<20} {'Temp°C':>9} {'Rain mm':>8} {'Humidity%':>10} {'US AQI':>7} {'EU AQI':>7} {'PM2.5':>7} {'PM10':>6}")
    print(f"{'─'*70}")

    for i, date in enumerate(dates):
        wcode = weather["weathercode"][i]
        tmax  = weather["temperature_2m_max"][i]
        tmin  = weather["temperature_2m_min"][i]
        tmean = weather["temperature_2m_mean"][i]
        rain  = weather["precipitation_sum"][i]
        hmax  = weather["relative_humidity_2m_max"][i]
        hmin  = weather["relative_humidity_2m_min"][i]
        temp_str = f"{fmt(tmin)}–{fmt(tmax)}" if tmin and tmax else fmt(tmean)
        hum_str  = f"{fmt(hmin,decimals=0)}–{fmt(hmax,decimals=0)}"
        aqi  = aqi_daily.get(date, {})
        us   = aqi.get("us_aqi")
        eu   = aqi.get("european_aqi")
        pm25 = aqi.get("pm2_5")
        pm10 = aqi.get("pm10")
        print(f"{date:<12} {weather_label(wcode):<20} {temp_str:>9} {fmt(rain,'mm'):>8} {hum_str:>10} {fmt(us,decimals=0):>7} {fmt(eu,decimals=0):>7} {fmt(pm25,'μg'):>8} {fmt(pm10,'μg'):>7}")

    us_vals   = [aqi_daily[d]["us_aqi"]       for d in dates if d in aqi_daily and aqi_daily[d]["us_aqi"]       is not None]
    eu_vals   = [aqi_daily[d]["european_aqi"] for d in dates if d in aqi_daily and aqi_daily[d]["european_aqi"] is not None]
    tmp_vals  = [weather["temperature_2m_mean"][i] for i, d in enumerate(dates) if weather["temperature_2m_mean"][i] is not None]
    rain_vals = [weather["precipitation_sum"][i]   for i, d in enumerate(dates) if weather["precipitation_sum"][i]   is not None]

    print(f"\n{'='*70}")
    print(f"  RANGE SUMMARY  ({total} days)")
    print(f"{'='*70}")
    if tmp_vals:
        print(f"  Avg Temperature : {round(sum(tmp_vals)/len(tmp_vals),1)} °C")
        print(f"  Max Temperature : {max(weather['temperature_2m_max'])} °C")
        print(f"  Min Temperature : {min(weather['temperature_2m_min'])} °C")
    if rain_vals:
        print(f"  Total Rainfall  : {round(sum(rain_vals),1)} mm")
    if us_vals:
        avg_us = round(sum(us_vals)/len(us_vals), 1)
        print(f"  Avg US AQI      : {avg_us}  →  {us_aqi_label(avg_us)}")
    if eu_vals:
        avg_eu = round(sum(eu_vals)/len(eu_vals), 1)
        print(f"  Avg EU AQI      : {avg_eu}  →  {eu_aqi_label(avg_eu)}")
    print(f"{'='*70}\n")

    summary = {"start_date": start_date, "end_date": end_date, "days": total}
    if tmp_vals:
        summary["avg_temp"] = round(sum(tmp_vals)/len(tmp_vals), 1)
        summary["max_temp"] = max(weather["temperature_2m_max"])
        summary["min_temp"] = min(weather["temperature_2m_min"])
    if rain_vals:
        summary["total_rain"] = round(sum(rain_vals), 1)
    if us_vals:
        summary["avg_us_aqi"] = round(sum(us_vals)/len(us_vals), 1)
        summary["aqi_label"]  = us_aqi_label(summary["avg_us_aqi"])
    if eu_vals:
        summary["avg_eu_aqi"] = round(sum(eu_vals)/len(eu_vals), 1)
    return summary


# ══════════════════════════════════════════════════════════════════
#  MODULE 4 — POPULATION + DEMOGRAPHICS  (WorldPop + OSM proxy)
# ══════════════════════════════════════════════════════════════════

WORLDPOP_FILE = "worldpop.tif"


def estimate_income_proxy(lat, lon, dist):
    """
    Income proxy from OSM: count premium vs basic retail/services
    within the radius. Higher ratio → higher income area.
    """
    premium_tags = {
        "shop"   : ["jewelry", "jewellery", "boutique", "luxury"],
        "amenity": ["bank"],
        "tourism": ["hotel"],
    }
    basic_tags = {
        "shop"   : ["convenience", "general"],
        "amenity": ["fast_food"],
    }
    premium_count = len(_fetch_multi_tags(lat, lon, premium_tags, dist))
    basic_count   = len(_fetch_multi_tags(lat, lon, basic_tags, dist))
    total         = premium_count + basic_count
    if total == 0:
        ratio = 0.5
        label = "Unknown (insufficient OSM data)"
    else:
        ratio = premium_count / total
        label = (
            "High income area 💎"    if ratio > 0.6 else
            "Mixed income area 🏘️"  if ratio > 0.3 else
            "Lower income area 🏚️"
        )
    return {
        "premium_poi_count"  : premium_count,
        "basic_poi_count"    : basic_count,
        "income_proxy_ratio" : round(ratio, 3),
        "income_label"       : label,
    }


def estimate_age_distribution(lat, lon, dist):
    """
    Age distribution proxy from OSM amenities:
    - schools/playgrounds → young population
    - hospitals/clinics/retirement → older population
    - gyms/clubs/entertainment → working age
    """
    young_tags   = {"amenity": ["school", "kindergarten", "playground"]}
    working_tags = {"leisure": ["fitness_centre", "sports_centre", "nightclub"],
                    "amenity": ["gym", "cinema", "theatre"]}
    senior_tags  = {"amenity": ["hospital", "clinic", "nursing_home", "retirement_home"]}

    young   = len(_fetch_multi_tags(lat, lon, young_tags,   dist))
    working = len(_fetch_multi_tags(lat, lon, working_tags, dist))
    senior  = len(_fetch_multi_tags(lat, lon, senior_tags,  dist))
    total   = young + working + senior or 1

    dominant = max(
        [("Young (0–18)", young), ("Working Age (19–60)", working), ("Senior (60+)", senior)],
        key=lambda x: x[1]
    )[0]

    return {
        "young_poi_count"   : young,
        "working_poi_count" : working,
        "senior_poi_count"  : senior,
        "dominant_age_group": dominant,
        "young_pct"   : round(young   / total * 100, 1),
        "working_pct" : round(working / total * 100, 1),
        "senior_pct"  : round(senior  / total * 100, 1),
    }


def get_population(lat, lon, radius_pixels=5):
    age_data    = {}
    income_data = {}
    try:
        radius_m    = radius_pixels * 100
        print(f"\n--- Demographic Layer ---")

        # Population from WorldPop
        pop = 0
        try:
            with rasterio.open(WORLDPOP_FILE) as dataset:
                row, col = dataset.index(lon, lat)
                size     = radius_pixels * 2
                window   = Window(col - radius_pixels, row - radius_pixels, size, size)
                data     = dataset.read(1, window=window)
                pop      = float(data.sum())
        except FileNotFoundError:
            print(f"  ⚠️  WorldPop file '{WORLDPOP_FILE}' not found — population set to 0.")
            print(f"      Download: https://www.worldpop.org/geodata/listing?id=29")
        except Exception as e:
            print(f"  WorldPop error: {e}")

        area_km2  = math.pi * (radius_m / 1000) ** 2
        pop_density = round(pop / area_km2, 1) if area_km2 > 0 else 0

        level = (
            "Very High 🔴 — Dense urban" if pop > 100_000 else
            "High 🟠 — Urban"            if pop > 50_000  else
            "Moderate 🟡 — Semi-urban"   if pop > 10_000  else
            "Low 🟢 — Suburban/rural"    if pop > 1_000   else
            "Very Low ✅ — Sparse"
        )

        print(f"  Population (WorldPop) : {pop:,.0f}  |  Density: {pop_density:,.1f} /km²")
        print(f"  Level                 : {level}")

        # Income proxy
        print("  [Fetching income proxy via OSM...]")
        income_data = estimate_income_proxy(lat, lon, radius_m)
        print(f"  Income Proxy          : {income_data['income_label']} (ratio {income_data['income_proxy_ratio']})")

        # Age distribution proxy
        print("  [Fetching age distribution proxy via OSM...]")
        age_data = estimate_age_distribution(lat, lon, radius_m)
        print(f"  Age Distribution      : Dominant → {age_data['dominant_age_group']}")
        print(f"    Young {age_data['young_pct']}%  |  Working {age_data['working_pct']}%  |  Senior {age_data['senior_pct']}%")

        print(f"{'='*50}\n")

        return {
            "population"     : pop,
            "pop_density_km2": pop_density,
            "level"          : level,
            "radius_m"       : radius_m,
            "income"         : income_data,
            "age_distribution": age_data,
        }

    except Exception as e:
        print(f"  Population module error: {e}")
        return {
            "population": 0, "pop_density_km2": 0,
            "level": "Error", "radius_m": radius_pixels * 100,
            "income": income_data, "age_distribution": age_data,
        }


# ══════════════════════════════════════════════════════════════════
#  MODULE 5 — LAND USE, ZONING & BUILDING FOOTPRINTS
# ══════════════════════════════════════════════════════════════════

LANDUSE_COLORS = {
    "commercial"  : "#fbbf24",
    "retail"      : "#f97316",
    "residential" : "#86efac",
    "industrial"  : "#94a3b8",
    "farmland"    : "#d9f99d",
    "forest"      : "#4ade80",
    "meadow"      : "#a7f3d0",
    "park"        : "#6ee7b7",
    "construction": "#fca5a5",
    "military"    : "#b45309",
    "cemetery"    : "#e5e7eb",
    "education"   : "#c4b5fd",
    "health"      : "#fda4af",
}


def get_landuse_zoning(lat, lon, dist):
    """
    Fetch land use and building footprints from OSM.
    Returns categorised landuse polygons + building footprint stats.
    """
    print(f"\n--- Land Use & Zoning Layer ---")

    landuse_data   = []
    building_data  = []
    zone_breakdown = {}

    # Land use
    try:
        landuse_tags = {"landuse": True}
        lu_gdf = ox.features_from_point((lat, lon), tags=landuse_tags, dist=dist)
        if not lu_gdf.empty:
            lu_gdf = lu_gdf.copy()
            for _, row in lu_gdf.iterrows():
                lu_type = safe_str(row.get("landuse", "unknown"))
                try:
                    centroid = row.geometry.centroid
                    c_lat, c_lon = centroid.y, centroid.x
                    area_m2 = row.geometry.area if row.geometry else 0
                except Exception:
                    c_lat = c_lon = None
                    area_m2 = 0
                zone_breakdown[lu_type] = zone_breakdown.get(lu_type, 0) + 1
                landuse_data.append({
                    "type"   : lu_type,
                    "name"   : safe_str(row.get("name", None)),
                    "lat"    : c_lat,
                    "lon"    : c_lon,
                    "area_m2": round(area_m2, 1),
                })
        print(f"  Land use polygons found : {len(landuse_data)}")
        for lu, cnt in sorted(zone_breakdown.items(), key=lambda x: -x[1]):
            print(f"    {lu:<20} : {cnt}")
    except Exception as e:
        print(f"  Land use fetch error: {e}")

    # Building footprints
    try:
        building_tags = {"building": True}
        bld_gdf = ox.features_from_point((lat, lon), tags=building_tags, dist=dist)
        if not bld_gdf.empty:
            bld_gdf = bld_gdf.copy()
            total_bld     = len(bld_gdf)
            bld_types     = {}
            total_bld_area = 0
            for _, row in bld_gdf.iterrows():
                btype = safe_str(row.get("building", "yes"))
                bld_types[btype] = bld_types.get(btype, 0) + 1
                try:
                    total_bld_area += row.geometry.area
                except Exception:
                    pass
                try:
                    centroid = row.geometry.centroid
                    c_lat, c_lon = centroid.y, centroid.x
                except Exception:
                    c_lat = c_lon = None
                building_data.append({
                    "type": btype,
                    "lat" : c_lat,
                    "lon" : c_lon,
                    "area_m2": round(getattr(row.geometry, "area", 0), 1),
                })
            print(f"  Building footprints    : {total_bld}  |  Total area: {total_bld_area:,.0f} m²")
            for bt, cnt in sorted(bld_types.items(), key=lambda x: -x[1])[:8]:
                print(f"    {bt:<20} : {cnt}")
    except Exception as e:
        print(f"  Building footprint error: {e}")

    # Dominant zone classification
    dominant_zone = "unknown"
    if zone_breakdown:
        dominant_zone = max(zone_breakdown, key=zone_breakdown.get)

    zone_label = (
        "Commercial Zone 🏪"    if dominant_zone in ("commercial", "retail") else
        "Residential Zone 🏘️"  if dominant_zone in ("residential",) else
        "Industrial Zone 🏭"   if dominant_zone in ("industrial",) else
        "Mixed / Other Zone 🗺️"
    )

    print(f"  Dominant Zone : {zone_label}")
    print(f"{'='*50}\n")

    return {
        "landuse_features": landuse_data,
        "building_features": building_data,
        "zone_breakdown"   : zone_breakdown,
        "dominant_zone"    : dominant_zone,
        "zone_label"       : zone_label,
    }


# ══════════════════════════════════════════════════════════════════
#  MODULE 6 — ENVIRONMENTAL & RISK DATA
# ══════════════════════════════════════════════════════════════════

def get_flood_risk(lat, lon, dist):
    """
    Fetch OSM natural flood-prone / water features near the point.
    Also queries Open-Elevation for terrain data as a flood proxy.
    """
    print("  [Flood Risk] Querying OSM water/flood features...")
    flood_tags = {
        "natural"   : ["water", "wetland", "flood_prone", "floodplain"],
        "waterway"  : ["river", "stream", "canal", "drain"],
        "landuse"   : ["floodplain"],
        "hazard"    : ["flood"],
    }
    water_features = []
    water_count    = 0
    try:
        gdf = ox.features_from_point((lat, lon), tags=flood_tags, dist=dist)
        if not gdf.empty:
            water_count = len(gdf)
            for _, row in gdf.iterrows():
                feat_type = (safe_str(row.get("natural")) or safe_str(row.get("waterway")) or
                             safe_str(row.get("landuse")) or "water_feature")
                try:
                    c = row.geometry.centroid
                    c_lat, c_lon = c.y, c.x
                except Exception:
                    c_lat = c_lon = None
                water_features.append({
                    "type": feat_type,
                    "name": safe_str(row.get("name", "unnamed")),
                    "lat" : c_lat,
                    "lon" : c_lon,
                })
    except Exception as e:
        print(f"    Flood OSM query error: {e}")

    # Elevation proxy via Open-Elevation API
    elevation_m = None
    try:
        r = requests.get(
            "https://api.open-elevation.com/api/v1/lookup",
            params={"locations": f"{lat},{lon}"},
            timeout=8
        )
        data = r.json()
        elevation_m = data["results"][0]["elevation"]
    except Exception:
        pass

    flood_risk_score = (
        "High 🔴"    if water_count > 5 or (elevation_m is not None and elevation_m < 5) else
        "Moderate 🟡" if water_count > 2 or (elevation_m is not None and elevation_m < 20) else
        "Low 🟢"
    )

    print(f"    Water/flood features nearby : {water_count}")
    print(f"    Elevation (approx)          : {elevation_m} m" if elevation_m else "    Elevation: unavailable")
    print(f"    Flood Risk Score            : {flood_risk_score}")

    return {
        "water_feature_count": water_count,
        "water_features"     : water_features,
        "elevation_m"        : elevation_m,
        "flood_risk_score"   : flood_risk_score,
    }


def get_earthquake_risk(lat, lon):
    """
    Query USGS Earthquake Hazards API for seismic hazard at the location.
    Returns peak ground acceleration (PGA) estimate where available.
    """
    print("  [Earthquake Risk] Querying USGS seismic hazard...")
    pga    = None
    label  = "Unknown"
    source = "USGS"

    try:
        # USGS Unified Hazard Tool (static hazard data at 2% in 50 years)
        url    = "https://earthquake.usgs.gov/ws/designmaps/asce7-22.json"
        params = {"latitude": lat, "longitude": lon, "riskCategory": "II",
                  "siteClass": "D", "title": "location_intel"}
        r      = requests.get(url, params=params, timeout=10)
        data   = r.json()
        pga    = data.get("output", {}).get("data", [{}])[0].get("pga")
        if pga is not None:
            label = (
                "Very High ☠️ (>0.6g)"  if pga > 0.6 else
                "High 🔴 (0.3–0.6g)"    if pga > 0.3 else
                "Moderate 🟡 (0.1–0.3g)" if pga > 0.1 else
                "Low 🟢 (<0.1g)"
            )
    except Exception as e:
        # Fallback: recent earthquakes within ~200 km
        try:
            r2   = requests.get(
                "https://earthquake.usgs.gov/fdsnws/event/1/query",
                params={"format":"geojson","latitude":lat,"longitude":lon,
                        "maxradiuskm":200,"minmagnitude":3.0,"limit":5,"orderby":"magnitude"},
                timeout=10
            )
            feats = r2.json().get("features", [])
            if feats:
                max_mag = max(f["properties"]["mag"] for f in feats)
                label   = (
                    "High 🔴 (recent M≥5 activity)"    if max_mag >= 5 else
                    "Moderate 🟡 (recent M3–5 activity)" if max_mag >= 3 else
                    "Low 🟢"
                )
                source  = "USGS recent events (fallback)"
            else:
                label  = "Low 🟢 (no recent M≥3 events nearby)"
                source = "USGS recent events (fallback)"
        except Exception:
            label  = "Unavailable"
            source = "N/A"

    print(f"    PGA (USGS)     : {pga}g" if pga else f"    PGA: unavailable")
    print(f"    Seismic Label  : {label}")
    print(f"    Source         : {source}")

    return {"pga_g": pga, "earthquake_label": label, "source": source}


def get_environmental_risk(lat, lon, dist, weather_summary=None):
    """Combine flood, earthquake and AQI into one environmental risk block."""
    print(f"\n--- Environmental & Risk Layer ---")
    flood    = get_flood_risk(lat, lon, dist)
    quake    = get_earthquake_risk(lat, lon)

    aqi_label = "N/A"
    avg_aqi   = None
    if weather_summary:
        avg_aqi   = weather_summary.get("avg_us_aqi")
        aqi_label = weather_summary.get("aqi_label", "N/A")

    print(f"  AQI (from weather module)   : {avg_aqi} → {aqi_label}")
    print(f"{'='*50}\n")

    return {
        "flood"   : flood,
        "earthquake": quake,
        "aqi_summary": {"avg_us_aqi": avg_aqi, "label": aqi_label},
    }


# ══════════════════════════════════════════════════════════════════
#  GEOJSON EXPORT — all layers → one FeatureCollection
# ══════════════════════════════════════════════════════════════════

def _clean_props(d: dict) -> dict:
    """Recursively make all values JSON-serialisable."""
    out = {}
    for k, v in d.items():
        if v is None or isinstance(v, (str, int, float, bool)):
            out[k] = v
        elif isinstance(v, dict):
            out[k] = _clean_props(v)
        elif isinstance(v, (list, tuple)):
            out[k] = [_clean_props(i) if isinstance(i, dict) else
                      (None if not isinstance(i, (str, int, float, bool)) else i)
                      for i in v]
        else:
            out[k] = str(v)
    return out


def build_geojson(lat, lon, dist, results) -> dict:
    """
    Assemble a GeoJSON FeatureCollection from all analysis results.
    Every data point becomes a Feature with appropriate geometry.
    """
    features = []

    # ── Origin point ──────────────────────────────────────────────
    features.append({
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": _clean_props({
            "layer"  : "origin",
            "label"  : "Analysis Origin",
            "radius_m": dist,
        }),
    })

    # ── Layer 1: Demographics ─────────────────────────────────────
    pop = results.get("population", {})
    if pop:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": _clean_props({
                "layer"          : "demographics",
                "population"     : pop.get("population"),
                "pop_density_km2": pop.get("pop_density_km2"),
                "level"          : pop.get("level"),
                "radius_m"       : pop.get("radius_m"),
                **({
                    "income_proxy_ratio" : pop["income"].get("income_proxy_ratio"),
                    "income_label"       : pop["income"].get("income_label"),
                } if pop.get("income") else {}),
                **({
                    "age_dominant_group" : pop["age_distribution"].get("dominant_age_group"),
                    "age_young_pct"      : pop["age_distribution"].get("young_pct"),
                    "age_working_pct"    : pop["age_distribution"].get("working_pct"),
                    "age_senior_pct"     : pop["age_distribution"].get("senior_pct"),
                } if pop.get("age_distribution") else {}),
            }),
        })

    # ── Layer 2a: Road network summary ───────────────────────────
    roads = results.get("roads", {})
    if roads:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": _clean_props({
                "layer"              : "transportation_summary",
                "road_length_km"     : roads.get("road_score_km"),
                "road_density_km_km2": roads.get("road_density_km_km2"),
                "rating"             : roads.get("rating"),
                "total_segments"     : roads.get("total_segments"),
                "intersections"      : roads.get("intersections"),
                "dead_ends"          : roads.get("dead_ends"),
            }),
        })

    # ── Layer 2b: Isochrones ─────────────────────────────────────
    for t_min, poly in (roads.get("isochrones") or {}).items():
        if poly is not None:
            try:
                # poly coords are (lat, lon) — swap to GeoJSON (lon, lat)
                coords = [[lon2, lat2] for lat2, lon2 in list(poly.exterior.coords)]
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [coords]},
                    "properties": {
                        "layer"          : "isochrone",
                        "travel_time_min": t_min,
                        "label"          : f"{t_min}-minute drive-time isochrone",
                    },
                })
            except Exception:
                pass

    # ── Layer 2c: Landmarks ───────────────────────────────────────
    for lm in (roads.get("landmarks") or []):
        if lm.get("lat") is not None:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lm["lon"], lm["lat"]]},
                "properties": _clean_props({
                    "layer"      : "landmark",
                    "label"      : lm.get("label"),
                    "name"       : lm.get("name"),
                    "distance_m" : lm.get("distance_m"),
                    "route_type" : lm.get("note"),
                }),
            })

    # ── Layer 3: POIs ─────────────────────────────────────────────
    comp = results.get("competitors", {})
    for item in (comp.get("competitors") or []):
        if item.get("lat") is not None:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [item["lon"], item["lat"]]},
                "properties": _clean_props({**item, "layer": "competitor"}),
            })
    for item in (comp.get("complementary") or []):
        if item.get("lat") is not None:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [item["lon"], item["lat"]]},
                "properties": _clean_props({**item, "layer": "complementary_business"}),
            })
    for item in (comp.get("anchor_tenants") or []):
        if item.get("lat") is not None:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [item["lon"], item["lat"]]},
                "properties": _clean_props({**item, "layer": "anchor_tenant"}),
            })

    # ── Layer 4: Land use ─────────────────────────────────────────
    landuse = results.get("landuse", {})
    for item in (landuse.get("landuse_features") or []):
        if item.get("lat") is not None:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [item["lon"], item["lat"]]},
                "properties": _clean_props({**item, "layer": "landuse"}),
            })
    for item in (landuse.get("building_features") or []):
        if item.get("lat") is not None:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [item["lon"], item["lat"]]},
                "properties": _clean_props({**item, "layer": "building_footprint"}),
            })

    # ── Layer 5: Environmental / risk ─────────────────────────────
    env = results.get("environmental", {})
    # Flood
    flood = env.get("flood", {})
    features.append({
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": _clean_props({
            "layer"               : "flood_risk",
            "flood_risk_score"    : flood.get("flood_risk_score"),
            "water_feature_count" : flood.get("water_feature_count"),
            "elevation_m"         : flood.get("elevation_m"),
        }),
    })
    for wf in (flood.get("water_features") or []):
        if wf.get("lat") is not None:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [wf["lon"], wf["lat"]]},
                "properties": _clean_props({**wf, "layer": "water_feature"}),
            })
    # Earthquake
    quake = env.get("earthquake", {})
    features.append({
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": _clean_props({
            "layer"            : "earthquake_risk",
            "pga_g"            : quake.get("pga_g"),
            "earthquake_label" : quake.get("earthquake_label"),
            "source"           : quake.get("source"),
        }),
    })
    # AQI
    aqi_s = env.get("aqi_summary", {})
    features.append({
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": _clean_props({
            "layer"      : "air_quality",
            "avg_us_aqi" : aqi_s.get("avg_us_aqi"),
            "aqi_label"  : aqi_s.get("label"),
        }),
    })

    # ── Weather summary ───────────────────────────────────────────
    weather = results.get("weather")
    if weather:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": _clean_props({"layer": "weather_summary", **weather}),
        })

    return {
        "type"    : "FeatureCollection",
        "features": features,
        "metadata": {
            "generated_at"     : datetime.utcnow().isoformat() + "Z",
            "origin_lat"       : lat,
            "origin_lon"       : lon,
            "analysis_radius_m": dist,
            "total_features"   : len(features),
            "layers": [
                "origin", "demographics", "transportation_summary",
                "isochrone", "landmark", "competitor", "complementary_business",
                "anchor_tenant", "landuse", "building_footprint",
                "flood_risk", "water_feature", "earthquake_risk",
                "air_quality", "weather_summary",
            ],
        },
    }


# ══════════════════════════════════════════════════════════════════
#  MODULE MAP — FOLIUM (same visual output as original)
# ══════════════════════════════════════════════════════════════════

LANDMARK_COLORS = {
    "🚌 Bus Stand"      : "blue",
    "🚌 Bus Stop"       : "lightblue",
    "🚌 Transit Stop"   : "cadetblue",
    "🏥 Hospital"       : "red",
    "🏫 School"         : "orange",
    "🎓 College"        : "orange",
    "⛽ Fuel Station"   : "darkgreen",
    "👮 Police Station" : "darkblue",
    "🏦 Bank"           : "purple",
    "💊 Pharmacy"       : "pink",
    "🛒 Market"         : "green",
    "🛒 Supermarket"    : "green",
    "🏬 Mall"           : "darkpurple",
    "🚉 Railway Station": "darkred",
    "🚉 Railway Halt"   : "darkred",
    "📍 Other"          : "gray",
}

ROAD_COLORS = {
    "motorway"      : "#e92b2b",
    "trunk"         : "#f97c2b",
    "primary"       : "#fcd34d",
    "secondary"     : "#86efac",
    "tertiary"      : "#93c5fd",
    "residential"   : "#c4b5fd",
    "living_street" : "#d1d5db",
    "unclassified"  : "#9ca3af",
    "trunk_link"    : "#fdba74",
    "primary_link"  : "#fde68a",
    "tertiary_link" : "#bfdbfe",
    "secondary_link": "#bbf7d0",
}

ISOCHRONE_STYLES = {
    5 : {"color": "#22c55e", "fill_color": "#22c55e", "fill_opacity": 0.08, "weight": 2, "dash": "8 4"},
    10: {"color": "#f59e0b", "fill_color": "#f59e0b", "fill_opacity": 0.06, "weight": 2, "dash": "8 4"},
    15: {"color": "#ef4444", "fill_color": "#ef4444", "fill_opacity": 0.05, "weight": 2, "dash": "8 4"},
}


def build_map(lat, lon, dist, results):
    m = folium.Map(location=[lat, lon], zoom_start=14, tiles="CartoDB positron")

    # ── 1. Search radius circle ──────────────────────────────
    folium.Circle(
        location=[lat, lon], radius=dist,
        color="#3b82f6", fill=True, fill_color="#3b82f6",
        fill_opacity=0.05, weight=2,
        tooltip=f"Search radius: {dist} m",
    ).add_to(m)

    # ── 2. Origin marker ─────────────────────────────────────
    folium.Marker(
        location=[lat, lon],
        tooltip="📍 Your Location",
        popup=folium.Popup(
            f"<b>📍 Origin Point</b><br>Lat: {lat}<br>Lon: {lon}<br>Radius: {dist} m",
            max_width=200),
        icon=folium.Icon(color="red", icon="home", prefix="fa"),
    ).add_to(m)

    road_data = results.get("roads")

    # ── 3. Isochrones ─────────────────────────────────────────
    if road_data and road_data.get("isochrones"):
        iso_layer = folium.FeatureGroup(name="🕐 Drive-Time Isochrones", show=True)
        for t_min in [15, 10, 5]:  # draw largest first
            poly = road_data["isochrones"].get(t_min)
            if poly is not None:
                try:
                    st = ISOCHRONE_STYLES[t_min]
                    coords = [(lat2, lon2) for lat2, lon2 in list(poly.exterior.coords)]
                    folium.Polygon(
                        locations=coords,
                        color=st["color"], fill=True,
                        fill_color=st["fill_color"],
                        fill_opacity=st["fill_opacity"],
                        weight=st["weight"],
                        dash_array=st["dash"],
                        tooltip=f"{t_min}-minute drive-time isochrone",
                    ).add_to(iso_layer)
                except Exception:
                    pass
        iso_layer.add_to(m)

    # ── 4. Road network overlay ──────────────────────────────
    if road_data and "edges_gdf" in road_data:
        road_layer = folium.FeatureGroup(name="🛣 Road Network", show=True)
        try:
            edges_wgs = road_data["edges_gdf"].to_crs("epsg:4326")
            for _, row in edges_wgs.iterrows():
                rtype  = safe_str(row.get("highway", "unclassified"))
                color  = ROAD_COLORS.get(rtype, "#9ca3af")
                weight = 4   if rtype in ("motorway","trunk","primary") else \
                         2.5 if rtype in ("secondary","tertiary") else 1.5
                try:
                    coords = [(c[1], c[0]) for c in row.geometry.coords]
                    name   = safe_str(row.get("name", "unknown"))
                    tip    = f"{rtype} — {name}" if name not in ("unknown","unnamed") else rtype
                    folium.PolyLine(coords, color=color, weight=weight,
                                   opacity=0.75, tooltip=tip).add_to(road_layer)
                except Exception:
                    pass
        except Exception as e:
            print(f"  (Road overlay skipped: {e})")
        road_layer.add_to(m)

    # ── 5. Land use overlay ───────────────────────────────────
    landuse_data = results.get("landuse", {})
    if landuse_data and landuse_data.get("landuse_features"):
        lu_layer = folium.FeatureGroup(name="🗺️ Land Use / Zoning", show=False)
        for item in landuse_data["landuse_features"]:
            if item.get("lat") is None:
                continue
            color = LANDUSE_COLORS.get(item["type"], "#e5e7eb")
            folium.CircleMarker(
                location=[item["lat"], item["lon"]],
                radius=6, color=color, fill=True, fill_color=color,
                fill_opacity=0.7,
                tooltip=f"🗺️ {item['type']} — {item['name']}",
                popup=folium.Popup(
                    f"<b>Land Use: {item['type']}</b><br>Name: {item['name']}<br>"
                    f"Area: {item['area_m2']:,.0f} m²", max_width=200),
            ).add_to(lu_layer)
        lu_layer.add_to(m)

    # ── 6. Building footprints (sample, clustered) ────────────
    if landuse_data and landuse_data.get("building_features"):
        bld_layer   = folium.FeatureGroup(name="🏗️ Building Footprints", show=False)
        bld_cluster = MarkerCluster().add_to(bld_layer)
        for item in landuse_data["building_features"][:500]:   # cap at 500 for perf
            if item.get("lat") is None:
                continue
            folium.CircleMarker(
                location=[item["lat"], item["lon"]],
                radius=3, color="#64748b", fill=True, fill_color="#64748b",
                fill_opacity=0.5,
                tooltip=f"🏗️ {item['type']} ({item['area_m2']:,.0f} m²)",
            ).add_to(bld_cluster)
        bld_layer.add_to(m)

    # ── 7. Landmark markers (clustered) ──────────────────────
    if road_data and road_data.get("landmarks"):
        lm_layer   = folium.FeatureGroup(name="📍 Landmarks", show=True)
        lm_cluster = MarkerCluster().add_to(lm_layer)
        seen       = set()
        for lm in road_data["landmarks"]:
            if lm.get("lat") is None:
                continue
            key = (round(lm["lat"], 5), round(lm["lon"], 5))
            if key in seen:
                continue
            seen.add(key)
            color = LANDMARK_COLORS.get(lm["label"], "gray")
            d     = lm["distance_m"]
            d_str = f"{d:,.0f} m" if d < 1000 else f"{d/1000:.2f} km"
            folium.Marker(
                location=[lm["lat"], lm["lon"]],
                tooltip=f"{lm['label']} — {lm['name']} ({d_str})",
                popup=folium.Popup(
                    f"<b>{lm['label']}</b><br><b>{lm['name']}</b><br>"
                    f"Distance: <b>{d_str}</b><br>Via: {lm['note']}",
                    max_width=260),
                icon=folium.Icon(color=color, icon="info-sign"),
            ).add_to(lm_cluster)
        lm_layer.add_to(m)

    # ── 8. Competitor markers (clustered) ────────────────────
    comp_data = results.get("competitors")
    if comp_data and comp_data.get("total_count", 0) > 0:
        btype        = comp_data.get("business_type", "business")
        comp_layer   = folium.FeatureGroup(name=f"🏪 Competitors ({btype})", show=True)
        comp_cluster = MarkerCluster().add_to(comp_layer)
        seen         = set()
        for c in comp_data.get("competitors", []):
            if c.get("lat") is None:
                continue
            key = (round(c["lat"], 5), round(c["lon"], 5))
            if key in seen:
                continue
            seen.add(key)
            lines = [f"<b>{c['name']}</b>", f"Type: {c['category']}"]
            if c.get("address") : lines.append(f"📍 {c['address']}")
            if c.get("phone")   : lines.append(f"📞 {c['phone']}")
            if c.get("hours")   : lines.append(f"🕐 {c['hours']}")
            if c.get("cuisine") : lines.append(f"🍽 {c['cuisine']}")
            if c.get("website") : lines.append(f"🌐 {c['website']}")
            folium.Marker(
                location=[c["lat"], c["lon"]],
                tooltip=f"🏪 {c['name']} [{c['category']}]",
                popup=folium.Popup("<br>".join(lines), max_width=270),
                icon=folium.Icon(color="orange", icon="shopping-cart", prefix="fa"),
            ).add_to(comp_cluster)
        comp_layer.add_to(m)

        # Complementary businesses
        if comp_data.get("complementary"):
            cpl_layer   = folium.FeatureGroup(name="🤝 Complementary Businesses", show=False)
            cpl_cluster = MarkerCluster().add_to(cpl_layer)
            for c in comp_data["complementary"]:
                if c.get("lat") is None:
                    continue
                folium.Marker(
                    location=[c["lat"], c["lon"]],
                    tooltip=f"🤝 {c['name']} [{c['category']}]",
                    popup=folium.Popup(f"<b>{c['name']}</b><br>Type: {c['category']}", max_width=220),
                    icon=folium.Icon(color="green", icon="handshake-o", prefix="fa"),
                ).add_to(cpl_cluster)
            cpl_layer.add_to(m)

        # Anchor tenants
        if comp_data.get("anchor_tenants"):
            anc_layer   = folium.FeatureGroup(name="⚓ Anchor Tenants", show=False)
            anc_cluster = MarkerCluster().add_to(anc_layer)
            for c in comp_data["anchor_tenants"]:
                if c.get("lat") is None:
                    continue
                folium.Marker(
                    location=[c["lat"], c["lon"]],
                    tooltip=f"⚓ {c['name']} [{c['category']}]",
                    popup=folium.Popup(f"<b>{c['name']}</b><br>Type: {c['category']}", max_width=220),
                    icon=folium.Icon(color="darkpurple", icon="anchor", prefix="fa"),
                ).add_to(anc_cluster)
            anc_layer.add_to(m)

    # ── 9. Flood / water features ────────────────────────────
    env_data = results.get("environmental", {})
    flood_data = env_data.get("flood", {})
    if flood_data.get("water_features"):
        fl_layer = folium.FeatureGroup(name="💧 Flood / Water Features", show=False)
        for wf in flood_data["water_features"]:
            if wf.get("lat") is None:
                continue
            folium.CircleMarker(
                location=[wf["lat"], wf["lon"]],
                radius=6, color="#0ea5e9", fill=True, fill_color="#0ea5e9",
                fill_opacity=0.6,
                tooltip=f"💧 {wf['type']} — {wf['name']}",
            ).add_to(fl_layer)
        fl_layer.add_to(m)

    # ── 10. Info panel (top-right) ────────────────────────────
    road_html = comp_html = weather_html = pop_html = env_html = lu_html = ""

    if road_data:
        road_html = f"""
        <div class="panel-section">
          <div class="section-title" style="color:#1d4ed8">🛣 Road Network</div>
          <b>{road_data['road_score_km']} km</b> total &nbsp;·&nbsp;
          Density: <b>{road_data.get('road_density_km_km2','N/A')} km/km²</b><br>
          {road_data['rating']}<br>
          <span class="muted">
            Segments: {road_data['total_segments']:,} &nbsp;·&nbsp;
            Nodes: {road_data['total_nodes']:,}<br>
            Intersections: {road_data['intersections']:,} &nbsp;·&nbsp;
            Dead-ends: {road_data['dead_ends']:,}
          </span>
        </div>"""

    if comp_data:
        total_c = comp_data.get("total_count", 0)
        named_c = comp_data.get("named_count", 0)
        level_c = comp_data.get("competition_level", "N/A")
        btype_c = comp_data.get("business_type", "")
        anc_c   = len(comp_data.get("anchor_tenants", []))
        cpl_c   = len(comp_data.get("complementary", []))
        comp_html = f"""
        <div class="panel-section">
          <div class="section-title" style="color:#d97706">🏪 POIs</div>
          Business: <b>{btype_c}</b><br>
          Competitors: <b>{total_c}</b> (named: {named_c})<br>
          Complementary: <b>{cpl_c}</b> &nbsp;·&nbsp; Anchors: <b>{anc_c}</b><br>
          <span class="muted">{level_c}</span>
        </div>"""

    weather_s = results.get("weather")
    if weather_s:
        weather_html = f"""
        <div class="panel-section">
          <div class="section-title" style="color:#0f766e">🌤 Weather & AQI</div>
          Period: {weather_s.get('start_date','')} → {weather_s.get('end_date','')}<br>
          Avg Temp: <b>{weather_s.get('avg_temp','N/A')} °C</b>
          &nbsp;(max {weather_s.get('max_temp','N/A')}°C)<br>
          Rain: {weather_s.get('total_rain','N/A')} mm &nbsp;·&nbsp;
          AQI: {weather_s.get('avg_us_aqi','N/A')}
          <span class="muted">({weather_s.get('aqi_label','N/A')})</span>
        </div>"""

    pop_s = results.get("population")
    if pop_s and pop_s.get("population", 0) > 0:
        age_d  = pop_s.get("age_distribution", {})
        inc_d  = pop_s.get("income", {})
        pop_html = f"""
        <div class="panel-section">
          <div class="section-title" style="color:#7c3aed">👥 Demographics</div>
          Pop: <b>{pop_s['population']:,.0f}</b>
          &nbsp;·&nbsp; Density: <b>{pop_s['pop_density_km2']:,.0f} /km²</b><br>
          <span class="muted">{pop_s['level']}</span><br>
          Income: <span class="muted">{inc_d.get('income_label','N/A')}</span><br>
          Age: <span class="muted">{age_d.get('dominant_age_group','N/A')}</span>
        </div>"""

    if landuse_data:
        dom_zone = landuse_data.get("zone_label", "N/A")
        zb       = landuse_data.get("zone_breakdown", {})
        bld_cnt  = len(landuse_data.get("building_features", []))
        top_zones = ", ".join(f"{k}:{v}" for k, v in list(sorted(
            zb.items(), key=lambda x: -x[1]))[:3]) if zb else "N/A"
        lu_html = f"""
        <div class="panel-section">
          <div class="section-title" style="color:#b45309">🗺️ Land Use</div>
          Dominant: <b>{dom_zone}</b><br>
          Top zones: <span class="muted">{top_zones}</span><br>
          Building footprints: <b>{bld_cnt}</b>
        </div>"""

    if env_data:
        fl   = env_data.get("flood", {})
        qk   = env_data.get("earthquake", {})
        env_html = f"""
        <div class="panel-section">
          <div class="section-title" style="color:#dc2626">⚠️ Environmental Risk</div>
          Flood: <b>{fl.get('flood_risk_score','N/A')}</b>
          &nbsp;·&nbsp; Elev: {fl.get('elevation_m','N/A')} m<br>
          Seismic: <b>{qk.get('earthquake_label','N/A')}</b>
          <span class="muted">{(' PGA:'+str(qk['pga_g'])+'g') if qk.get('pga_g') else ''}</span>
        </div>"""

    info_panel = f"""
    <style>
      #info-panel {{
        position: fixed; top: 12px; right: 12px;
        width: 280px;
        background: rgba(255,255,255,0.97);
        border: 1px solid #cbd5e1;
        border-radius: 12px;
        padding: 14px 16px;
        font-family: Arial, sans-serif;
        font-size: 12.5px;
        line-height: 1.65;
        z-index: 9999;
        box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        max-height: 90vh;
        overflow-y: auto;
      }}
      #info-panel .panel-title {{
        font-size: 14px; font-weight: bold;
        border-bottom: 1px solid #e2e8f0;
        padding-bottom: 6px; margin-bottom: 10px;
      }}
      #info-panel .panel-section {{
        margin-bottom: 10px;
        padding-bottom: 10px;
        border-bottom: 1px solid #f1f5f9;
      }}
      #info-panel .section-title {{ font-weight: bold; margin-bottom: 3px; }}
      #info-panel .muted {{ color: #64748b; font-size: 11.5px; }}
      #info-panel .footer {{
        font-size: 10px; color: #94a3b8;
        margin-top: 6px; padding-top: 6px;
        border-top: 1px solid #e2e8f0;
      }}
    </style>
    <div id="info-panel">
      <div class="panel-title">📍 Location Intelligence</div>
      <div class="muted" style="margin-bottom:10px">
        {lat}, {lon} &nbsp;·&nbsp; radius: {dist} m
      </div>
      {road_html}{comp_html}{weather_html}{pop_html}{lu_html}{env_html}
      <div class="footer">Data: OSM · Open-Meteo · WorldPop · USGS · Open-Elevation</div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(info_panel))

    # ── 11. Legend (bottom-right) ─────────────────────────────
    dot  = lambda color: (f'<span style="display:inline-block;width:11px;height:11px;'
                          f'border-radius:50%;background:{color};margin-right:5px;vertical-align:middle"></span>')
    rect = lambda color: (f'<span style="display:inline-block;width:18px;height:5px;'
                          f'background:{color};margin-right:5px;vertical-align:middle"></span>')

    lm_rows   = "".join(f'<div>{dot(color)}{label}</div>'
                        for label, color in LANDMARK_COLORS.items() if label != "📍 Other")
    road_rows = "".join(f'<div>{rect(color)}{rtype.title()}</div>'
                        for rtype, color in list(ROAD_COLORS.items())[:6])
    iso_rows  = "".join(
        f'<div>{rect(ISOCHRONE_STYLES[t]["color"])}{t}-min drive</div>'
        for t in [5, 10, 15]
    )

    legend_html = f"""
    <style>
      #map-legend {{
        position: fixed; bottom: 30px; right: 12px;
        width: 185px;
        background: rgba(255,255,255,0.95);
        border: 1px solid #cbd5e1;
        border-radius: 10px;
        padding: 10px 13px;
        font-family: Arial, sans-serif;
        font-size: 11px; line-height: 1.85;
        z-index: 9998;
        box-shadow: 0 2px 10px rgba(0,0,0,0.12);
        max-height: 52vh;
        overflow-y: auto;
      }}
      #map-legend b {{ font-size: 11.5px; }}
    </style>
    <div id="map-legend">
      <b>Landmarks</b>
      {lm_rows}
      <div style="margin-top:6px">{dot('orange')}🏪 Competitor</div>
      <div>{dot('green')}🤝 Complementary</div>
      <div>{dot('darkpurple')}⚓ Anchor Tenant</div>
      <div>{dot('#0ea5e9')}💧 Water Feature</div>
      <div style="margin-top:8px"><b>Roads</b></div>
      {road_rows}
      <div style="margin-top:8px"><b>Isochrones</b></div>
      {iso_rows}
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    # ── 12. Layer control ─────────────────────────────────────
    folium.LayerControl(collapsed=False).add_to(m)

    return m


# ══════════════════════════════════════════════════════════════════
#  MAIN MENU
# ══════════════════════════════════════════════════════════════════

def print_banner():
    print(f"\n{'#'*65}")
    print(f"#{'':^63}#")
    print(f"#{'  📍 LOCATION INTELLIGENCE TOOL  v2':^63}#")
    print(f"#{'  Road · POI · Demographics · Zoning · Risk · Map':^63}#")
    print(f"#{'':^63}#")
    print(f"{'#'*65}\n")


def get_yes_no(prompt):
    while True:
        ans = input(prompt + " (y/n): ").strip().lower()
        if ans in ("y", "n", "yes", "no"):
            return ans in ("y", "yes")
        print("  Please enter y or n.")


def main():
    print_banner()

    print("─── SHARED INPUTS ───────────────────────────────────────")
    lat      = float(input("  Enter latitude                         : "))
    lon      = float(input("  Enter longitude                        : "))
    dist_str = input("  Enter radius in meters (default 2000)  : ").strip()
    dist     = int(dist_str) if dist_str else 2000

    print("\n─── SELECT MODULES TO RUN ───────────────────────────────")
    run_roads   = get_yes_no("  Run Road Network + Isochrones?      ")
    run_comp    = get_yes_no("  Run POI Analysis (comp/anchor/compl)?")
    run_weather = get_yes_no("  Run Weather + AQI Report?           ")
    run_pop     = get_yes_no("  Run Demographics (pop/income/age)?  ")
    run_landuse = get_yes_no("  Run Land Use & Zoning?              ")
    run_env     = get_yes_no("  Run Environmental & Risk Data?      ")

    business_type = None
    if run_comp:
        print(f"\n  Available business types:")
        for i, btype in enumerate(BUSINESS_TAGS.keys(), 1):
            print(f"    {i:>2}. {btype}")
        business_type = input("\n  Enter business type : ").strip().lower()

    start_date = end_date = None
    if run_weather:
        print("\n  Weather date range (AQI from 2022, weather from 1940)")
        start_date = input("  Enter start date (YYYY-MM-DD) : ").strip()
        end_date   = input("  Enter end date   (YYYY-MM-DD) : ").strip()

    radius_pixels = 5
    if run_pop:
        rp = input("\n  Population radius in pixels (default 5, 1 pixel ≈ 100m) : ").strip()
        radius_pixels = int(rp) if rp else 5

    # ── Run modules ───────────────────────────────────────────
    results = {}

    print(f"\n\n{'#'*65}")
    print(f"#{'  RUNNING ANALYSIS':^63}#")
    print(f"{'#'*65}")

    if run_roads:
        print(f"\n{'━'*65}")
        print(f"  MODULE 1 — ROAD NETWORK + ISOCHRONES")
        print(f"{'━'*65}")
        results["roads"] = get_road_score(lat, lon, dist)

    if run_comp:
        print(f"\n{'━'*65}")
        print(f"  MODULE 2 — POI ANALYSIS  (competitors / complementary / anchors)")
        print(f"{'━'*65}")
        results["competitors"] = get_competitors(lat, lon, business_type, dist)

    if run_weather:
        print(f"\n{'━'*65}")
        print(f"  MODULE 3 — WEATHER + AQI")
        print(f"{'━'*65}")
        results["weather"] = get_weather_aqi(lat, lon, start_date, end_date)

    if run_pop:
        print(f"\n{'━'*65}")
        print(f"  MODULE 4 — DEMOGRAPHICS  (population / income / age)")
        print(f"{'━'*65}")
        results["population"] = get_population(lat, lon, radius_pixels)

    if run_landuse:
        print(f"\n{'━'*65}")
        print(f"  MODULE 5 — LAND USE & ZONING")
        print(f"{'━'*65}")
        results["landuse"] = get_landuse_zoning(lat, lon, dist)

    if run_env:
        print(f"\n{'━'*65}")
        print(f"  MODULE 6 — ENVIRONMENTAL & RISK")
        print(f"{'━'*65}")
        results["environmental"] = get_environmental_risk(
            lat, lon, dist, weather_summary=results.get("weather")
        )

    # ── Summary ───────────────────────────────────────────────
    print(f"\n{'#'*65}")
    print(f"#{'  ✅ ALL DONE — SUMMARY':^63}#")
    print(f"{'#'*65}\n")

    if results.get("roads"):
        r = results["roads"]
        print(f"  Road Score   : {r.get('road_score_km','N/A')} km  |  {r.get('rating','N/A')}")
        print(f"  Road Density : {r.get('road_density_km_km2','N/A')} km/km²")

    if results.get("competitors"):
        c = results["competitors"]
        print(f"  Competitors  : {c.get('total_count',0)}  |  Complementary: "
              f"{len(c.get('complementary',[]))}  |  Anchors: {len(c.get('anchor_tenants',[]))}")
        print(f"  Competition  : {c.get('competition_level','N/A')}")

    if results.get("weather"):
        w = results["weather"]
        print(f"  Weather      : Avg {w.get('avg_temp','N/A')}°C  |  "
              f"AQI {w.get('avg_us_aqi','N/A')} ({w.get('aqi_label','N/A')})")

    if results.get("population"):
        p = results["population"]
        inc = p.get("income", {})
        age = p.get("age_distribution", {})
        print(f"  Population   : {p.get('population',0):,.0f}  |  "
              f"Density: {p.get('pop_density_km2',0):,.0f}/km²  |  {p.get('level','N/A')}")
        print(f"  Income       : {inc.get('income_label','N/A')}")
        print(f"  Age Group    : {age.get('dominant_age_group','N/A')}")

    if results.get("landuse"):
        lu = results["landuse"]
        print(f"  Land Use     : {lu.get('zone_label','N/A')}  |  "
              f"Buildings: {len(lu.get('building_features',[]))}")

    if results.get("environmental"):
        env = results["environmental"]
        print(f"  Flood Risk   : {env.get('flood',{}).get('flood_risk_score','N/A')}")
        print(f"  Seismic Risk : {env.get('earthquake',{}).get('earthquake_label','N/A')}")

    # ── Generate HTML Map ─────────────────────────────────────
    print(f"\n{'━'*65}")
    print(f"  GENERATING INTERACTIVE MAP...")
    print(f"{'━'*65}")
    try:
        fmap     = build_map(lat, lon, dist, results)
        map_file = "location_map.html"
        fmap.save(map_file)
        print(f"\n  ✅  Map saved  →  {map_file}")
        print(f"      Open in any browser — works offline, no server needed.\n")
        print(f"  Map layers available:")
        print(f"    🕐  Drive-time isochrones  (5 / 10 / 15 min)")
        print(f"    🛣  Road network            (colour-coded by type)")
        print(f"    📍  Landmarks")
        print(f"    🏪  Competitors / 🤝 Complementary / ⚓ Anchors")
        print(f"    🗺️  Land use / zoning")
        print(f"    🏗️  Building footprints")
        print(f"    💧  Flood / water features")
        print(f"    📊  Info panel  (top-right)")
        print(f"    🗂  Legend      (bottom-right)\n")
    except Exception as e:
        print(f"\n  ⚠️  Map generation failed: {e}\n")

    # ── Generate GeoJSON Export ───────────────────────────────
    print(f"{'━'*65}")
    print(f"  GENERATING GEOJSON EXPORT...")
    print(f"{'━'*65}")
    try:
        geojson_data = build_geojson(lat, lon, dist, results)
        geojson_file = "location_intelligence.geojson"
        with open(geojson_file, "w", encoding="utf-8") as f:
            json.dump(geojson_data, f, ensure_ascii=False, indent=2)
        feat_count = geojson_data["metadata"]["total_features"]
        print(f"\n  ✅  GeoJSON saved  →  {geojson_file}")
        print(f"      Total features : {feat_count}")
        print(f"      Layers encoded :")
        for layer in geojson_data["metadata"]["layers"]:
            count = sum(1 for f in geojson_data["features"]
                        if f["properties"].get("layer") == layer)
            if count:
                print(f"        · {layer:<35} {count} feature(s)")
        print(f"\n      Open in QGIS, ArcGIS, kepler.gl, or any GeoJSON viewer.\n")
    except Exception as e:
        print(f"\n  ⚠️  GeoJSON export failed: {e}\n")

    print()


if __name__ == "__main__":
    main()