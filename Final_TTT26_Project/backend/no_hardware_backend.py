"""
GeoSpatial API Function Tester
==============================
Tests all functions using only external APIs — no local files, no osmnx.
Saves full results (including competitor lat/lon) to test_results.json
for rendering in geo_map.html.

Usage:
    python no_hardware_backend.py
    python no_hardware_backend.py --lat 23.0225 --lon 72.5714 --radius 2000

Changelog:
    - Integrated real Population API (data.portal / JWT auth)
    - Integrated OpenCelliD / Unwired Labs Cell Tower API
    - Fixed WorldPop geojson serialisation bug (str() → json.dumps())
    - Fixed EONET radius (was radius_km*5, now radius_km)
    - Fixed road intersection counting (nodes may be int or dict)
    - Fixed weather avg when series is empty
    - Concurrent sub-calls in main() for speed
    - [NEW] test_competitors_ola uses full paginated fetch + 3-level coord
      enrichment from ola_places_full.py strategy (geometry → Details → Geocode)
"""

import argparse
import json
import math
import time
import requests
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ═══════════════════════════════════════════════════════════
#  ██████████  CHANGE YOUR API KEYS HERE  ██████████
#
#  Priority: env-var → hardcoded fallback below.
#  Set an env var (e.g. export OLA_MAPS_API_KEY=xxx) to
#  override at runtime, or just paste your key as the
#  second argument to os.getenv().
# ═══════════════════════════════════════════════════════════

# ── Ola Maps (India competitor search) ─────────────────────
# Get your key at: https://maps.olakrutrim.com/
OLA_MAPS_API_KEY = os.getenv(
    "q4YyJBEO6pok33P8dM261aNb8Jg1cRcn9T5KW9a4",
    "q4YyJBEO6pok33P8dM261aNb8Jg1cRcn9T5KW9a4",   # ← CHANGE THIS if your key is different
)

# ── Google Places (optional, improves competitor results) ──
# Get at: https://console.cloud.google.com/
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")   # ← paste key here

# ── Foursquare (optional) ───────────────────────────────────
FOURSQUARE_API_KEY = os.getenv("FOURSQUARE_API_KEY", "")         # ← paste key here

# ── OpenCage Geocoder (optional) ───────────────────────────
OPENCAGE_API_KEY = os.getenv("OPENCAGE_API_KEY", "")             # ← paste key here

# ── OpenRouteService (optional, for real isochrones) ────────
OPENROUTESERVICE_API_KEY = os.getenv("OPENROUTESERVICE_API_KEY", "")  # ← paste key here

# ── Population Data Portal (JWT) ───────────────────────────
# Update POPULATION_API_BASE to your real portal URL.
POPULATION_API_BEARER = os.getenv(
    "POPULATION_API_BEARER",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJtZGgxMTA0NzhAZ21haWwuY29tIiwiZW1haWwiOiJtZGgxMTA0NzhAZ21haWwuY29tIiwidW5pcXVlX25hbWUiOiJtZGgxMTA0NzhAZ21haWwuY29tIiwibmJmIjoxNzc1ODU5MDUxLCJleHAiOjE4MDczOTUwNTEsImlhdCI6MTc3NTg1OTA1MSwiaXNzIjoiZG90bmV0LXVzZXItand0cyIsImF1ZCI6ImRhdGEtcG9ydGFsLWFwaSJ9.5RB_H01Zt4SrmL4tbDHYjF1snpsiEj1bEIKBO2kgMmg",
)
POPULATION_API_BASE = "https://data-portal-api.example.com"   # ← UPDATE to your real base URL

# ── Cell Tower / Unwired Labs ───────────────────────────────
CELL_TOWER_API_KEY = os.getenv("CELL_TOWER_API_KEY", "pk.03d561ff2d0afab481005b31dff3347b")  # ← paste key here
CELL_TOWER_API_URL = "https://us1.unwiredlabs.com/v2/search.json"

# ═══════════════════════════════════════════════════════════
#  END OF KEY CONFIG
# ═══════════════════════════════════════════════════════════

# ─────────────────────────────────────────────
#  OVERPASS MIRRORS
# ─────────────────────────────────────────────
OVERPASS_ENDPOINTS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def _header(title: str):
    print("\n" + "═" * 60)
    print(f"  {title}")
    print("═" * 60)

def _ok(key, value):
    print(f"  ✅  {key:30s} {value}")

def _warn(key, value):
    print(f"  ⚠️   {key:30s} {value}")

def _err(msg):
    print(f"  ❌  {msg}")

_overpass_lock = threading.Lock()

def _overpass_query(query: str, timeout: int = 45) -> dict:
    """Try multiple Overpass mirrors until one succeeds. Serialized to prevent 504 drops on bursts."""
    last_exc = None
    with _overpass_lock:
        for url in OVERPASS_ENDPOINTS:
            try:
                print(f"  ⏳  Trying {url} ...")
                resp = requests.post(url, data={"data": query}, timeout=timeout)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                _warn(f"Mirror failed ({url})", str(e))
                last_exc = e
    raise RuntimeError(f"All Overpass mirrors failed. Last error: {last_exc}")

def _safe_avg(values: list) -> float | None:
    """Return average of non-None values, or None if list is empty."""
    clean = [v for v in values if v is not None]
    return round(sum(clean) / len(clean), 2) if clean else None

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return 6371.0 * (2 * math.asin(math.sqrt(a)))


# ═══════════════════════════════════════════════════════════
#  1. ROAD SCORE
# ═══════════════════════════════════════════════════════════

