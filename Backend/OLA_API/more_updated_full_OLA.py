"""
ola_places_full.py
──────────────────
ONE-STEP script:
  - Queries multiple offset points within the area, each with the FULL radius,
    so the Ola API always returns results (small radius = empty results bug)
  - Deduplicates by place_id across all queries
  - Enriches each new place with lat/lng in parallel ON THE SPOT
  - Saves ola_places_enriched.json  <- load this into ola_places_viewer.html

Usage:
  python ola_places_full.py
"""

import requests
import json
import time
import math
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
API_KEY   = "q4YyJBEO6pok33P8dM261aNb8Jg1cRcn9T5KW9a4"    # <-- your Ola Maps API key
LATITUDE  = 23.0009
LONGITUDE = 72.5065
RADIUS    = 2000   # metres — search radius used for EVERY query point

OUTPUT_FILE = "ola_places_enriched.json"
# ─────────────────────────────────────────────────────────────────────────────

# Multi-point settings
# Each query uses the full RADIUS but from a slightly different centre.
# Shifting the centre causes the API to return a different ranking/set of
# results, effectively bypassing the 50-result cap through overlap.
# OFFSETS controls how far (in metres) each shifted centre is from the original.
# More offset points = more unique places found.
OFFSETS = [
    (0,    0),       # centre
    (800,  0),       # N
    (-800, 0),       # S
    (0,    800),     # E
    (0,   -800),     # W
    (600,  600),     # NE
    (-600, 600),     # SE
    (-600,-600),     # SW
    (600, -600),     # NW
]

# Speed settings
FETCH_DELAY    = 0.3   # seconds between nearby-search requests
MAX_RETRIES    = 5
RETRY_BACKOFF  = 5
SAVE_EVERY     = 200
PAGE_LIMIT     = 50    # Ola API hard cap per page
ENRICH_WORKERS = 12    # parallel threads for coord enrichment

NEARBY_URL  = "https://api.olamaps.io/places/v1/nearbysearch"
DETAILS_URL = "https://api.olamaps.io/places/v1/details"
GEOCODE_URL = "https://api.olamaps.io/places/v1/geocode"

ALL_TYPES = [
    # "accounting", "airport", "amusement_park", "aquarium", "art_gallery",
    # "atm", "bakery", "bank", "bar", "beauty_salon", "bicycle_store",
    # "book_store", "bowling_alley", "bus_station", "cafe", "campground",
    # "car_dealer", "car_rental", "car_repair", "car_wash", "casino",
    # "cemetery", "church", "city_hall", "clothing_store", "convenience_store",
    # "courthouse", "dentist", "department_store", "doctor", "drugstore",
    # "electrician", "electronics_store", "embassy", "fire_station",
    # "florist", "funeral_home", "furniture_store", "gas_station", "gym",
    # "hair_care", "hardware_store", "hindu_temple", "home_goods_store",
    # "hospital", "insurance_agency", "jewelry_store", "laundry",
    # "lawyer", "library", "light_rail_station", "liquor_store",
    # "local_government_office", "locksmith", "lodging",
    # "mosque", "movie_rental", "movie_theater",
    # "moving_company", "museum", "night_club", "painter", "park",
    # "parking", "pet_store", "pharmacy", "physiotherapist", "plumber",
    # "police", "post_office", "primary_school", "real_estate_agency",
    # "restaurant", "roofing_contractor", "rv_park", "school",
    # "secondary_school", "shoe_store", "shopping_mall", "spa",
    # "stadium", "storage", "store", "supermarket",
    # "synagogue", "taxi_stand", "tourist_attraction",
    # "transit_station", "travel_agency", "university", "veterinary_care",
    "zoo",
]

# Thread-safe counters
_lock        = threading.Lock()
_coords_ok   = 0
_coords_fail = 0


# ── Offset point generation ───────────────────────────────────────────────────

def offset_point(lat, lng, north_m, east_m):
    """Shift a lat/lng by north_m metres north and east_m metres east."""
    dlat = north_m / 111320.0
    dlng = east_m  / (111320.0 * math.cos(math.radians(lat)))
    return lat + dlat, lng + dlng

def get_query_points():
    return [offset_point(LATITUDE, LONGITUDE, n, e) for n, e in OFFSETS]


# ── HTTP helper ───────────────────────────────────────────────────────────────

def _get(url, params):
    wait = RETRY_BACKOFF
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 429:
                print(f"\n    [429 — waiting {wait}s]", end=" ", flush=True)
                time.sleep(wait); wait *= 2; continue
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            print(f"\n  [Request error] {e}"); break
        except json.JSONDecodeError:
            print(f"\n  [Bad JSON]"); break
    return {}


# ── Field helpers ─────────────────────────────────────────────────────────────

def get_name(p):
    return (p.get("name")
            or (p.get("structured_formatting") or {}).get("main_text")
            or p.get("description") or "Unknown")

def get_types(p):
    raw = p.get("types") or p.get("type") or []
    return [raw] if isinstance(raw, str) else raw

