import requests
import json
import time
import webbrowser
import os
from collections import defaultdict

# ─────────────────────────────────────────────
#  CONFIGURATION — fill these in before running
# ─────────────────────────────────────────────
API_KEY    = "q4YyJBEO6pok33P8dM261aNb8Jg1cRcn9T5KW9a4"   # <-- paste your Ola Maps API key here
LATITUDE   = 23.0009              # centre point latitude
LONGITUDE  = 72.5065              # centre point longitude
RADIUS     = 2000                 # search radius in metres
# ─────────────────────────────────────────────

# Rate-limit settings
DELAY_BETWEEN_REQUESTS = 0.8   # seconds between every request
MAX_RETRIES            = 5     # retries on 429 before giving up
RETRY_BACKOFF          = 5     # seconds to wait on first 429 (doubles each retry)

BASE_URL = "https://api.olamaps.io/places/v1/nearbysearch"

ALL_TYPES = [
    "accounting", "airport", "amusement_park", "aquarium", "art_gallery",
    "atm", "bakery", "bank", "bar", "beauty_salon", "bicycle_store",
    "book_store", "bowling_alley", "bus_station", "cafe", "campground",
    "car_dealer", "car_rental", "car_repair", "car_wash", "casino",
    "cemetery", "church", "city_hall", "clothing_store", "convenience_store",
    "courthouse", "dentist", "department_store", "doctor", "drugstore",
    "electrician", "electronics_store", "embassy", "fire_station",
    "florist", "funeral_home", "furniture_store", "gas_station", "gym",
    "hair_care", "hardware_store", "hindu_temple", "home_goods_store",
    "hospital", "insurance_agency", "jewelry_store", "laundry",
    "lawyer", "library", "light_rail_station", "liquor_store",
    "local_government_office", "locksmith", "lodging", "meal_delivery",
    "meal_takeaway", "mosque", "movie_rental", "movie_theater",
    "moving_company", "museum", "night_club", "painter", "park",
    "parking", "pet_store", "pharmacy", "physiotherapist", "plumber",
    "police", "post_office", "primary_school", "real_estate_agency",
    "restaurant", "roofing_contractor", "rv_park", "school",
    "secondary_school", "shoe_store", "shopping_mall", "spa",
    "stadium", "storage", "store", "subway_station", "supermarket",
    "synagogue", "taxi_stand", "tourist_attraction", "train_station",
    "transit_station", "travel_agency", "university", "veterinary_care",
    "zoo",
]


# ── API helpers ────────────────────────────────────────────────────────────

def fetch_places_for_type(place_type: str) -> list:
    params = {
        "location": f"{LATITUDE},{LONGITUDE}",
        "radius":   RADIUS,
        "types":    place_type,
        "api_key":  API_KEY,
    }
    wait = RETRY_BACKOFF
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(BASE_URL, params=params, timeout=10)
            if resp.status_code == 429:
                print(
                    f"\n    ⚠  429 rate-limited (attempt {attempt}/{MAX_RETRIES})"
                    f" — waiting {wait}s …", end=" ", flush=True
                )
                time.sleep(wait)
                wait *= 2          # exponential back-off
                continue
            resp.raise_for_status()
            data = resp.json()
            return data.get("predictions") or data.get("results") or []
        except requests.exceptions.HTTPError as e:
            print(f"\n  [HTTP error for type '{place_type}'] {e}")
            break
        except requests.exceptions.RequestException as e:
            print(f"\n  [Request error for type '{place_type}'] {e}")
            break
        except json.JSONDecodeError:
            print(f"\n  [Bad JSON for type '{place_type}']")
            break
    return []


# ── Place field extractors ─────────────────────────────────────────────────

def get_place_key(place: dict) -> str:
    return (
        place.get("place_id")
        or place.get("id")
        or get_name(place) + str(place.get("geometry", ""))
    )


def get_name(place: dict) -> str:
    return (
        place.get("name")
        or place.get("structured_formatting", {}).get("main_text")
        or place.get("description")
        or "Unknown"
    )


def get_address(place: dict) -> str:
    return (
        place.get("vicinity")
        or place.get("formatted_address")
        or place.get("structured_formatting", {}).get("secondary_text")
        or "—"
    )