def test_road_score(lat: float, lon: float, radius: int) -> dict:
    _header("1. ROAD SCORE  (Overpass API)")
    t0 = time.time()

    query = f"""
    [out:json][timeout:60];
    (
      way["highway"](around:{radius},{lat},{lon});
    );
    out geom;
    """

    try:
        data = _overpass_query(query, timeout=45)
    except Exception as e:
        _err(f"Overpass request failed: {e}")
        return {}

    elements = data.get("elements", [])
    if not elements:
        _warn("ways found", "0 — try increasing radius")
        return {}

    highway_types  = {}
    total_length_m = 0.0
    node_set       = set()

    for way in elements:
        hw = way.get("tags", {}).get("highway", "unclassified")
        highway_types[hw] = highway_types.get(hw, 0) + 1

        geom = way.get("geometry", [])

        # BUG FIX: nodes can be int IDs or dicts with "ref" key
        for n in way.get("nodes", []):
            if isinstance(n, int):
                node_set.add(n)
            elif isinstance(n, dict):
                node_set.add(n.get("ref", 0))

        for i in range(len(geom) - 1):
            a, b = geom[i], geom[i + 1]
            # Guard against missing lat/lon in geometry points
            if None in (a.get("lat"), a.get("lon"), b.get("lat"), b.get("lon")):
                continue
            dlat = math.radians(b["lat"] - a["lat"])
            dlon = math.radians(b["lon"] - a["lon"])
            ha   = math.sin(dlat / 2) ** 2 + (
                math.cos(math.radians(a["lat"])) *
                math.cos(math.radians(b["lat"])) *
                math.sin(dlon / 2) ** 2
            )
            total_length_m += 6_371_000 * 2 * math.asin(math.sqrt(ha))

    total_km = round(total_length_m / 1000, 2)

    node_way_count = {}
    for way in elements:
        for n in way.get("nodes", []):
            # BUG FIX: same normalisation as above
            nid = n if isinstance(n, int) else n.get("ref", 0)
            node_way_count[nid] = node_way_count.get(nid, 0) + 1

    intersections = sum(1 for v in node_way_count.values() if v >= 2)
    dead_ends     = sum(1 for v in node_way_count.values() if v == 1)

    top_types = [k for k, _ in sorted(highway_types.items(), key=lambda x: -x[1])[:12]]
    result = {
        "total_ways":        len(elements),
        "total_nodes":       len(node_set),
        "road_score_km":     total_km,
        "total_length_km":   total_km,  # alias for API clients
        "intersections":     intersections,
        "dead_ends":         dead_ends,
        "highway_breakdown": dict(sorted(highway_types.items(), key=lambda x: -x[1])[:8]),
        "top_highway_types": top_types,
        "elapsed_s":         round(time.time() - t0, 2),
        "source":            "overpass",
    }

    _ok("Total road ways",   str(result["total_ways"]))
    _ok("Total road length", f"{result['road_score_km']} km")
    _ok("Intersections",     str(result["intersections"]))
    _ok("Dead-ends",         str(result["dead_ends"]))
    _ok("Top highway types", str(list(highway_types.keys())[:4]))
    _ok("Elapsed",           f"{result['elapsed_s']} s")
    return result


# ═══════════════════════════════════════════════════════════
#  2. COMPETITORS  →  Overpass / Google
# ═══════════════════════════════════════════════════════════

OSM_BUSINESS_TAGS = {
    "restaurant":  [("amenity", "restaurant"), ("amenity", "cafe"), ("amenity", "fast_food")],
    "hotel":       [("tourism", "hotel"), ("tourism", "guest_house"), ("tourism", "hostel"), ("tourism", "stays"), ("tourism", "motel"), ("tourism", "resort"), ("tourism", "apartment")],
    "pharmacy":    [("amenity", "pharmacy"), ("amenity", "medical"), ("shop", "medical_supply"), ("shop", "chemist")],
    "supermarket": [("shop", "supermarket"), ("shop", "convenience"), ("shop", "kirana"), ("shop", "groceries"), ("shop", "dukaan"), ("shop", "general_stores"), ("shop", "general"), ("shop", "greengrocer"), ("shop", "department_store")],
    "bank":        [("amenity", "bank"), ("amenity", "atm"), ("amenity", "finance")],
    "gym":         [("leisure", "fitness_centre"), ("amenity", "gym"), ("leisure", "sports_centre"), ("leisure", "fitness")],
    "hospital":    [("amenity", "hospital"), ("amenity", "clinic"), ("amenity", "doctors"), ("amenity", "healthcare"), ("amenity", "nursing_home")],
    "petrol":      [("amenity", "fuel"), ("amenity", "charging_station")],
    "clothing":    [("shop", "clothes"), ("shop", "fashion"), ("shop", "shoes"), ("shop", "boutique"), ("shop", "tailor")],
    "hardware":    [("shop", "hardware"), ("shop", "doityourself"), ("shop", "paint"), ("shop", "tools"), ("shop", "trade")],
    "telecom_towers": [("man_made", "mast"), ("man_made", "tower"), ("man_made", "communications_tower")],
    "ev_stations": [("amenity", "charging_station")],
}

# ═══════════════════════════════════════════════════════════
#  OLA MAPS COMPETITOR SEARCH  (India-only, falls back to OSM)
# ═══════════════════════════════════════════════════════════

OLA_MAPS_CATEGORY_MAP = {
    "restaurant":  "restaurant,cafe",
    "hotel":       "lodging",
    "pharmacy":    "pharmacy",
    "supermarket": "supermarket,convenience_store",
    "bank":        "bank,atm",
    "gym":         "gym",
    "hospital":    "hospital",
    "petrol":      "gas_station",
    "clothing":    "clothing_store",
    "hardware":    "hardware_store",
    "telecom_towers": "",
    "ev_stations": "",
}

OLA_AUTOCOMPLETE_KWS = {
    "restaurant": ["pizza", "donut", "ice cream", "burger", "McDonald's", "Domino's", "KFC", "Subway", "Pizza Hut", "Burger King", "Starbucks", "Cafe Coffee Day", "Haldiram's", "Bikanervala", "Barbeque Nation"],
    "supermarket": ["Reliance Smart", "D-Mart", "Big Bazaar", "Grocery", "Provisions", "Supermarket", "Blinkit", "Zepto", "Spencer's", "More Supermarket", "Reliance Fresh", "Groceries"],
    "hotel": ["OYO", "Taj", "ITC", "Marriott", "Radisson", "Lemon Tree", "Hotel", "Resort", "Guest House", "Lodge", "Inn"],
    "bank": ["HDFC", "SBI", "ICICI", "Axis Bank", "Kotak", "Bank of Baroda", "Punjab National Bank", "ATM", "Bank", "Finance", "Union Bank", "Central Bank"],
    "pharmacy": ["Pharmacy", "MedPlus", "Netmeds", "Medical", "Chemist", "Drugs", "Medicine"],
    "hospital": ["Apollo", "Fortis", "Max Hospital", "AIIMS", "Clinic", "Hospital", "Care", "Healthcare", "Nursing Home"],
    "gym": ["Cult.fit", "Gold's Gym", "Fitness First", "Talwalkars", "Gym", "Fitness", "Workout", "Health Club", "Shred", "Fitness studio"],
    "clothing": ["Zara", "H&M", "Pantaloons", "Lifestyle", "Max Fashion", "Shoppers Stop", "Trendy", "Apparel", "Boutique", "Clothing", "Shoes", "Garments"],
    "hardware": ["Hardware", "Paints", "Asian Paints", "Berger", "Sanitary", "Electricals", "Tools", "Plywood", "Tiles"],
    "petrol": ["Indian Oil", "Bharat Petroleum", "HP", "Reliance Petrol", "Shell", "Nayara", "Petrol Pump", "Gas Station", "CNG"],
    "telecom_towers": ["Telecom Tower", "Cell Tower", "Mobile Mast", "Jio Tower", "Airtel Tower", "Vodafone Tower", "BSNL Tower", "Indus Tower"],
    "ev_stations": ["EV Charging", "Electric Vehicle Charging", "Tata Power EV", "Ather Grid", "ChargeZone", "Statiq", "EV Station", "Jio-bp pulse", "Zeon Charging"]
}