def place_key(p):
    return (p.get("place_id") or p.get("id")
            or get_name(p) + str(p.get("geometry", "")))

def extract_coords(blob):
    loc = (blob.get("geometry") or {}).get("location") or {}
    if loc.get("lat") and loc.get("lng"):
        return float(loc["lat"]), float(loc["lng"])
    lat = blob.get("lat") or blob.get("latitude")
    lng = blob.get("lng") or blob.get("longitude")
    if lat and lng:
        return float(lat), float(lng)
    return None


# ── Coord enrichment ──────────────────────────────────────────────────────────

def enrich(place):
    global _coords_ok, _coords_fail

    # 1. Already in the nearby result — free, no extra call
    coords = extract_coords(place)
    if coords:
        place["lat"], place["lng"] = coords
        with _lock:
            _coords_ok += 1
        return True

    # 2. Place Details
    pid = place.get("place_id")
    if pid:
        data   = _get(DETAILS_URL, {"place_id": pid, "api_key": API_KEY})
        coords = extract_coords(data.get("result") or {})
        if coords:
            place["lat"], place["lng"] = coords
            with _lock:
                _coords_ok += 1
            return True

    # 3. Geocode fallback
    desc = place.get("description") or get_name(place)
    if desc:
        data    = _get(GEOCODE_URL, {"address": desc, "api_key": API_KEY})
        results = data.get("geocodingResults") or data.get("results") or []
        if results:
            coords = extract_coords(results[0])
            if coords:
                place["lat"], place["lng"] = coords
                with _lock:
                    _coords_ok += 1
                return True

    with _lock:
        _coords_fail += 1
    return False


def enrich_batch(new_places):
    if not new_places:
        return
    with ThreadPoolExecutor(max_workers=ENRICH_WORKERS) as ex:
        for f in as_completed({ex.submit(enrich, p): p for p in new_places}):
            f.result()


# ── Save helper ───────────────────────────────────────────────────────────────

def _save(places):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(places, f, ensure_ascii=False, indent=2)


# ── Main fetch + enrich loop ──────────────────────────────────────────────────

def fetch_and_enrich():
    points = get_query_points()
    n_pts  = len(points)

    print(f"\nFetching all nearby places  ({n_pts} query points × {len(ALL_TYPES)} types, {ENRICH_WORKERS} enrich threads)")
    print(f"Centre : {LATITUDE}, {LONGITUDE}  |  Radius : {RADIUS} m  |  Offset points : {n_pts}\n")

    seen        = set()
    all_places  = []
    total_types = len(ALL_TYPES)

    for i, ptype in enumerate(ALL_TYPES, 1):
        type_fetched   = 0
        type_new_count = 0
        prev_total     = len(all_places)

        for pt_lat, pt_lng in points:
            page_token = None

            while True:
                params = {
                    "location": f"{pt_lat},{pt_lng}",
                    "radius":   RADIUS,
                    "types":    ptype,
                    "limit":    PAGE_LIMIT,
                    "api_key":  API_KEY,
                }
                if page_token:
                    params["pagetoken"] = page_token

                data    = _get(NEARBY_URL, params)
                results = data.get("predictions") or data.get("results") or []

                batch = []
                for p in results:
                    k = place_key(p)
                    if k not in seen:
                        seen.add(k)
                        batch.append(p)
                        all_places.append(p)
                        type_new_count += 1

                type_fetched += len(results)
                enrich_batch(batch)

                page_token = data.get("next_page_token") or data.get("nextPageToken")
                if not page_token or not results:
                    break
                time.sleep(FETCH_DELAY)

            time.sleep(FETCH_DELAY)

        print(f"[{i:>3}/{total_types}] {ptype:<30} -> {type_fetched} fetched, {type_new_count} new  "
              f"[total: {len(all_places)}, coords: {_coords_ok} ok / {_coords_fail} failed]")

        if len(all_places) // SAVE_EVERY > prev_total // SAVE_EVERY:
            _save(all_places)

    return all_places


# ── Summary ───────────────────────────────────────────────────────────────────

def print_summary(places):
    by_type = defaultdict(int)
    for p in places:
        for t in get_types(p):
            by_type[t] += 1
    print("\nBreakdown by category:")
    for cat, cnt in sorted(by_type.items(), key=lambda x: -x[1]):
        bar = "#" * min(cnt, 40)
        print(f"  {cat:<38} {cnt:>4}  {bar}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    places = fetch_and_enrich()

    if not places:
        print("No places found. Check your API key, coordinates, and radius.")
        return

    _save(places)
    print_summary(places)

    plotted = sum(1 for p in places if p.get("lat") and p.get("lng"))
    print(f"\nDone.")
    print(f"  Total places  : {len(places)}")
    print(f"  Coords ok     : {_coords_ok}")
    print(f"  Coords failed : {_coords_fail}")
    print(f"  Map-ready     : {plotted}")
    print(f"  Saved to      : {OUTPUT_FILE}")
    print(f"\n  Drag & drop '{OUTPUT_FILE}' into ola_places_viewer.html\n")


if __name__ == "__main__":
    main()