def get_types(place: dict) -> str:
    raw = place.get("types") or place.get("type") or []
    if isinstance(raw, str):
        raw = [raw]
    return ", ".join(raw) if raw else "—"


def get_primary_type(place: dict) -> str:
    raw = place.get("types") or place.get("type") or []
    if isinstance(raw, str):
        return raw
    return raw[0] if raw else "unknown"


def get_coords(place: dict):
    """Return (lat, lng) tuple or None."""
    geo = place.get("geometry", {})
    loc = geo.get("location", {})
    lat = loc.get("lat")
    lng = loc.get("lng")
    if lat is not None and lng is not None:
        return float(lat), float(lng)
    # fallback flat fields
    lat = place.get("lat") or place.get("latitude")
    lng = place.get("lng") or place.get("longitude")
    if lat is not None and lng is not None:
        return float(lat), float(lng)
    return None


# ── Map builder (pure Leaflet.js — zero extra dependencies) ───────────────

def build_map_html(places: list, type_colour_map: dict) -> str:
    markers_js_lines = []
    for place in places:
        coords = get_coords(place)
        if coords is None:
            continue
        lat, lng = coords
        name    = get_name(place).replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
        address = get_address(place).replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
        types   = get_types(place).replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
        ptype   = get_primary_type(place)
        colour  = type_colour_map.get(ptype, "#3388ff")

        popup = (
            f"<div style='font-family:Arial,sans-serif;min-width:180px'>"
            f"<b style='font-size:13px'>{name}</b><br>"
            f"<span style='color:#e65c00;font-size:11px'>{types}</span><br>"
            f"<span style='color:#555;font-size:11px'>{address}</span>"
            f"</div>"
        )
        markers_js_lines.append(
            f"L.circleMarker([{lat},{lng}],{{radius:7,fillColor:'{colour}',"
            f"color:'#333',weight:1,opacity:1,fillOpacity:0.85}})"
            f".addTo(map).bindPopup('{popup}');"
        )

    legend_html = "".join(
        f"<div style='display:flex;align-items:center;gap:6px;margin:3px 0'>"
        f"<span style='width:11px;height:11px;border-radius:50%;"
        f"background:{c};border:1px solid #555;flex-shrink:0'></span>"
        f"<span style='font-size:11px'>{t}</span></div>"
        for t, c in sorted(type_colour_map.items())
    )

    plotted   = len(markers_js_lines)
    markers_block = "\n  ".join(markers_js_lines)

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Ola Maps — Nearby Places ({plotted} plotted)</title>
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{font-family:Arial,sans-serif}}
    #map{{height:100vh;width:100%}}
    .panel{{
      position:absolute;z-index:1000;
      background:rgba(255,255,255,0.96);
      border-radius:8px;
      box-shadow:0 2px 12px rgba(0,0,0,0.22);
      padding:12px 14px;
    }}
    #info{{top:10px;left:10px;max-width:210px}}
    #info h3{{font-size:14px;margin-bottom:4px}}
    #info p{{font-size:12px;color:#555;line-height:1.5}}
    #legend{{bottom:30px;right:10px;max-height:55vh;overflow-y:auto;max-width:195px}}
    #legend h4{{font-size:13px;margin-bottom:6px}}
  </style>
</head>
<body>
<div id="map"></div>
<div class="panel" id="info">
  <h3>📍 Nearby Places</h3>
  <p>
    <b>Centre:</b> {LATITUDE}, {LONGITUDE}<br>
    <b>Radius:</b> {RADIUS} m<br>
    <b>Plotted:</b> {plotted} places
  </p>
  <p style="margin-top:6px;font-size:10px;color:#999">Click any dot for details</p>
</div>
<div class="panel" id="legend">
  <h4>🏷 Category</h4>
  {legend_html}