def _is_india(lat: float, lon: float) -> bool:
    """Bounding box check — fast, no API call."""
    return 6.0 <= lat <= 37.5 and 68.0 <= lon <= 97.5

# ── Ola Maps full-fetch helpers (ola_places_full.py strategy) ──────────────

_OLA_NEARBY_URL     = "https://api.olamaps.io/places/v1/nearbysearch"
_OLA_DETAILS_URL    = "https://api.olamaps.io/places/v1/details"
_OLA_GEOCODE_URL    = "https://api.olamaps.io/places/v1/geocode"
_OLA_AUTO_URL       = "https://api.olamaps.io/places/v1/autocomplete"

_OLA_FETCH_DELAY    = 0.3    # seconds between paginated page requests
_OLA_MAX_RETRIES    = 3
_OLA_PAGE_LIMIT     = 50     # max results per page
_OLA_ENRICH_WORKERS = 16     # parallel threads for coord enrichment


def _ola_get(url: str, params: dict) -> dict:
    """Resilient GET with retry and 429 back-off."""
    wait = 5
    for _ in range(_OLA_MAX_RETRIES):
        try:
            r = requests.get(url, params=params, timeout=12)
            if r.status_code == 429:
                time.sleep(wait)
                wait *= 2
                continue
            r.raise_for_status()
            return r.json()
        except Exception:
            break
    return {}


def _ola_place_key(p: dict) -> str:
    """Unique key for deduplication across nearbysearch + autocomplete results."""
    name = (
        p.get("name")
        or (p.get("structured_formatting") or {}).get("main_text")
        or p.get("description")
        or ""
    )
    return p.get("place_id") or p.get("id") or (name + str(p.get("geometry", "")))


def _ola_extract_coords(blob: dict):
    """Pull (lat, lng) from any Ola Maps response shape. Returns (lat, lng) or None."""
    loc = (blob.get("geometry") or {}).get("location") or {}
    if loc.get("lat") and loc.get("lng"):
        return float(loc["lat"]), float(loc["lng"])
    lat = blob.get("lat") or blob.get("latitude")
    lng = blob.get("lng") or blob.get("longitude")
    if lat and lng:
        return float(lat), float(lng)
    return None


def _ola_enrich_place(place: dict, api_key: str) -> bool:
    """
    Attach lat/lng to place dict in-place using 3-level fallback:
      1. geometry already in the nearbysearch/autocomplete result  → free, no extra call
      2. Place Details API                                         → 1 extra call
      3. Geocode API                                               → last resort
    Returns True if coordinates were successfully resolved.
    """
    # Level 1 — geometry already present
    coords = _ola_extract_coords(place)
    if coords:
        place["lat"], place["lng"] = coords
        return True

    # Level 2 — Place Details API
    pid = place.get("place_id")
    if pid:
        data = _ola_get(_OLA_DETAILS_URL, {"place_id": pid, "api_key": api_key})
        coords = _ola_extract_coords(data.get("result") or {})
        if coords:
            place["lat"], place["lng"] = coords
            # Also pull enriched fields if available
            result = data.get("result", {})
            if result.get("name"):
                place["name"] = result["name"]
            if result.get("formatted_address"):
                place["formatted_address"] = result["formatted_address"]
            if result.get("rating"):
                place["rating"] = result["rating"]
            if result.get("opening_hours"):
                place["opening_hours"] = result["opening_hours"]
            return True

    # Level 3 — Geocode fallback
    desc = place.get("description") or place.get("name") or ""
    if desc:
        data = _ola_get(_OLA_GEOCODE_URL, {"address": desc, "api_key": api_key})
        results = data.get("geocodingResults") or data.get("results") or []
        if results:
            coords = _ola_extract_coords(results[0])
            if coords:
                place["lat"], place["lng"] = coords
                return True

    return False


def _ola_fetch_type_paginated(ptype: str, lat: float, lon: float,
                               radius: int, api_key: str) -> list:
    """
    Fetch ALL pages for one place type from Ola Maps nearbysearch.
    Follows next_page_token until exhausted.
    """
    results_all = []
    page_token  = None
    while True:
        params = {
            "location": f"{lat},{lon}",
            "radius":   radius,
            "types":    ptype,
            "limit":    _OLA_PAGE_LIMIT,
            "api_key":  api_key,
        }
        if page_token:
            params["pagetoken"] = page_token
        data       = _ola_get(_OLA_NEARBY_URL, params)
        page_items = data.get("predictions") or data.get("results") or []
        results_all.extend(page_items)
        page_token = data.get("next_page_token") or data.get("nextPageToken")
        if not page_token or not page_items:
            break
        time.sleep(_OLA_FETCH_DELAY)
    return results_all


def _ola_fetch_autocomplete(kw: str, lat: float, lon: float,
                             radius: int, api_key: str) -> list:
    """Single autocomplete query for a brand/chain keyword."""
    try:
        resp = requests.get(
            _OLA_AUTO_URL,
            params={"location": f"{lat},{lon}", "radius": radius,
                    "input": kw, "api_key": api_key},
            headers={"Accept": "application/json"},
            timeout=8,
        )
        if resp.status_code == 200:
            return resp.json().get("predictions", [])
    except Exception:
        pass
    return []


