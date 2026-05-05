"""
enrich_coords.py
────────────────
Reads ola_places_output.json, fetches lat/lng for each place via the
Ola Maps Place Details API, and saves ola_places_enriched.json.

Run ONCE before opening the viewer HTML.
"""

import requests
import json
import time
import os

# ─────────────────────────────────────────────
API_KEY      = "q4YyJBEO6pok33P8dM261aNb8Jg1cRcn9T5KW9a4"        # <-- your Ola Maps API key
INPUT_FILE   = "ola_places_output.json"  # produced by ola_nearby_places.py
OUTPUT_FILE  = "ola_places_enriched.json"  # viewer will read this
# ─────────────────────────────────────────────

DETAILS_URL  = "https://api.olamaps.io/places/v1/details"
GEOCODE_URL  = "https://api.olamaps.io/places/v1/geocode"

DELAY        = 0.5   # seconds between requests
MAX_RETRIES  = 4
RETRY_WAIT   = 6     # seconds, doubles on each retry


def fetch_details(place_id: str) -> tuple[float, float] | None:
    """Fetch lat/lng for a place_id from the Place Details endpoint."""
    params = {"place_id": place_id, "api_key": API_KEY}
    wait = RETRY_WAIT
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(DETAILS_URL, params=params, timeout=10)
            if r.status_code == 429:
                print(f"  ⚠ 429 (attempt {attempt}) — waiting {wait}s", end=" ", flush=True)
                time.sleep(wait); wait *= 2; continue
            r.raise_for_status()
            data = r.json()
            # Response shape: { "result": { "geometry": { "location": { "lat": ..., "lng": ... } } } }
            loc = (data.get("result") or {}).get("geometry", {}).get("location", {})
            if loc.get("lat") and loc.get("lng"):
                return float(loc["lat"]), float(loc["lng"])
        except Exception as e:
            print(f"  [error: {e}]", end=" ")
            break
    return None


def fetch_geocode(description: str) -> tuple[float, float] | None:
    """Fallback: geocode by address string."""
    params = {"address": description, "api_key": API_KEY}
    wait = RETRY_WAIT
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(GEOCODE_URL, params=params, timeout=10)
            if r.status_code == 429:
                print(f"  ⚠ 429 geocode (attempt {attempt}) — waiting {wait}s", end=" ", flush=True)
                time.sleep(wait); wait *= 2; continue
            r.raise_for_status()
            data = r.json()
            results = data.get("geocodingResults") or data.get("results") or []
            if results:
                loc = results[0].get("geometry", {}).get("location", {})
                if loc.get("lat") and loc.get("lng"):
                    return float(loc["lat"]), float(loc["lng"])
        except Exception as e:
            print(f"  [geocode error: {e}]", end=" ")
            break
    return None


def main():
    if not os.path.exists(INPUT_FILE):
        print(f"❌  '{INPUT_FILE}' not found. Run ola_nearby_places.py first.")
        return

    with open(INPUT_FILE, encoding="utf-8") as f:
        places = json.load(f)

    # Resume support — skip places that already have coords
    already_done = sum(1 for p in places if p.get("lat") and p.get("lng"))
    total = len(places)

    print(f"\n{'='*60}")
    print(f"  Enriching {total} places with coordinates")
    print(f"  Already done: {already_done}  |  Remaining: {total - already_done}")
    print(f"{'='*60}\n")

    ok = already_done
    failed = 0

    for i, place in enumerate(places, 1):
        # Skip if already enriched
        if place.get("lat") and place.get("lng"):
            continue

        name = (place.get("structured_formatting") or {}).get("main_text") \
               or place.get("name") or place.get("description") or "?"
        print(f"[{i:>4}/{total}] {name[:45]:<45}", end=" … ", flush=True)

        coords = None

        # Try Place Details first (most accurate)
        pid = place.get("place_id")
        if pid:
            coords = fetch_details(pid)

        # Fallback to geocoding the description
        if not coords and place.get("description"):
            coords = fetch_geocode(place["description"])

        if coords:
            place["lat"], place["lng"] = coords
            print(f"✔  {coords[0]:.5f}, {coords[1]:.5f}")
            ok += 1
        else:
            print("✘  no coords")
            failed += 1

        time.sleep(DELAY)

        # Save progress every 50 places in case of interruption
        if i % 50 == 0:
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(places, f, ensure_ascii=False, indent=2)
            print(f"  💾  Progress saved ({ok} enriched so far)\n")

    # Final save
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(places, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"  ✔  Enriched : {ok}/{total}")
    print(f"  ✘  Failed   : {failed}/{total}")
    print(f"  📄  Saved to : {OUTPUT_FILE}")
    print(f"{'='*60}\n")
    print("  Now load this file into ola_places_viewer.html\n")


if __name__ == "__main__":
    main()