</div>
<script>
  var map = L.map('map').setView([{LATITUDE},{LONGITUDE}],15);
  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{
    attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  }}).addTo(map);

  // Search-radius ring
  L.circle([{LATITUDE},{LONGITUDE}],{{
    radius:{RADIUS},color:'#3388ff',fillColor:'#3388ff',
    fillOpacity:0.05,weight:1.5,dashArray:'6,4'
  }}).addTo(map);

  // Centre pin
  L.circleMarker([{LATITUDE},{LONGITUDE}],{{
    radius:9,fillColor:'#FFD700',color:'#333',weight:2,fillOpacity:1
  }}).addTo(map).bindPopup('<b>📍 Search Centre</b>');

  // Place markers
  {markers_block}
</script>
</body>
</html>"""


# ── main ───────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*65}")
    print(f"  Ola Maps — Nearby Places Fetcher")
    print(f"  Centre : {LATITUDE}, {LONGITUDE}")
    print(f"  Radius : {RADIUS} m")
    print(f"  Delay  : {DELAY_BETWEEN_REQUESTS}s between requests (rate-limit safe)")
    print(f"{'='*65}\n")

    seen_keys: set       = set()
    all_places: list     = []
    by_type: defaultdict = defaultdict(list)

    total = len(ALL_TYPES)
    for i, place_type in enumerate(ALL_TYPES, 1):
        print(f"[{i:>3}/{total}] Fetching '{place_type}' …", end=" ", flush=True)
        results = fetch_places_for_type(place_type)

        new_count = 0
        for place in results:
            key = get_place_key(place)
            if key not in seen_keys:
                seen_keys.add(key)
                all_places.append(place)
                for t in (place.get("types") or [place_type]):
                    by_type[t].append(place)
                new_count += 1

        print(f"{len(results)} returned, {new_count} new")
        time.sleep(DELAY_BETWEEN_REQUESTS)

    # ── Console table ────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  TOTAL UNIQUE PLACES FOUND : {len(all_places)}")
    print(f"{'='*65}\n")

    if not all_places:
        print("No places found. Check your API key, coordinates, and radius.")
        return

    all_places.sort(key=lambda p: get_name(p).lower())

    W = (5, 35, 35, 50)
    hdr = f"{'#':<{W[0]}} {'NAME':<{W[1]}} {'TYPE(S)':<{W[2]}} {'ADDRESS':<{W[3]}}"
    print(hdr)
    print("-" * len(hdr))
    for idx, place in enumerate(all_places, 1):
        print(
            f"{idx:<{W[0]}} "
            f"{get_name(place)[:W[1]]:<{W[1]}} "
            f"{get_types(place)[:W[2]]:<{W[2]}} "
            f"{get_address(place)[:W[3]]:<{W[3]}}"
        )

    # ── Category breakdown ───────────────────────────────────────────
    print(f"\n{'='*65}")
    print("  BREAKDOWN BY CATEGORY")
    print(f"{'='*65}")
    for cat, ps in sorted(by_type.items(), key=lambda x: -len(x[1])):
        bar = "█" * min(len(ps), 40)
        print(f"  {cat:<38} {len(ps):>4}  {bar}")

    # ── Save JSON ────────────────────────────────────────────────────
    json_path = "ola_places_output.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_places, f, ensure_ascii=False, indent=2)
    print(f"\n  ✔  Raw data  → {json_path}")

    # ── Build and open map ───────────────────────────────────────────
    all_primary_types = sorted({get_primary_type(p) for p in all_places})
    palette = [
        "#e6194b","#3cb44b","#4363d8","#f58231","#911eb4",
        "#42d4f4","#f032e6","#bfef45","#469990","#dcbeff",
        "#9A6324","#800000","#aaffc3","#808000","#ffd8b1",
        "#000075","#a9a9a9","#e6beff","#fffac8","#fabebe",
    ]
    type_colour_map = {
        t: palette[i % len(palette)]
        for i, t in enumerate(all_primary_types)
    }

    map_path = "ola_places_map.html"
    with open(map_path, "w", encoding="utf-8") as f:
        f.write(build_map_html(all_places, type_colour_map))

    plotted = sum(1 for p in all_places if get_coords(p))
    print(f"  ✔  Map        → {map_path}  ({plotted} places plotted)")
    print(f"{'='*65}\n")

    webbrowser.open("file://" + os.path.abspath(map_path))
    print("  🗺  Map opened in your browser.\n")


if __name__ == "__main__":
    main()