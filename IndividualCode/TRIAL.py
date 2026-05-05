import osmnx as ox
import networkx as nx
import rasterio
import requests
import warnings
from collections import defaultdict
from rasterio.windows import Window
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")


# ══════════════════════════════════════════════════════════════════
#  SHARED UTILITIES
# ══════════════════════════════════════════════════════════════════

def safe_str(val):
    """Convert ANY column value to a safe string — handles lists, None, etc."""
    if val is None:
        return "unknown"
    if isinstance(val, list):
        return val[0] if val else "unknown"
    s = str(val)
    return "unknown" if s in ("nan", "None", "") else s


def safe_unique(series):
    """Get unique values from a series that may contain lists."""
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

        results.append({"label": label, "name": name,
                         "distance_m": round(road_dist, 1), "note": note})

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
        return None

    print(f"\nSearching for '{business_type}' competitors within {dist}m of ({lat}, {lon})...")

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
        print("No competitors found in this area.")
        return {"count": 0, "competitors": []}

    try:
        pois = pd.concat(all_dfs)
        pois = pois[~pois.index.duplicated(keep='first')]
    except Exception as e:
        print(f"Error combining results: {e}")
        return {"count": 0, "competitors": []}

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
        })

    competitors.sort(key=lambda x: (x["name"] == "Unnamed", x["name"]))

    category_count = {}
    for c in competitors:
        cat = c["category"]
        category_count[cat] = category_count.get(cat, 0) + 1

    named   = [c for c in competitors if c["name"] != "Unnamed"]
    unnamed = [c for c in competitors if c["name"] == "Unnamed"]

    print(f"\n{'='*60}")
    print(f"  COMPETITOR ANALYSIS REPORT")
    print(f"  Business Type : {business_type}")
    print(f"  Location      : ({lat}, {lon})")
    print(f"  Radius        : {dist} m")
    print(f"{'='*60}")

    print(f"\n--- Summary ---")
    print(f"  Total found    : {len(competitors)}")
    print(f"  Named          : {len(named)}")
    print(f"  Unnamed        : {len(unnamed)}  (POIs with no name tag on OSM)")

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

    print(f"\n--- Detailed Info (named, with contact/address) ---")
    has_detail = [c for c in named if any([c["address"], c["phone"], c["website"], c["hours"]])]
    if has_detail:
        for c in has_detail:
            print(f"\n  {c['name']}  [{c['category']}]")
            if c["address"] : print(f"    Address  : {c['address']}")
            if c["phone"]   : print(f"    Phone    : {c['phone']}")
            if c["website"] : print(f"    Website  : {c['website']}")
            if c["hours"]   : print(f"    Hours    : {c['hours']}")
            if c["cuisine"] : print(f"    Cuisine  : {c['cuisine']}")
            if c["brand"]   : print(f"    Brand    : {c['brand']}")
    else:
        print(f"  (No contact/address data available for this area on OSM)")

    total = len(competitors)
    level = (
        "Very High 🔴 — extremely saturated market" if total > 50 else
        "High 🟠      — strong competition"          if total > 20 else
        "Moderate 🟡  — some competition"            if total > 10 else
        "Low 🟢       — good opportunity"            if total > 3  else
        "Very Low ✅  — almost no competition"
    )
    print(f"\n--- Competition Level ---")
    print(f"  {level}")
    print(f"\n{'='*60}\n")

    return {
        "total_count"       : len(competitors),
        "named_count"       : len(named),
        "unnamed_count"     : len(unnamed),
        "competition_level" : level,
        "category_breakdown": category_count,
        "competitors"       : competitors,
        "named_list"        : [c["name"] for c in named],
    }


# ══════════════════════════════════════════════════════════════════
#  MODULE 3 — WEATHER + AQI
# ══════════════════════════════════════════════════════════════════

WEATHER_URL = "https://archive-api.open-meteo.com/v1/archive"
AQI_URL     = "https://air-quality-api.open-meteo.com/v1/air-quality"