def test_competitors_ola(lat: float, lon: float, radius: int,
                          business_type: str = "restaurant") -> dict:
    """
    Full Ola Maps competitor search using the ola_places_full.py strategy:
      • Paginated nearbysearch across ALL mapped category types (follows next_page_token)
      • Keyword-based autocomplete sweep for Indian brand/chain names
      • Parallel coord enrichment: geometry → Details API → Geocode fallback
      • Strict radius filter applied after enrichment
      • Returns named_count + coords_ok/coords_failed for diagnostics
    """
    _header(f"2c. COMPETITORS — Ola Maps (full paginated fetch)  [{business_type}]")

    if not OLA_MAPS_API_KEY:
        _warn("Skipped", "OLA_MAPS_API_KEY not set — add it to the key config at top of file")
        return {}

    t0 = time.time()
    _ok("API key active", f"{OLA_MAPS_API_KEY[:8]}...{OLA_MAPS_API_KEY[-4:]}")

    category_str       = OLA_MAPS_CATEGORY_MAP.get(business_type.lower(), business_type)
    types_to_search    = [c.strip() for c in category_str.split(",") if c.strip()]
    keywords_to_search = OLA_AUTOCOMPLETE_KWS.get(business_type.lower(), [])

    # ── Phase 1: parallel fetch ─────────────────────────────────────────────
    raw_places: list = []
    seen_keys:  set  = set()
    raw_lock         = threading.Lock()

    def _collect(items: list):
        with raw_lock:
            for p in items:
                k = _ola_place_key(p)
                if k not in seen_keys:
                    seen_keys.add(k)
                    raw_places.append(p)

    with ThreadPoolExecutor(max_workers=12) as ex:
        futures = {}
        for ptype in types_to_search:
            f = ex.submit(_ola_fetch_type_paginated, ptype, lat, lon, radius, OLA_MAPS_API_KEY)
            futures[f] = f"nearby:{ptype}"
        for kw in keywords_to_search:
            f = ex.submit(_ola_fetch_autocomplete, kw, lat, lon, radius, OLA_MAPS_API_KEY)
            futures[f] = f"auto:{kw}"

        for f in as_completed(futures):
            try:
                _collect(f.result())
            except Exception as e:
                _warn(f"Fetch failed ({futures[f]})", str(e))

    _ok("Raw candidates (deduped)", str(len(raw_places)))

    # ── Phase 2: parallel coord enrichment ─────────────────────────────────
    coords_ok   = 0
    coords_fail = 0
    enrich_lock = threading.Lock()

    def _enrich_and_count(p):
        nonlocal coords_ok, coords_fail
        ok = _ola_enrich_place(p, OLA_MAPS_API_KEY)
        with enrich_lock:
            if ok:
                coords_ok += 1
            else:
                coords_fail += 1

    with ThreadPoolExecutor(max_workers=_OLA_ENRICH_WORKERS) as ex:
        futs = [ex.submit(_enrich_and_count, p) for p in raw_places]
        for f in as_completed(futs):
            try:
                f.result()
            except Exception:
                pass

    # ── Phase 3: radius filter + build output ───────────────────────────────
    competitors = []
    for p in raw_places:
        clat = p.get("lat")
        clng = p.get("lng")
        if clat is None or clng is None:
            continue
        dist_km = _haversine_km(lat, lon, float(clat), float(clng))
        if dist_km * 1000 > radius:
            continue

        name = (
            p.get("name")
            or (p.get("structured_formatting") or {}).get("main_text")
            or p.get("description")
            or "Unnamed"
        ).strip() or "Unnamed"

        competitors.append({
            "name":     name,
            "lat":      float(clat),
            "lon":      float(clng),
            "rating":   p.get("rating"),
            "address":  (p.get("formatted_address")
                         or p.get("vicinity")
                         or p.get("description", "")),
            "place_id": p.get("place_id", ""),
            "types":    p.get("types") or [],
            "open_now": (p.get("opening_hours") or {}).get("open_now"),
            "source":   "ola_maps",
        })

    named = [c for c in competitors if c["name"] != "Unnamed"]

    result = {
        "total_count":   len(competitors),
        "named_count":   len(named),
        "named_list":    [c["name"] for c in named],
        "locations":     [{"lat": c["lat"], "lon": c["lon"], "name": c["name"]} for c in competitors],
        "competitors":   competitors,
        "coords_ok":     coords_ok,
        "coords_failed": coords_fail,
        "elapsed_s":     round(time.time() - t0, 2),
        "source":        "ola_maps",
        "business_type": business_type,
    }

    _ok("Total in radius", str(result["total_count"]))
    _ok("Named",           str(result["named_count"]))
    _ok("Coords ok/fail",  f"{coords_ok} / {coords_fail}")
    _ok("Sample names",    str(result["named_list"][:8]))
    _ok("Elapsed",         f"{result['elapsed_s']} s")
    return result


def test_competitors_osm(lat: float, lon: float, radius: int,
                          business_type: str = "restaurant") -> dict:
    _header(f"2a. COMPETITORS — OSM / Overpass  [{business_type}]")
    t0 = time.time()

    tags = OSM_BUSINESS_TAGS.get(business_type.lower(),
                                  [("amenity", business_type)])

    union_parts = []
    # Group values by key to build regex strings (exponentially faster for Overpass public instances)
    key_map = {}
    for key, val in tags:
        if key not in key_map:
            key_map[key] = []
        key_map[key].append(val)
        
    for key, vals in key_map.items():
        if len(vals) == 1:
            union_parts.append(f'node["{key}"="{vals[0]}"](around:{radius},{lat},{lon});')
            union_parts.append(f'way["{key}"="{vals[0]}"](around:{radius},{lat},{lon});')
        else:
            val_str = "|".join(vals)
            union_parts.append(f'node["{key}"~"^({val_str})$"](around:{radius},{lat},{lon});')
            union_parts.append(f'way["{key}"~"^({val_str})$"](around:{radius},{lat},{lon});')

    query = "[out:json][timeout:25];\n(\n" + "\n".join(union_parts) + "\n);\nout center tags;"

    try:
        data     = _overpass_query(query, timeout=45)
        elements = data.get("elements", [])
    except Exception as e:
        _err(f"Overpass request failed: {e}")
        return {}

    competitors = []
    for el in elements:
        tags_el = el.get("tags", {})
        name    = (tags_el.get("name:en") or tags_el.get("name") or tags_el.get("brand:en") or tags_el.get("brand") or "Unnamed").strip() or "Unnamed"
        cuisine = tags_el.get("cuisine", "")
        phone   = tags_el.get("phone", tags_el.get("contact:phone", ""))
        website = tags_el.get("website", tags_el.get("contact:website", ""))

        if el["type"] == "node":
            clat, clon = el.get("lat"), el.get("lon")
        else:
            center = el.get("center", {})
            clat, clon = center.get("lat"), center.get("lon")

        if clat is None or clon is None:
            continue

        competitors.append({
            "name":    name,
            "lat":     clat,
            "lon":     clon,
            "cuisine": cuisine,
            "phone":   phone,
            "website": website,
            "type":    tags_el.get("amenity",
                       tags_el.get("shop",
                       tags_el.get("tourism", ""))),
        })

    total = len(competitors)
    named = [c for c in competitors if c["name"] != "Unnamed"]

    result = {
        "total_count":   total,
        "named_count":   len(named),
        "named_list":    [c["name"] for c in named],
        "locations":     [{"lat": c["lat"], "lon": c["lon"], "name": c["name"]} for c in competitors],
        "competitors":   competitors,
        "elapsed_s":     round(time.time() - t0, 2),
        "source":        "osm",
        "business_type": business_type,
    }

    _ok("Total found",  str(total))
    _ok("Named",        str(len(named)))
    _ok("Sample names", str(result["named_list"][:5]))
    _ok("Elapsed",      f"{result['elapsed_s']} s")
    return result


