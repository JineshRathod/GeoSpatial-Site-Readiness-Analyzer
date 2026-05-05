import osmnx as ox
import networkx as nx
import rasterio
import requests
import folium
import warnings
from collections import defaultdict
from rasterio.windows import Window
from datetime import datetime, timedelta
from folium.plugins import MarkerCluster

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


# ══════════════════════════════════════════════════════════════════
#  MODULE 1 — ROAD NETWORK ANALYSIS
# ══════════════════════════════════════════════════════════════════

def get_landmark_distances(lat, lon, G_proj, dist):
    import math
    from pyproj import Transformer

    transformer = Transformer.from_crs("epsg:4326", G_proj.graph["crs"], always_xy=True)

    def to_proj(lon_, lat_):
        return transformer.transform(lon_, lat_)

    def haversine(lat1, lon1, lat2, lon2):
        R = 6_371_000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

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
    dead_ends       = sum(1 for n in G.nodes() if G.degree(n) == 1)
    intersections   = sum(1 for n in G.nodes() if G.degree(n) >= 3)
    oneway_count    = int(edges["oneway"].apply(lambda x: x == "True").sum()) if "oneway" in edges.columns else 0
    twoway_count    = total_edges - oneway_count

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
        "landmarks"         : landmarks,
        "edges_gdf"         : edges,
        "nodes_gdf"         : nodes,
    }


# ══════════════════════════════════════════════════════════════════
#  MODULE 2 — COMPETITOR ANALYSIS
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

