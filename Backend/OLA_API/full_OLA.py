"""
ola_places_full.py
──────────────────
ONE-STEP script:
  - Fetches ALL nearby places (all types, all pages)
  - Enriches each new place with lat/lng ON THE SPOT as it is found
  - Uses parallel threads for coord enrichment to maximise speed
  - Saves ola_places_enriched.json  <- load this into ola_places_viewer.html

Usage:
  python ola_places_full.py
"""

import requests
import json
import time
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
API_KEY   = "q4YyJBEO6pok33P8dM261aNb8Jg1cRcn9T5KW9a4"   # <-- your Ola Maps API key
LATITUDE  = 23.0073
LONGITUDE = 72.4549
RADIUS    = 2000             # metres

OUTPUT_FILE = "ola_places_enriched.json"
# ─────────────────────────────────────────────────────────────────────────────

FETCH_DELAY    = 0.3   # seconds between nearby-search page requests
MAX_RETRIES    = 5
RETRY_BACKOFF  = 5     # seconds (doubles each retry)
SAVE_EVERY     = 150   # save to disk every N total places
PAGE_LIMIT     = 50    # max results per page
ENRICH_WORKERS = 18    # parallel threads for coord enrichment

NEARBY_URL  = "https://api.olamaps.io/places/v1/nearbysearch"
DETAILS_URL = "https://api.olamaps.io/places/v1/details"
GEOCODE_URL = "https://api.olamaps.io/places/v1/geocode"

ALL_TYPES = [
    # "accounting", "airport", "amusement_park", "aquarium", "art_gallery",
    "atm", "bakery", "bank", "bar", "beauty_salon", "bicycle_store",
    # "book_store", "bowling_alley", "bus_station", "cafe", "campground",
    # "car_dealer", "car_rental", "car_repair", "car_wash", "casino",
    # "cemetery", "church", "city_hall", "clothing_store", "convenience_store",
    # "courthouse", "dentist", "department_store", "doctor", "drugstore",
    # "electrician", "electronics_store", "embassy", "fire_station",
    # "florist", "funeral_home", "furniture_store", "gas_station", "gym",
    # "hair_care", "hardware_store", "hindu_temple", "home_goods_store",
    # "hospital", "insurance_agency", "jewelry_store", "laundry",
    # "lawyer", "library", "light_rail_station", "liquor_store",
    # "local_government_office", "locksmith", "lodging", "meal_delivery",
    # "meal_takeaway", "mosque", "movie_rental", "movie_theater",
    # "moving_company", "museum", "night_club", "painter", "park",
    # "parking", "pet_store", "pharmacy", "physiotherapist", "plumber",
    # "police", "post_office", "primary_school", "real_estate_agency",
    # "restaurant", "roofing_contractor", "rv_park", "school",
    # "secondary_school", "shoe_store", "shopping_mall", "spa",
    # "stadium", "storage", "store", "subway_station", "supermarket",
    # "synagogue", "taxi_stand", "tourist_attraction", "train_station",
    # "transit_station", "travel_agency", "university", "veterinary_care",
    # "zoo",
]

# Thread-safe counters
_lock        = threading.Lock()
_coords_ok   = 0
_coords_fail = 0


# ── HTTP helper ───────────────────────────────────────────────────────────────

def _get(url, params):
    wait = RETRY_BACKOFF
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 429:
                time.sleep(wait); wait *= 2; continue
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException:
            break
        except json.JSONDecodeError:
            break
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
    """Pull lat/lng from any response shape."""
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
    """
    Attach lat/lng to place in-place.
    Order of preference (fastest first):
      1. Coords already in the nearby result geometry  -> no extra API call
      2. Place Details API
      3. Geocode API (last resort)
    """
    global _coords_ok, _coords_fail

    # 1. Already present — free, no API call needed
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
    """Enrich a list of places in parallel."""
    if not new_places:
        return
    with ThreadPoolExecutor(max_workers=ENRICH_WORKERS) as ex:
        futures = {ex.submit(enrich, p): p for p in new_places}
        for f in as_completed(futures):
            f.result()  # surface exceptions if any


# ── Save helper ───────────────────────────────────────────────────────────────

def _save(places):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(places, f, ensure_ascii=False, indent=2)


# ── Main fetch + enrich loop ──────────────────────────────────────────────────

def fetch_and_enrich():
    print(f"\nFetching all nearby places  (parallel enrichment, {ENRICH_WORKERS} threads)")
    print(f"Centre : {LATITUDE}, {LONGITUDE}  |  Radius : {RADIUS} m\n")

    seen        = set()
    all_places  = []
    total_types = len(ALL_TYPES)

    for i, ptype in enumerate(ALL_TYPES, 1):
        print(f"[{i:>3}/{total_types}] {ptype:<30}", end=" ", flush=True)

        type_fetched = 0
        type_new     = []
        page_token   = None

        while True:
            params = {
                "location": f"{LATITUDE},{LONGITUDE}",
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
                    type_new.append(p)
                    all_places.append(p)

            type_fetched += len(results)

            # Enrich this page's new places in parallel while fetching continues
            enrich_batch(batch)

            page_token = data.get("next_page_token") or data.get("nextPageToken")
            if not page_token or not results:
                break
            time.sleep(FETCH_DELAY)

        print(f"-> {type_fetched} fetched, {len(type_new)} new  "
              f"[total: {len(all_places)}, coords: {_coords_ok} ok / {_coords_fail} failed]")

        if len(all_places) // SAVE_EVERY > (len(all_places) - len(type_new)) // SAVE_EVERY:
            _save(all_places)

        time.sleep(FETCH_DELAY)

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