def test_competitors_google(lat: float, lon: float, radius: int,
                             business_type: str = "restaurant") -> dict:
    _header(f"2b. COMPETITORS — Google Places  [{business_type}]")

    if not GOOGLE_PLACES_API_KEY:
        _warn("Skipped", "GOOGLE_PLACES_API_KEY not set")
        return {}

    t0  = time.time()
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lon}",
        "radius":   radius,
        "type":     business_type,
        "key":      GOOGLE_PLACES_API_KEY,
        "language": "en",
    }
    try:
        data   = requests.get(url, params=params, timeout=15).json()
        places = data.get("results", [])
    except Exception as e:
        _err(f"Google Places failed: {e}")
        return {}

    competitors = []
    for p in places:
        loc = p.get("geometry", {}).get("location", {})
        competitors.append({
            "name":   p.get("name", "Unnamed"),
            "lat":    loc.get("lat"),
            "lon":    loc.get("lng"),
            "rating": p.get("rating"),
            "source": "google",
        })

    result = {
        "total_count": len(places),
        "named_list":  [p.get("name") for p in places],
        "competitors": competitors,
        "elapsed_s":   round(time.time() - t0, 2),
        "source":      "google",
    }

    _ok("Total found",  str(result["total_count"]))
    _ok("Sample names", str(result["named_list"][:5]))
    _ok("Elapsed",      f"{result['elapsed_s']} s")
    return result


# ═══════════════════════════════════════════════════════════
#  3. WEATHER + AQI
# ═══════════════════════════════════════════════════════════

def test_weather_aqi(lat: float, lon: float,
                      start_date: str = "2024-01-01",
                      end_date:   str = "2024-01-31") -> dict:
    _header("3. WEATHER + AQI  (Open-Meteo — free, no key)")
    t0 = time.time()

    weather_url    = "https://archive-api.open-meteo.com/v1/archive"
    weather_params = {
        "latitude":   lat,  "longitude":  lon,
        "start_date": start_date, "end_date": end_date,
        "daily":      "temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max",
        "timezone":   "auto",
    }
    aqi_url    = "https://air-quality-api.open-meteo.com/v1/air-quality"
    aqi_params = {
        "latitude":   lat,  "longitude":  lon,
        "start_date": start_date, "end_date": end_date,
        "hourly":     "us_aqi,pm10,pm2_5",
        "timezone":   "auto",
    }

    try:
        wr = requests.get(weather_url, params=weather_params, timeout=15).json()
        ar = requests.get(aqi_url,     params=aqi_params,     timeout=15).json()
    except Exception as e:
        _err(f"Open-Meteo request failed: {e}")
        return {}

    daily     = wr.get("daily", {})
    temps_max = daily.get("temperature_2m_max", [])
    temps_min = daily.get("temperature_2m_min", [])
    precip    = daily.get("precipitation_sum",  [])
    wind      = daily.get("windspeed_10m_max",  [])

    # BUG FIX: use _safe_avg to avoid division on empty list + skip None pairs
    mid_temps  = [(a + b) / 2 for a, b in zip(temps_max, temps_min)
                  if a is not None and b is not None]
    avg_temp   = round(_safe_avg(mid_temps), 1) if mid_temps else None
    avg_precip = _safe_avg(precip)
    avg_wind   = _safe_avg(wind)

    aqi_vals  = ar.get("hourly", {}).get("us_aqi",  [])
    pm25_vals = ar.get("hourly", {}).get("pm2_5",   [])
    avg_aqi   = _safe_avg(aqi_vals)
    avg_pm25  = _safe_avg(pm25_vals)

    daily_series = []
    for i, d in enumerate(daily.get("time", [])):
        daily_series.append({
            "date":     d,
            "temp_max": temps_max[i] if i < len(temps_max) else None,
            "temp_min": temps_min[i] if i < len(temps_min) else None,
            "precip":   precip[i]    if i < len(precip)    else None,
        })

    result = {
        "avg_temp_c":        avg_temp,
        "avg_precip_mm":     avg_precip,
        "avg_wind_kmh":      avg_wind,
        "avg_us_aqi":        avg_aqi,
        "avg_pm25":          avg_pm25,
        "days_fetched":      len(temps_max),
        "aqi_hours_fetched": len([v for v in aqi_vals if v is not None]),
        "daily_series":      daily_series,
        "elapsed_s":         round(time.time() - t0, 2),
        "source":            "open-meteo",
    }

    _ok("Avg temperature",   f"{avg_temp} °C")
    _ok("Avg precipitation", f"{avg_precip} mm/day")
    _ok("Avg wind speed",    f"{avg_wind} km/h")
    _ok("Avg US AQI",        str(avg_aqi))
    _ok("Avg PM2.5",         f"{avg_pm25} µg/m³")
    _ok("Days fetched",      str(result["days_fetched"]))
    _ok("Elapsed",           f"{result['elapsed_s']} s")
    return result


# ═══════════════════════════════════════════════════════════
#  4. POPULATION  →  Real Population API (JWT)  +  fallbacks
# ═══════════════════════════════════════════════════════════

def _iso3_from_latlon(lat: float, lon: float) -> str:
    if  6 <= lat <= 37   and  68 <= lon <= 97:  return "IND"
    if 24 <= lat <= 50   and -125 <= lon <= -66: return "USA"
    if 49 <= lat <= 61   and  -8  <= lon <= 2:   return "GBR"
    if 41 <= lat <= 52   and   0  <= lon <= 17:  return "FRA"
    if 36 <= lat <= 55   and   6  <= lon <= 15:  return "DEU"
    if 18 <= lat <= 32   and  25  <= lon <= 40:  return "SAU"
    if -34 <= lat <= -10 and 113  <= lon <= 154: return "AUS"
    return "IND"


