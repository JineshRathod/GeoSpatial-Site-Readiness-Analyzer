import osmnx as ox
import networkx as nx
import warnings
from collections import defaultdict
warnings.filterwarnings("ignore")


def safe_str(val):
    """Convert ANY column value to a safe string — handles lists, None, etc."""
    if val is None:
        return "unknown"
    if isinstance(val, list):
        return val[0] if val else "unknown"
    return str(val)


def safe_unique(series):
    """Get unique values from a series that may contain lists."""
    seen = set()
    result = []
    for val in series:
        key = safe_str(val)
        if key not in seen:
            seen.add(key)
            result.append(key)
    return result


# ──────────────────────────────────────────────────────────────
#  LANDMARK DISTANCE FUNCTION
# ──────────────────────────────────────────────────────────────
def get_landmark_distances(lat, lon, G_proj, dist):
    import math
    from pyproj import Transformer

    transformer = Transformer.from_crs("epsg:4326", G_proj.graph["crs"], always_xy=True)

    def to_proj(lon_, lat_):
        return transformer.transform(lon_, lat_)

    def haversine(lat1, lon1, lat2, lon2):
        R = 6_371_000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi       = math.radians(lat2 - lat1)
        dlam       = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # ── Single batch query — all tags at once (much faster) ──
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

    # Project origin point
    ox_x, ox_y  = to_proj(lon, lat)
    origin_node = ox.nearest_nodes(G_proj, ox_x, ox_y)

    gdf           = gdf.copy()
    gdf["_centroid"] = gdf.geometry.centroid
    gdf["_lat"]   = gdf["_centroid"].y
    gdf["_lon"]   = gdf["_centroid"].x

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
        poi_lat  = row["_lat"]
        poi_lon  = row["_lon"]
        label    = get_label(row)
        name     = get_name(row)

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
            "distance_m": round(road_dist, 1),
            "note"      : note
        })

    # ── Group by label, show closest 2 per type ──
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


# ──────────────────────────────────────────────────────────────
#  MAIN ROAD SCORE FUNCTION
# ──────────────────────────────────────────────────────────────
def get_road_score(lat, lon, dist=2000):
    print(f"\nFetching road network within {dist}m of ({lat}, {lon})...")

    # ── Download & project ──
    G      = ox.graph_from_point((lat, lon), dist=dist, network_type='drive')
    G_proj = ox.project_graph(G)
    nodes, edges = ox.graph_to_gdfs(G_proj)
    edges  = edges.copy()

    # ── Sanitize ALL columns that may contain lists ──
    for col in edges.columns:
        if edges[col].dtype == object:
            edges[col] = edges[col].apply(safe_str)

    # ── Measurements ──
    total_edges     = len(edges)
    total_nodes     = len(nodes)
    total_length_m  = edges.length.sum()
    total_length_km = total_length_m / 1000
    dead_ends       = sum(1 for n in G.nodes() if G.degree(n) == 1)
    intersections   = sum(1 for n in G.nodes() if G.degree(n) >= 3)
    oneway_count    = int(edges["oneway"].apply(lambda x: x == "True").sum()) if "oneway" in edges.columns else 0
    twoway_count    = total_edges - oneway_count

    # ── Road types ──
    road_types     = {}
    length_by_type = {}
    if "highway" in edges.columns:
        for rtype, group in edges.groupby("highway"):
            road_types[rtype]     = len(group)
            length_by_type[rtype] = group.length.sum()

    # ── Named roads ──
    named_roads = []
    if "name" in edges.columns:
        for val in edges["name"].unique():
            if val not in ("unknown", "nan", "None"):
                named_roads.append(val)
    named_roads = sorted(set(named_roads))

    # ── Rating ──
    rating = (
        "Excellent ✅  (city center / commercial hub)" if total_length_km > 100 else
        "Good 🟢      (well connected area)"           if total_length_km > 60  else
        "Moderate 🟡  (average connectivity)"          if total_length_km > 30  else
        "Low 🔴       (poor road access)"
    )

    # ══════════════════════════════════════════
    #  REPORT
    # ══════════════════════════════════════════
    print(f"\n{'='*55}")
    print(f"  ROAD NETWORK REPORT")
    print(f"  Location : ({lat}, {lon})")
    print(f"  Radius   : {dist} m")
    print(f"{'='*55}")

    print(f"\n--- Core Score ---")
    print(f"  Total Road Length  : {total_length_m:>10,.1f} m")
    print(f"                     : {total_length_km:>10.2f} km")
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

    # ── Landmark distances (uses projected graph — no scikit-learn needed) ──
    get_landmark_distances(lat, lon, G_proj, dist)

    print(f"\n{'='*55}\n")

    return {
        "road_score_m"      : round(total_length_m, 1),
        "road_score_km"     : round(total_length_km, 2),
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
    }


# ─────────────────────────────────────────
if __name__ == "__main__":
    lat  = float(input("Enter latitude  : "))
    lon  = float(input("Enter longitude : "))
    dist = input("Enter radius in meters (default 2000): ").strip()
    dist = int(dist) if dist else 2000

    get_road_score(lat, lon, dist)