# ── Always-safe empty competitor result ─────────────────────────
def _empty_comp(business_type):
    return {
        "total_count"       : 0,
        "named_count"       : 0,
        "unnamed_count"     : 0,
        "competition_level" : "Very Low ✅  — almost no competition",
        "category_breakdown": {},
        "competitors"       : [],
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


def get_competitors(lat, lon, business_type, dist=2000):
    import pandas as pd

    tags = BUSINESS_TAGS.get(business_type.lower())
    if not tags:
        print(f"\n❌ Unknown business type: '{business_type}'")
        print(f"   Available types: {', '.join(BUSINESS_TAGS.keys())}")
        return _empty_comp(business_type)

    print(f"\nSearching for '{business_type}' competitors within {dist}m...")

    all_dfs = []
    for key, values in tags.items():
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
        print("  No competitors found in this area.")
        return _empty_comp(business_type)

    try:
        pois = pd.concat(all_dfs)
        pois = pois[~pois.index.duplicated(keep='first')]
    except Exception as e:
        print(f"  Error combining results: {e}")
        return _empty_comp(business_type)

    competitors = []
    for _, row in pois.iterrows():
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
        address    = ", ".join(addr_parts) if addr_parts else None
        category   = amenity or shop or tourism or leisure or "unknown"

        competitors.append({
            "name"    : name or "Unnamed",
            "category": category,
            "brand"   : brand,
            "cuisine" : cuisine,
            "address" : address,
            "phone"   : phone,
            "website" : website,
            "hours"   : hours,
            "lat"     : c_lat,
            "lon"     : c_lon,
        })

    competitors.sort(key=lambda x: (x["name"] == "Unnamed", x["name"]))

    category_count = {}
    for c in competitors:
        cat = c["category"]
        category_count[cat] = category_count.get(cat, 0) + 1

    named   = [c for c in competitors if c["name"] != "Unnamed"]
    unnamed = [c for c in competitors if c["name"] == "Unnamed"]

    print(f"\n{'='*60}")
    print(f"  COMPETITOR ANALYSIS — {business_type}")
    print(f"{'='*60}")
    print(f"  Total: {len(competitors)}  |  Named: {len(named)}  |  Unnamed: {len(unnamed)}")
    print(f"\n--- By Category ---")
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
            if c["hours"]  : extra_parts.append(f"hours: {c['hours']}")
            extra = " | ".join(extra_parts) if extra_parts else ""
            print(f"  {i:<4} {c['name']:<30} {c['category']:<18} {extra}")
    print(f"\n--- Detailed Info ---")
    has_detail = [c for c in named if any([c["address"], c["phone"], c["website"], c["hours"]])]
    if has_detail:
        for c in has_detail:
            print(f"\n  {c['name']}  [{c['category']}]")
            if c["address"] : print(f"    Address : {c['address']}")
            if c["phone"]   : print(f"    Phone   : {c['phone']}")
            if c["website"] : print(f"    Website : {c['website']}")
            if c["hours"]   : print(f"    Hours   : {c['hours']}")
    else:
        print(f"  (No contact/address data available on OSM)")

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

def fmt(v, unit="", decimals=1):
    return f"{round(v, decimals)}{unit}" if v is not None else "N/A"

def date_range(start_str, end_str):
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end   = datetime.strptime(end_str,   "%Y-%m-%d")
    return [(start + timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range((end - start).days + 1)]


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

    print(f"\n\n{'='*70}")
    print(f"  DETAILED DAILY BREAKDOWN")
    print(f"{'='*70}")
    for i, date in enumerate(dates):
        aqi   = aqi_daily.get(date, {})
        wcode = weather["weathercode"][i]
        tmax  = weather["temperature_2m_max"][i]
        tmin  = weather["temperature_2m_min"][i]
        wind  = weather["windspeed_10m_max"][i]
        rain  = weather["precipitation_sum"][i]
        hmax  = weather["relative_humidity_2m_max"][i]
        hmin  = weather["relative_humidity_2m_min"][i]
        us    = aqi.get("us_aqi")
        eu    = aqi.get("european_aqi")
        print(f"\n  [{date}]  {weather_label(wcode)}")
        print(f"    Temperature   : {fmt(tmin)}°C – {fmt(tmax)}°C  (mean: {fmt(weather['temperature_2m_mean'][i])}°C)")
        print(f"    Precipitation : {fmt(rain)} mm  |  Wind: {fmt(wind)} m/s")
        print(f"    Humidity      : {fmt(hmin,decimals=0)}% – {fmt(hmax,decimals=0)}%")
        print(f"    US AQI        : {fmt(us,decimals=0)}  →  {us_aqi_label(us)}")
        print(f"    EU AQI        : {fmt(eu,decimals=0)}  →  {eu_aqi_label(eu)}")
        print(f"    PM2.5 / PM10  : {fmt(aqi.get('pm2_5'))} / {fmt(aqi.get('pm10'))} μg/m³")
        print(f"    NO₂ / SO₂     : {fmt(aqi.get('no2'))} / {fmt(aqi.get('so2'))} μg/m³")
        print(f"    Ozone / CO    : {fmt(aqi.get('ozone'))} / {fmt(aqi.get('co'))} μg/m³")
        print(f"    Dust / UV     : {fmt(aqi.get('dust'))} μg/m³  /  UV {fmt(aqi.get('uv_index'))}")
        print(f"    {'─'*50}")

    us_vals   = [aqi_daily[d]["us_aqi"]       for d in dates if d in aqi_daily and aqi_daily[d]["us_aqi"]       is not None]
    eu_vals   = [aqi_daily[d]["european_aqi"] for d in dates if d in aqi_daily and aqi_daily[d]["european_aqi"] is not None]
    tmp_vals  = [weather["temperature_2m_mean"][i]  for i, d in enumerate(dates) if weather["temperature_2m_mean"][i]  is not None]
    rain_vals = [weather["precipitation_sum"][i]    for i, d in enumerate(dates) if weather["precipitation_sum"][i]    is not None]

    print(f"\n{'='*70}")
    print(f"  RANGE SUMMARY  ({total} days)")
    print(f"{'='*70}")
    if tmp_vals:
        print(f"  Avg Temperature : {round(sum(tmp_vals)/len(tmp_vals),1)} °C")
        print(f"  Max Temperature : {max(weather['temperature_2m_max'])} °C  on {dates[weather['temperature_2m_max'].index(max(weather['temperature_2m_max']))]}")
        print(f"  Min Temperature : {min(weather['temperature_2m_min'])} °C  on {dates[weather['temperature_2m_min'].index(min(weather['temperature_2m_min']))]}")
    if rain_vals:
        print(f"  Total Rainfall  : {round(sum(rain_vals),1)} mm")
    if us_vals:
        avg_us = round(sum(us_vals)/len(us_vals), 1)
        print(f"  Avg US AQI      : {avg_us}  →  {us_aqi_label(avg_us)}")
        print(f"  Max/Min US AQI  : {max(us_vals)} / {min(us_vals)}")
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
    return summary


# ══════════════════════════════════════════════════════════════════
#  MODULE 4 — POPULATION ESTIMATE
# ══════════════════════════════════════════════════════════════════

WORLDPOP_FILE = "worldpop.tif"


def get_population(lat, lon, radius_pixels=5):
    try:
        with rasterio.open(WORLDPOP_FILE) as dataset:
            row, col = dataset.index(lon, lat)
            size     = radius_pixels * 2
            window   = Window(col - radius_pixels, row - radius_pixels, size, size)
            data     = dataset.read(1, window=window)
            pop      = float(data.sum())

        level = (
            "Very High 🔴 — Dense urban" if pop > 100_000 else
            "High 🟠 — Urban"            if pop > 50_000  else
            "Moderate 🟡 — Semi-urban"   if pop > 10_000  else
            "Low 🟢 — Suburban/rural"    if pop > 1_000   else
            "Very Low ✅ — Sparse"
        )
        radius_m = radius_pixels * 100
        print(f"\n{'='*50}")
        print(f"  POPULATION ESTIMATE  |  Radius: ~{radius_m} m")
        print(f"  Estimated : {pop:,.0f}")
        print(f"  Level     : {level}")
        print(f"{'='*50}\n")
        return {"population": pop, "level": level, "radius_m": radius_m}

    except FileNotFoundError:
        print(f"\n  ⚠️  WorldPop file '{WORLDPOP_FILE}' not found.")
        print(f"      Download: https://www.worldpop.org/geodata/listing?id=29\n")
        return {"population": 0, "level": "N/A — file not found", "radius_m": radius_pixels * 100}
    except Exception as e:
        print(f"  Population error: {e}")
        return {"population": 0, "level": "Error", "radius_m": radius_pixels * 100}


# ══════════════════════════════════════════════════════════════════
#  MODULE 5 — INTERACTIVE MAP  (Folium)
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

    # ── 3. Road network overlay ──────────────────────────────
    road_data = results.get("roads")
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

    # ── 4. Landmark markers (clustered) ─────────────────────
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
            popup_html = (
                f"<b>{lm['label']}</b><br>"
                f"<b>{lm['name']}</b><br>"
                f"Distance: <b>{d_str}</b><br>"
                f"Via: {lm['note']}"
            )
            folium.Marker(
                location=[lm["lat"], lm["lon"]],
                tooltip=f"{lm['label']} — {lm['name']} ({d_str})",
                popup=folium.Popup(popup_html, max_width=260),
                icon=folium.Icon(color=color, icon="info-sign"),
            ).add_to(lm_cluster)
        lm_layer.add_to(m)

    # ── 5. Competitor markers (clustered) ────────────────────
    comp_data = results.get("competitors")
    # Only draw markers if there are actual competitors with coordinates
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

    # ── 6. Info panel (top-right) ────────────────────────────
    road_html = comp_html = weather_html = pop_html = ""

    if road_data:
        road_html = f"""
        <div class="panel-section">
          <div class="section-title" style="color:#1d4ed8">🛣 Road Network</div>
          <b>{road_data['road_score_km']} km</b> total road length<br>
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
        comp_html = f"""
        <div class="panel-section">
          <div class="section-title" style="color:#d97706">🏪 Competitors</div>
          Business: <b>{btype_c}</b><br>
          Total: <b>{total_c}</b> &nbsp;·&nbsp; Named: {named_c}<br>
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
        pop_html = f"""
        <div class="panel-section">
          <div class="section-title" style="color:#7c3aed">👥 Population</div>
          Estimated: <b>{pop_s['population']:,.0f}</b><br>
          <span class="muted">{pop_s['level']}<br>Radius: {pop_s['radius_m']} m</span>
        </div>"""

    info_panel = f"""
    <style>
      #info-panel {{
        position: fixed; top: 12px; right: 12px;
        width: 275px;
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
      {road_html}{comp_html}{weather_html}{pop_html}
      <div class="footer">Data: OpenStreetMap · Open-Meteo · WorldPop</div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(info_panel))

    # ── 7. Legend (bottom-right) ─────────────────────────────
    dot  = lambda color: (f'<span style="display:inline-block;width:11px;height:11px;'
                          f'border-radius:50%;background:{color};margin-right:5px;vertical-align:middle"></span>')
    rect = lambda color: (f'<span style="display:inline-block;width:18px;height:5px;'
                          f'background:{color};margin-right:5px;vertical-align:middle"></span>')

    lm_rows   = "".join(f'<div>{dot(color)}{label}</div>'
                        for label, color in LANDMARK_COLORS.items() if label != "📍 Other")
    road_rows = "".join(f'<div>{rect(color)}{rtype.title()}</div>'
                        for rtype, color in list(ROAD_COLORS.items())[:6])

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
      <div style="margin-top:8px"><b>Roads</b></div>
      {road_rows}
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    # ── 8. Layer control ─────────────────────────────────────
    folium.LayerControl(collapsed=False).add_to(m)

    return m


# ══════════════════════════════════════════════════════════════════
#  MAIN MENU
# ══════════════════════════════════════════════════════════════════

def print_banner():
    print(f"\n{'#'*65}")
    print(f"#{'':^63}#")
    print(f"#{'  📍 LOCATION INTELLIGENCE TOOL':^63}#")
    print(f"#{'  Road · Competition · Weather · Population · Map':^63}#")
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
    run_roads   = get_yes_no("  Run Road Network Analysis?          ")
    run_comp    = get_yes_no("  Run Competitor Analysis?            ")
    run_weather = get_yes_no("  Run Weather + AQI Report?           ")
    run_pop     = get_yes_no("  Run Population Estimate?            ")

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
        print(f"  MODULE 1/4 — ROAD NETWORK ANALYSIS")
        print(f"{'━'*65}")
        results["roads"] = get_road_score(lat, lon, dist)

    if run_comp:
        print(f"\n{'━'*65}")
        print(f"  MODULE 2/4 — COMPETITOR ANALYSIS")
        print(f"{'━'*65}")
        results["competitors"] = get_competitors(lat, lon, business_type, dist)

    if run_weather:
        print(f"\n{'━'*65}")
        print(f"  MODULE 3/4 — WEATHER + AQI REPORT")
        print(f"{'━'*65}")
        results["weather"] = get_weather_aqi(lat, lon, start_date, end_date)

    if run_pop:
        print(f"\n{'━'*65}")
        print(f"  MODULE 4/4 — POPULATION ESTIMATE")
        print(f"{'━'*65}")
        results["population"] = get_population(lat, lon, radius_pixels)

    # ── Summary — fully safe .get() access everywhere ─────────
    print(f"\n{'#'*65}")
    print(f"#{'  ✅ ALL DONE — SUMMARY':^63}#")
    print(f"{'#'*65}\n")

    if results.get("roads"):
        r = results["roads"]
        print(f"  Road Score   : {r.get('road_score_km','N/A')} km  |  {r.get('rating','N/A')}")

    if results.get("competitors"):
        c = results["competitors"]
        total_c = c.get("total_count", 0)
        level_c = c.get("competition_level", "N/A")
        btype_c = c.get("business_type", "")
        if total_c > 0:
            print(f"  Competition  : {total_c} found ({btype_c})  |  {level_c}")
        else:
            print(f"  Competition  : None found ({btype_c}) — {level_c}")

    if results.get("weather"):
        w = results["weather"]
        print(f"  Weather      : Avg {w.get('avg_temp','N/A')}°C  |  "
              f"AQI {w.get('avg_us_aqi','N/A')} ({w.get('aqi_label','N/A')})")

    if results.get("population"):
        p = results["population"]
        print(f"  Population   : {p.get('population',0):,.0f}  |  {p.get('level','N/A')}")

    # ── Generate map ──────────────────────────────────────────
    print(f"\n{'━'*65}")
    print(f"  GENERATING INTERACTIVE MAP...")
    print(f"{'━'*65}")
    try:
        fmap     = build_map(lat, lon, dist, results)
        map_file = "location_map.html"
        fmap.save(map_file)
        print(f"\n  ✅  Map saved  →  {map_file}")
        print(f"      Open in any browser — works offline, no server needed.\n")
        print(f"  Map layers:")
        print(f"    🛣  Road network  (colour-coded by road type)")
        if results.get("roads", {}).get("landmarks"):
            print(f"    📍  Landmarks    (bus stops, hospitals, banks, etc.)")
        c = results.get("competitors", {})
        if c.get("total_count", 0) > 0:
            print(f"    🏪  Competitors  ({c.get('business_type','')})")
        print(f"    📊  Info panel   (top-right corner)")
        print(f"    🗂  Legend       (bottom-right corner)\n")
    except Exception as e:
        print(f"\n  ⚠️  Map generation failed: {e}\n")

    print()


if __name__ == "__main__":
    main()