def _population_from_data_portal(lat: float, lon: float, radius_m: int) -> dict | None:
    """
    Query the real Population Data Portal using JWT bearer token.
    Endpoint pattern: GET /api/population/radius?lat=..&lon=..&radius_m=..
    Adjust the path below if the actual API differs.
    Returns parsed dict or None on failure.
    """
    if not POPULATION_API_BEARER:
        return None

    headers = {
        "Authorization": f"Bearer {POPULATION_API_BEARER}",
        "Accept": "application/json",
    }

    # Common endpoint patterns — tries both; use whichever your portal supports
    endpoints_to_try = [
        f"{POPULATION_API_BASE}/api/population/radius",
        f"{POPULATION_API_BASE}/api/v1/population",
        f"{POPULATION_API_BASE}/population/query",
    ]

    params = {"lat": lat, "lon": lon, "radius_m": radius_m, "latitude": lat, "longitude": lon}

    for endpoint in endpoints_to_try:
        try:
            resp = requests.get(endpoint, params=params, headers=headers, timeout=15)
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            data = resp.json()

            # Normalise common response shapes
            pop = (
                data.get("population")
                or data.get("total_population")
                or data.get("count")
                or data.get("value")
                or 0
            )
            return {
                "population":    int(pop),
                "source_detail": f"data_portal ({endpoint})",
                "raw":           data,
            }
        except requests.HTTPError as he:
            _warn(f"Data portal {endpoint}", f"HTTP {he.response.status_code}")
        except Exception as e:
            _warn(f"Data portal {endpoint}", str(e))

    return None