def fetch_weather(lat, lon, start_date, end_date):
    params = {
        "latitude"   : lat,
        "longitude"  : lon,
        "start_date" : start_date,
        "end_date"   : end_date,
        "daily"      : ["temperature_2m_max", "temperature_2m_min", "temperature_2m_mean",
                        "precipitation_sum", "windspeed_10m_max",
                        "relative_humidity_2m_max", "relative_humidity_2m_min", "weathercode"],
        "timezone"        : "auto",
        "temperature_unit": "celsius",
        "windspeed_unit"  : "ms",
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
        "latitude"  : lat,
        "longitude" : lon,
        "start_date": start_date,
        "end_date"  : end_date,
        "hourly"    : ["pm10", "pm2_5", "carbon_monoxide", "nitrogen_dioxide",
                       "sulphur_dioxide", "ozone", "us_aqi", "us_aqi_pm2_5",
                       "us_aqi_pm10", "european_aqi", "dust", "uv_index"],
        "timezone"  : "auto",
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
            daily[date] = {k: [] for k in
                           ["us_aqi", "european_aqi", "pm2_5", "pm10",
                            "no2", "so2", "ozone", "co", "dust", "uv_index"]}

        field_map = {
            "us_aqi": "us_aqi", "european_aqi": "european_aqi",
            "pm2_5": "pm2_5", "pm10": "pm10",
            "no2": "nitrogen_dioxide", "so2": "sulphur_dioxide",
            "ozone": "ozone", "co": "carbon_monoxide",
            "dust": "dust", "uv_index": "uv_index",
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
    return                 "Hazardous ☠️"

def eu_aqi_label(aqi):
    if aqi is None: return "N/A"
    if aqi <= 20:   return "Good ✅"
    if aqi <= 40:   return "Fair 🟢"
    if aqi <= 60:   return "Moderate 🟡"
    if aqi <= 80:   return "Poor 🟠"
    if aqi <= 100:  return "Very Poor 🔴"
    return                 "Extremely Poor ☠️"

def weather_label(code):
    codes = {
        0: "Clear ☀️", 1: "Mainly clear 🌤️", 2: "Partly cloudy ⛅", 3: "Overcast ☁️",
        45: "Fog 🌫️", 48: "Icy fog 🌫️",
        51: "Light drizzle 🌦️", 53: "Drizzle 🌦️", 55: "Heavy drizzle 🌧️",
        61: "Light rain 🌧️", 63: "Rain 🌧️", 65: "Heavy rain 🌧️",
        71: "Light snow 🌨️", 73: "Snow 🌨️", 75: "Heavy snow ❄️",
        80: "Showers 🌦️", 81: "Heavy showers 🌧️", 82: "Violent showers ⛈️",
        95: "Thunderstorm ⛈️", 96: "Thunderstorm+hail ⛈️",
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
    print(f"  Weather + AQI Report  |  {start_date} → {end_date}  ({total} days)")
    print(f"  Location: {lat}, {lon}")
    print(f"{'='*70}")

    print("\n[Fetching weather data...]")
    weather = fetch_weather(lat, lon, start_date, end_date)
    print("[Fetching AQI data...]")
    aqi_hourly = fetch_aqi(lat, lon, start_date, end_date)

    if not weather or not aqi_hourly:
        print("Failed to fetch data.")
        return

    aqi_daily = aggregate_aqi_daily(aqi_hourly, set(dates))

    print(f"\n{'─'*70}")
    print(f"{'Date':<12} {'Condition':<20} {'Temp°C':>9} {'Rain mm':>8} {'Humidity%':>10} {'US AQI':>7} {'EU AQI':>7} {'PM2.5':>7} {'PM10':>6}")
    print(f"{'─'*70}")

    for i, date in enumerate(dates):
        wcode  = weather["weathercode"][i]
        tmax   = weather["temperature_2m_max"][i]
        tmin   = weather["temperature_2m_min"][i]
        tmean  = weather["temperature_2m_mean"][i]
        rain   = weather["precipitation_sum"][i]
        hmax   = weather["relative_humidity_2m_max"][i]
        hmin   = weather["relative_humidity_2m_min"][i]

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
        print(f"    Precipitation : {fmt(rain)} mm")
        print(f"    Humidity      : {fmt(hmin,decimals=0)}% – {fmt(hmax,decimals=0)}%")
        print(f"    Wind (max)    : {fmt(wind)} m/s")
        print(f"    US AQI        : {fmt(us,decimals=0)}  →  {us_aqi_label(us)}")
        print(f"    EU AQI        : {fmt(eu,decimals=0)}  →  {eu_aqi_label(eu)}")
        print(f"    PM2.5         : {fmt(aqi.get('pm2_5'))} μg/m³")
        print(f"    PM10          : {fmt(aqi.get('pm10'))} μg/m³")
        print(f"    NO₂           : {fmt(aqi.get('no2'))} μg/m³")
        print(f"    SO₂           : {fmt(aqi.get('so2'))} μg/m³")
        print(f"    Ozone         : {fmt(aqi.get('ozone'))} μg/m³")
        print(f"    CO            : {fmt(aqi.get('co'))} μg/m³")
        print(f"    Dust          : {fmt(aqi.get('dust'))} μg/m³")
        print(f"    UV Index      : {fmt(aqi.get('uv_index'))}")
        print(f"    {'─'*50}")

    us_vals   = [aqi_daily[d]["us_aqi"]       for d in dates if d in aqi_daily and aqi_daily[d]["us_aqi"]       is not None]
    eu_vals   = [aqi_daily[d]["european_aqi"] for d in dates if d in aqi_daily and aqi_daily[d]["european_aqi"] is not None]
    tmp_vals  = [weather["temperature_2m_mean"][i]  for i, d in enumerate(dates) if weather["temperature_2m_mean"][i]  is not None]
    rain_vals = [weather["precipitation_sum"][i]    for i, d in enumerate(dates) if weather["precipitation_sum"][i]    is not None]

    print(f"\n{'='*70}")
    print(f"  RANGE SUMMARY  ({total} days)")
    print(f"{'='*70}")
    if tmp_vals:
        print(f"  Avg Temperature   : {round(sum(tmp_vals)/len(tmp_vals),1)} °C")
        print(f"  Max Temperature   : {max(weather['temperature_2m_max'])} °C  on {dates[weather['temperature_2m_max'].index(max(weather['temperature_2m_max']))]}")
        print(f"  Min Temperature   : {min(weather['temperature_2m_min'])} °C  on {dates[weather['temperature_2m_min'].index(min(weather['temperature_2m_min']))]}")
    if rain_vals:
        print(f"  Total Rainfall    : {round(sum(rain_vals),1)} mm")
    if us_vals:
        avg_us = round(sum(us_vals)/len(us_vals), 1)
        print(f"  Avg US AQI        : {avg_us}  →  {us_aqi_label(avg_us)}")
        print(f"  Max US AQI        : {max(us_vals)}  (worst day)")
        print(f"  Min US AQI        : {min(us_vals)}  (best day)")
    if eu_vals:
        avg_eu = round(sum(eu_vals)/len(eu_vals), 1)
        print(f"  Avg EU AQI        : {avg_eu}  →  {eu_aqi_label(avg_eu)}")
    print(f"{'='*70}\n")


# ══════════════════════════════════════════════════════════════════
#  MODULE 4 — POPULATION ESTIMATE
# ══════════════════════════════════════════════════════════════════

WORLDPOP_FILE = "worldpop.tif"


def get_population(lat, lon, radius_pixels=5):
    """
    Get population for a given coordinate and radius.
    Each pixel ≈ 100m in WorldPop data.
    """
    try:
        with rasterio.open(WORLDPOP_FILE) as dataset:
            row, col = dataset.index(lon, lat)
            size     = radius_pixels * 2
            window   = Window(col - radius_pixels, row - radius_pixels, size, size)
            data     = dataset.read(1, window=window)
            pop      = float(data.sum())

        level = (
            "Very High 🔴 — Dense urban area"    if pop > 100_000 else
            "High 🟠      — Urban area"           if pop > 50_000  else
            "Moderate 🟡  — Semi-urban"           if pop > 10_000  else
            "Low 🟢       — Suburban / rural"     if pop > 1_000   else
            "Very Low ✅  — Sparse / remote"
        )

        radius_m = radius_pixels * 100

        print(f"\n{'='*50}")
        print(f"  POPULATION ESTIMATE")
        print(f"  Location : ({lat}, {lon})")
        print(f"  Radius   : ~{radius_m} m  ({radius_pixels} pixels)")
        print(f"{'='*50}")
        print(f"  Estimated Population : {pop:>12,.0f}")
        print(f"  Density Level        : {level}")
        print(f"{'='*50}\n")

        return pop

    except FileNotFoundError:
        print(f"\n  ⚠️  WorldPop file '{WORLDPOP_FILE}' not found.")
        print(f"      Download from: https://www.worldpop.org/geodata/listing?id=29")
        print(f"      Place the .tif file in the same folder as this script.\n")
        return 0.0
    except Exception as e:
        print(f"  Population error: {e}")
        return 0.0


# ══════════════════════════════════════════════════════════════════
#  MAIN MENU — Collect all inputs first, then run all modules
# ══════════════════════════════════════════════════════════════════

def print_banner():
    print(f"\n{'#'*65}")
    print(f"#{'':^63}#")
    print(f"#{'  📍 LOCATION INTELLIGENCE TOOL':^63}#")
    print(f"#{'  Road · Competition · Weather · Population':^63}#")
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

    # ── Shared inputs ──────────────────────────────────────────
    print("─── SHARED INPUTS ───────────────────────────────────────")
    lat  = float(input("  Enter latitude                         : "))
    lon  = float(input("  Enter longitude                        : "))
    dist_str = input("  Enter radius in meters (default 2000)  : ").strip()
    dist = int(dist_str) if dist_str else 2000

    # ── Module selections ──────────────────────────────────────
    print("\n─── SELECT MODULES TO RUN ───────────────────────────────")
    run_roads  = get_yes_no("  Run Road Network Analysis?          ")
    run_comp   = get_yes_no("  Run Competitor Analysis?            ")
    run_weather= get_yes_no("  Run Weather + AQI Report?           ")
    run_pop    = get_yes_no("  Run Population Estimate?            ")

    # ── Competitor-specific input ──────────────────────────────
    business_type = None
    if run_comp:
        print(f"\n  Available business types:")
        for i, btype in enumerate(BUSINESS_TAGS.keys(), 1):
            print(f"    {i:>2}. {btype}")
        business_type = input("\n  Enter business type : ").strip().lower()

    # ── Weather-specific inputs ────────────────────────────────
    start_date = end_date = None
    if run_weather:
        print("\n  Weather date range (data available from 2022 for AQI,")
        print("  1940 for weather. Dates must be in the past.)")
        start_date = input("  Enter start date (YYYY-MM-DD) : ").strip()
        end_date   = input("  Enter end date   (YYYY-MM-DD) : ").strip()

    # ── Population-specific input ──────────────────────────────
    radius_pixels = 5
    if run_pop:
        rp = input("\n  Population radius in pixels (default 5, 1 pixel ≈ 100m) : ").strip()
        radius_pixels = int(rp) if rp else 5

    # ══════════════════════════════════════════════════════════
    #  RUN SELECTED MODULES
    # ══════════════════════════════════════════════════════════
    results = {}

    print(f"\n\n{'#'*65}")
    print(f"#{'  RUNNING ANALYSIS':^63}#")
    print(f"{'#'*65}")

    if run_roads:
        print(f"\n{'━'*65}")
        print(f"  MODULE 1 / 4 — ROAD NETWORK ANALYSIS")
        print(f"{'━'*65}")
        results["roads"] = get_road_score(lat, lon, dist)

    if run_comp:
        print(f"\n{'━'*65}")
        print(f"  MODULE 2 / 4 — COMPETITOR ANALYSIS")
        print(f"{'━'*65}")
        results["competitors"] = get_competitors(lat, lon, business_type, dist)

    if run_weather:
        print(f"\n{'━'*65}")
        print(f"  MODULE 3 / 4 — WEATHER + AQI REPORT")
        print(f"{'━'*65}")
        get_weather_aqi(lat, lon, start_date, end_date)

    if run_pop:
        print(f"\n{'━'*65}")
        print(f"  MODULE 4 / 4 — POPULATION ESTIMATE")
        print(f"{'━'*65}")
        results["population"] = get_population(lat, lon, radius_pixels)

    # ── Final summary ──────────────────────────────────────────
    print(f"\n{'#'*65}")
    print(f"#{'  ✅ ALL DONE':^63}#")
    print(f"{'#'*65}\n")

    if "roads" in results and results["roads"]:
        r = results["roads"]
        print(f"  Road Score   : {r['road_score_km']} km  |  {r['rating']}")

    if "competitors" in results and results["competitors"]:
        c = results["competitors"]
        print(f"  Competition  : {c['total_count']} found  |  {c['competition_level']}")

    if "population" in results:
        print(f"  Population   : {results['population']:,.0f} (estimated within radius)")

    print()


# ─────────────────────────────────────────
if __name__ == "__main__":
    main()