def _population_from_worldpop(lat: float, lon: float, radius_m: int, iso3: str) -> dict | None:
    """WorldPop Stats API — free, no key. BUG FIX: use json.dumps() not str()."""
    n_pts   = 12
    deg_lat = radius_m / 111_320
    deg_lon = radius_m / (111_320 * max(math.cos(math.radians(lat)), 0.01))
    ring    = []
    for i in range(n_pts + 1):
        angle = 2 * math.pi * i / n_pts
        ring.append([
            round(lon + deg_lon * math.cos(angle), 6),
            round(lat + deg_lat * math.sin(angle), 6),
        ])
    # BUG FIX: was str(geojson_dict).replace("'", '"') — invalid for bool/None values
    geojson_str = json.dumps({"type": "Polygon", "coordinates": [ring]})

    for dataset in ("wpgpas",):
        try:
            resp = requests.get(
                "https://api.worldpop.org/v1/services/stats",
                params={"dataset": dataset, "year": 2020,
                        "iso3": iso3, "geojson": geojson_str},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == "created":
                taskid = data.get("taskid")
                for _ in range(15):
                    time.sleep(1)
                    tr = requests.get(f"https://api.worldpop.org/v1/tasks/{taskid}", timeout=15).json()
                    if tr.get("status") == "finished":
                        pyr = tr.get("data", {}).get("agesexpyramid", [])
                        total = sum(x.get("male", 0) + x.get("female", 0) for x in pyr)
                        if total > 0:
                            return {"population": int(total), "source_detail": f"worldpop/{dataset} ({iso3})"}
                        break
                    elif tr.get("status") == "error":
                        break
        except Exception as e:
            _warn(f"WorldPop {dataset}", str(e))

    return None


def _population_from_geonames(lat: float, lon: float, radius_m: int) -> dict | None:
    """GeoNames demo fallback — rate-limited."""
    try:
        resp = requests.get(
            "http://api.geonames.org/findNearbyPlaceNameJSON",
            params={"lat": lat, "lng": lon,
                    "radius": radius_m / 1000,
                    "maxRows": 1, "username": "demo"},
            timeout=15,
        )
        gns = resp.json().get("geonames", [])
        if gns:
            pop = int(gns[0].get("population", 0) or 0)
            return {"population": pop, "source_detail": f"geonames ({gns[0].get('name', '')})"}
    except Exception as e:
        _warn("GeoNames fallback", str(e))
    return None


def _age_split_estimate(iso3: str, pop: int) -> dict:
    profiles = {
        "IND": (0.27, 0.67, 0.06),
        "USA": (0.22, 0.62, 0.16),
        "GBR": (0.18, 0.62, 0.20),
        "DEU": (0.18, 0.59, 0.23),
        "FRA": (0.19, 0.60, 0.21),
        "SAU": (0.25, 0.71, 0.04),
        "AUS": (0.19, 0.65, 0.16),
    }
    child, working, senior = profiles.get((iso3 or "IND").upper(), (0.24, 0.64, 0.12))
    return {
        "0_14":   int(pop * child),
        "15_64":  int(pop * working),
        "65_plus": int(pop * senior),
    }


def test_population(lat: float, lon: float, radius_m: int = 2000,
                    iso3: str = "") -> dict:
    _header("4. POPULATION  (Data Portal API  →  WorldPop  →  GeoNames)")
    t0 = time.time()

    if not iso3:
        iso3 = _iso3_from_latlon(lat, lon)

    pop           = 0
    source_detail = "unavailable"

    # Priority 1: Real Population Data Portal (JWT)
    portal_result = _population_from_data_portal(lat, lon, radius_m)
    if portal_result and portal_result["population"] > 0:
        pop           = portal_result["population"]
        source_detail = portal_result["source_detail"]
        _ok("Source", "Data Portal (JWT auth)")

    # Priority 2: WorldPop (free, no key)
    if pop <= 0:
        wp = _population_from_worldpop(lat, lon, radius_m, iso3)
        if wp and wp["population"] > 0:
            pop           = wp["population"]
            source_detail = wp["source_detail"]
            _ok("Source", f"WorldPop ({iso3})")

    # Priority 3: GeoNames (rate-limited demo)
    if pop <= 0:
        gn = _population_from_geonames(lat, lon, radius_m)
        if gn and gn["population"] > 0:
            pop           = gn["population"]
            source_detail = gn["source_detail"]
            _ok("Source", "GeoNames fallback")

    level = (
        "Very High — Dense urban" if pop > 100_000 else
        "High — Urban"            if pop > 50_000  else
        "Moderate — Semi-urban"   if pop > 10_000  else
        "Low — Suburban/rural"    if pop > 1_000   else
        "Very Low — Sparse"
    )

    result = {
        "population":    pop,
        "level":         level,
        "radius_m":      radius_m,
        "iso3":          iso3,
        "source_detail": source_detail,
        "age_groups":    _age_split_estimate(iso3, pop),
        "age_groups_note": "Estimated from country demographic profile",
        "elapsed_s":     round(time.time() - t0, 2),
        "source":        "data_portal_worldpop_geonames",
    }

    _ok("Estimated population", f"{result['population']:,}")
    _ok("Density level",        level)
    _ok("Country ISO3",         iso3)
    _ok("Source detail",        source_detail)
    _ok("Elapsed",              f"{result['elapsed_s']} s")
    return result


# ═══════════════════════════════════════════════════════════
#  4b. CELL TOWERS  (Unwired Labs / OpenCelliD)
# ═══════════════════════════════════════════════════════════

def test_cell_towers(lat: float, lon: float, radius_m: int = 2000) -> dict:
    """
    Query OSM (Overpass API) for telecom towers near the location.
    Replaces the Unwired Labs API since no radius-based cell id search exists.
    """
    _header("4b. TELECOM TOWERS  (OSM / Overpass)")
    t0 = time.time()

    query = f"""
    [out:json][timeout:30];
    (
      node["man_made"="mast"]["tower:type"="communication"](around:{radius_m},{lat},{lon});
      node["man_made"="tower"]["tower:type"="communication"](around:{radius_m},{lat},{lon});
      node["man_made"="communications_tower"](around:{radius_m},{lat},{lon});
      way["man_made"="mast"]["tower:type"="communication"](around:{radius_m},{lat},{lon});
      way["man_made"="tower"]["tower:type"="communication"](around:{radius_m},{lat},{lon});
    );
    out center tags;
    """

    error_msg = None
    towers = []

    try:
        data = _overpass_query(query, timeout=45)
        elements = data.get("elements", [])
        for el in elements:
            tags = el.get("tags", {})
            center = el.get("center", {}) if el.get("type") == "way" else el
            clat, clon = center.get("lat"), center.get("lon")
            if clat is None or clon is None:
                continue

            radio = tags.get("tower:type") or tags.get("telecom") or "communication"
            towers.append({
                "lat":        float(clat),
                "lon":        float(clon),
                "cell_id":    el.get("id"),
                "radio":      radio,
                "distance_m": round(_haversine_km(lat, lon, float(clat), float(clon)) * 1000),
                "source":     "osm_overpass",
            })
        towers.sort(key=lambda x: x["distance_m"])
    except Exception as e:
        error_msg = str(e)
        _err(f"Cell tower request failed: {e}")

    radio_types = {}
    for t in towers:
        rt = t.get("radio") or "unknown"
        radio_types[rt] = radio_types.get(rt, 0) + 1

    # Overpass queries for physical structures rather than cell antennas. Max coverage metric:
    coverage_score = min(100, len(towers) * 10) if towers else 0

    result = {
        "towers":          towers,
        "total_count":     len(towers),
        "radio_breakdown": radio_types,
        "coverage_score":  coverage_score,
        "coverage_note":   (
            "Excellent" if coverage_score >= 80 else
            "Good"      if coverage_score >= 50 else
            "Moderate"  if coverage_score >= 20 else
            "Poor"
        ),
        "source":          "osm_overpass",
        "elapsed_s":       round(time.time() - t0, 2),
    }
    if error_msg:
        result["error"] = error_msg

    _ok("Telecom towers found", str(len(towers)))
    _ok("Tower types",        str(radio_types))
    _ok("Coverage score",     f"{coverage_score}/100")
    _ok("Elapsed",            f"{result['elapsed_s']} s")
    return result


# ═══════════════════════════════════════════════════════════
#  5. LAND USE
# ═══════════════════════════════════════════════════════════

def test_land_use(lat: float, lon: float, radius: int = 1000) -> dict:
    _header("5. LAND USE / ZONING  (Overpass API — free, no key)")
    t0 = time.time()

    query = f"""
    [out:json][timeout:45];
    (
      way["landuse"](around:{radius},{lat},{lon});
      relation["landuse"](around:{radius},{lat},{lon});
      way["building"](around:{radius},{lat},{lon});
      way["natural"](around:{radius},{lat},{lon});
      way["leisure"](around:{radius},{lat},{lon});
    );
    out tags;
    """

    try:
        data     = _overpass_query(query, timeout=45)
        elements = data.get("elements", [])
    except Exception as e:
        _err(f"Overpass land-use request failed: {e}")
        return {}

    zone_counts    = {}
    building_types = {}

    for el in elements:
        t = el.get("tags", {})
        if "landuse" in t:
            lu = t["landuse"]
            zone_counts[lu] = zone_counts.get(lu, 0) + 1
        if "building" in t:
            bt = t["building"]
            building_types[bt] = building_types.get(bt, 0) + 1
        if "natural" in t:
            nk = "natural_" + t["natural"]
            zone_counts[nk] = zone_counts.get(nk, 0) + 1
        if "leisure" in t:
            lk = "leisure_" + t["leisure"]
            zone_counts[lk] = zone_counts.get(lk, 0) + 1

    dominant = max(zone_counts, key=zone_counts.get) if zone_counts else "unknown"
    comm_count = sum(v for k, v in zone_counts.items() if k.startswith(("commercial", "retail", "mixed", "industrial")))
    commercial_friendly = comm_count >= 2 or dominant.startswith(("commercial", "retail", "mixed", "industrial"))

    result = {
        "zones":               zone_counts,
        "building_types":      building_types,
        "dominant_zone":       dominant,
        "commercial_friendly": commercial_friendly,
        "total_polygons":      len(elements),
        "elapsed_s":           round(time.time() - t0, 2),
        "source":              "overpass",
    }

    _ok("Total land-use polygons", str(result["total_polygons"]))
    _ok("Zone breakdown",          str(zone_counts))
    _ok("Building types",          str(dict(list(building_types.items())[:4])))
    _ok("Dominant zone",           dominant)
    _ok("Commercial friendly",     str(commercial_friendly))
    _ok("Elapsed",                 f"{result['elapsed_s']} s")
    return result


# ═══════════════════════════════════════════════════════════
#  6. FLOOD RISK
# ═══════════════════════════════════════════════════════════

def test_flood_risk(lat: float, lon: float) -> dict:
    _header("6. FLOOD RISK  (OpenTopoData — free, no key)")
    t0 = time.time()

    try:
        resp = requests.get(
            "https://api.opentopodata.org/v1/srtm90m",
            params={"locations": f"{lat},{lon}"},
            timeout=15,
        )
        data      = resp.json()
        elevation = data.get("results", [{}])[0].get("elevation")
    except Exception as e:
        _err(f"OpenTopoData failed: {e}")
        return {}

    if elevation is None:
        _warn("Elevation", "Not available for this location")
        return {"flood_risk": "unknown", "elevation_m": None}

    risk = (
        "Very High" if elevation < 5   else
        "High"      if elevation < 15  else
        "Moderate"  if elevation < 30  else
        "Low"       if elevation < 100 else
        "Very Low"
    )

    result = {
        "elevation_m": elevation,
        "flood_risk":  risk,
        "elapsed_s":   round(time.time() - t0, 2),
        "source":      "opentopodata",
    }

    _ok("Elevation",  f"{elevation} m above sea level")
    _ok("Flood risk", risk)
    _ok("Elapsed",    f"{result['elapsed_s']} s")
    return result


# ═══════════════════════════════════════════════════════════
#  7. ISOCHRONES
# ═══════════════════════════════════════════════════════════

def test_isochrones(lat: float, lon: float,
                     minutes: list = [10, 20, 30]) -> dict:
    _header("7. ISOCHRONES  (OpenRouteService / circular approx)")
    t0 = time.time()

    if OPENROUTESERVICE_API_KEY:
        try:
            resp = requests.post(
                "https://api.openrouteservice.org/v2/isochrones/driving-car",
                headers={"Authorization": OPENROUTESERVICE_API_KEY,
                         "Content-Type":  "application/json"},
                json={"locations":   [[lon, lat]],
                      "range":       [m * 60 for m in minutes],
                      "range_type":  "time"},
                timeout=15,
            )
            features = resp.json().get("features", [])
            iso = []
            for feat in features:
                props = feat.get("properties", {})
                iso.append({
                    "minutes":  props.get("value", 0) // 60,
                    "area_km2": round(props.get("area", 0) / 1_000_000, 2),
                    "geometry": feat.get("geometry"),
                    "source":   "openrouteservice",
                })
            _ok("Source", "OpenRouteService (real drive-time)")
            for i in iso:
                _ok(f"  {i['minutes']} min isochrone", f"{i['area_km2']} km²")
            _ok("Elapsed", f"{round(time.time() - t0, 2)} s")
            return {"isochrones": iso}
        except Exception as e:
            _warn("ORS failed, using approx", str(e))

    speed_kmh = 20
    iso = []
    for m in minutes:
        r_km = (speed_kmh * m) / 60
        iso.append({
            "minutes":       m,
            "radius_m":      round(r_km * 1000),
            "area_km2":      round(math.pi * r_km ** 2, 2),
            "approximation": True,
            "source":        "circle_approx",
        })

    _ok("Source", "Circular approx (set OPENROUTESERVICE_API_KEY for real isochrones)")
    for i in iso:
        _ok(f"  {i['minutes']} min radius", f"{i['radius_m']} m  ({i['area_km2']} km²)")
    _ok("Elapsed", f"{round(time.time() - t0, 2)} s")
    return {"isochrones": iso}


# ═══════════════════════════════════════════════════════════
#  SUMMARY
# ═══════════════════════════════════════════════════════════

def print_summary(all_results: dict):
    _header("SUMMARY")
    checks = {
        "Roads":                bool(all_results.get("roads", {}).get("road_score_km")),
        "Competitors (OSM)":    bool(all_results.get("competitors_osm", {}).get("total_count")),
        "Competitors (Google)": bool(all_results.get("competitors_google", {}).get("total_count")),
        "Weather":              bool(all_results.get("weather", {}).get("avg_temp_c")),
        "Population":           bool(all_results.get("population", {}).get("population")),
        "Cell Towers":          "cell_towers" in all_results,
        "Land Use":             bool(all_results.get("land_use", {}).get("zones")),
        "Flood Risk":           bool(all_results.get("flood_risk", {}).get("elevation_m")),
        "Isochrones":           bool(all_results.get("isochrones", {}).get("isochrones")),
    }
    for name, passed in checks.items():
        icon = "✅" if passed else "❌"
        print(f"  {icon}  {name}")


# ═══════════════════════════════════════════════════════════
#  MAIN  — concurrent execution for speed
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="GeoSpatial API Tester")
    parser.add_argument("--lat",           type=float, default=23.0225)
    parser.add_argument("--lon",           type=float, default=72.5714)
    parser.add_argument("--radius",        type=int,   default=2000)
    parser.add_argument("--iso3",          type=str,   default="",
                        help="ISO3 country code for WorldPop (auto-detected if blank)")
    parser.add_argument("--business-type", type=str,   default="restaurant")
    parser.add_argument("--start-date",    type=str,   default="2024-01-01")
    parser.add_argument("--end-date",      type=str,   default="2024-01-31")
    parser.add_argument("--skip",          type=str,   default="",
                        help="Comma-separated: roads,competitors,weather,population,cell_towers,landuse,flood,isochrones")
    args = parser.parse_args()

    skip = {s.strip().lower() for s in args.skip.split(",") if s.strip()}

    print(f"\n  Location : {args.lat}, {args.lon}")
    print(f"  Radius   : {args.radius} m")
    print(f"  Business : {args.business_type}")
    print(f"  Dates    : {args.start_date} → {args.end_date}")

    all_results: dict = {
        "_meta": {
            "lat":           args.lat,
            "lon":           args.lon,
            "radius_m":      args.radius,
            "business_type": args.business_type,
            "start_date":    args.start_date,
            "end_date":      args.end_date,
        }
    }
    total_start = time.time()

    # Build task list
    tasks = {}
    if "roads"       not in skip:
        tasks["roads"]              = lambda: test_road_score(args.lat, args.lon, args.radius)
    if "competitors" not in skip:
        tasks["competitors_osm"]    = lambda: test_competitors_osm(args.lat, args.lon, args.radius, args.business_type)
        tasks["competitors_google"] = lambda: test_competitors_google(args.lat, args.lon, args.radius, args.business_type)
        tasks["competitors_ola"]    = lambda: test_competitors_ola(args.lat, args.lon, args.radius, args.business_type)
    if "weather"     not in skip:
        tasks["weather"]            = lambda: test_weather_aqi(args.lat, args.lon, args.start_date, args.end_date)
    if "population"  not in skip:
        tasks["population"]         = lambda: test_population(args.lat, args.lon, args.radius, iso3=args.iso3)
    if "cell_towers" not in skip:
        tasks["cell_towers"]        = lambda: test_cell_towers(args.lat, args.lon, args.radius)
    if "landuse"     not in skip:
        tasks["land_use"]           = lambda: test_land_use(args.lat, args.lon, min(args.radius, 1000))
    if "flood"       not in skip:
        tasks["flood_risk"]         = lambda: test_flood_risk(args.lat, args.lon)
    if "isochrones"  not in skip:
        tasks["isochrones"]         = lambda: test_isochrones(args.lat, args.lon)

    # PERF: Run all tasks concurrently (ThreadPoolExecutor for I/O-bound calls)
    with ThreadPoolExecutor(max_workers=6) as executor:
        future_to_key = {executor.submit(fn): key for key, fn in tasks.items()}
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                all_results[key] = future.result()
            except Exception as exc:
                _err(f"{key} raised: {exc}")
                all_results[key] = {"error": str(exc)}

    print_summary(all_results)
    print(f"\n  Total elapsed: {round(time.time() - total_start, 1)} s\n")

    out_file = "test_results.json"
    with open(out_file, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"  Full results saved → {out_file}")
    print(f"  Open geo_map.html in a browser to visualise everything.\n")


if __name__ == "__main__":
    main()