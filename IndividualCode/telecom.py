"""
find_towers_ev.py  ── v3  (Google Places API New + OSM fallback)
═══════════════════════════════════════════════════════════════════
Find Telecom Towers and EV Charging Stations near any coordinate.

FIXES in v3:
  • EV >20 results: Nearby Search (New) has NO pagination — we tile
    the search radius into a grid of overlapping sub-circles (each
    ≤50 km) so every 20-result cell covers a small area, giving
    full coverage across the whole radius.
  • Towers HTTP 400: Text Search requires locationBias (not
    locationRestriction) for circle-based queries. Fixed + added
    correct includedType filter where possible.

Usage:
    python find_towers_ev.py

    Set key as env var to skip the prompt:
        set GOOGLE_PLACES_API_KEY=AIza...   (Windows)
        export GOOGLE_PLACES_API_KEY=AIza...  (Linux/Mac)
"""

import os, sys, json, math, time, requests
from datetime import datetime

# ── Endpoints ─────────────────────────────────────────
NEARBY_URL   = "https://places.googleapis.com/v1/places:searchNearby"
TEXT_URL     = "https://places.googleapis.com/v1/places:searchText"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

GOOGLE_MAX_RADIUS = 50_000   # hard API limit in metres
TIMEOUT = 25

# ── Field masks ────────────────────────────────────────
EV_FIELDS = ",".join([
    "places.id", "places.displayName", "places.formattedAddress",
    "places.location", "places.primaryType", "places.types",
    "places.rating", "places.userRatingCount",
    "places.regularOpeningHours", "places.nationalPhoneNumber",
    "places.websiteUri", "places.evChargeOptions", "places.googleMapsUri",
])

TOWER_FIELDS = ",".join([
    "places.id", "places.displayName", "places.formattedAddress",
    "places.location", "places.primaryType", "places.types",
    "places.rating", "places.userRatingCount",
    "places.nationalPhoneNumber", "places.websiteUri", "places.googleMapsUri",
])


# ══════════════════════════════════════════════════════
#  GEOMETRY HELPERS
# ══════════════════════════════════════════════════════
def haversine(lat1, lon1, lat2, lon2):
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin(math.radians(lat2-lat1)/2)**2
         + math.cos(p1)*math.cos(p2)*math.sin(math.radians(lon2-lon1)/2)**2)
    return round(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))


def offset_point(lat, lon, bearing_deg, distance_m):
    """Return (lat, lon) moved `distance_m` metres in `bearing_deg` direction."""
    R = 6_371_000
    d = distance_m / R
    b = math.radians(bearing_deg)
    lat1, lon1 = math.radians(lat), math.radians(lon)
    lat2 = math.asin(math.sin(lat1)*math.cos(d) + math.cos(lat1)*math.sin(d)*math.cos(b))
    lon2 = lon1 + math.atan2(math.sin(b)*math.sin(d)*math.cos(lat1),
                              math.cos(d) - math.sin(lat1)*math.sin(lat2))
    return math.degrees(lat2), math.degrees(lon2)


def build_grid(centre_lat, centre_lon, total_radius_m, cell_radius_m):
    """
    Tile the search area with overlapping circles of radius `cell_radius_m`.
    Returns list of (lat, lon) centre points.
    The overlap factor (√2 step) ensures no gaps between cells.
    """
    step = cell_radius_m * math.sqrt(2)   # diagonal = step for square grid
    cells = set()
    cells.add((centre_lat, centre_lon))

    rings = math.ceil(total_radius_m / step)
    for ring in range(1, rings + 1):
        ring_r = ring * step
        # Place cells evenly around this ring
        circumference = 2 * math.pi * ring_r
        n_cells = max(6, math.ceil(circumference / step))
        for i in range(n_cells):
            bearing = 360 * i / n_cells
            clat, clon = offset_point(centre_lat, centre_lon, bearing, ring_r)
            # Only keep cells whose centre is within total_radius + cell_radius
            if haversine(centre_lat, centre_lon, clat, clon) <= total_radius_m + cell_radius_m:
                cells.add((round(clat, 6), round(clon, 6)))

    return list(cells)


# ══════════════════════════════════════════════════════
#  GOOGLE API CALLS
# ══════════════════════════════════════════════════════
def _post(url, api_key, body, field_mask):
    resp = requests.post(
        url, json=body,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": field_mask,
        },
        timeout=TIMEOUT,
    )
    if not resp.ok:
        raise requests.HTTPError(
            f"HTTP {resp.status_code}: {resp.text[:300]}", response=resp
        )
    return resp.json()


# ── EV Stations: tiled Nearby Search ──────────────────
def fetch_ev_google(api_key, centre_lat, centre_lon, total_radius_m):
    """
    Tile the area into sub-circles (≤10 km each) and run one Nearby Search
    per cell. Deduplicates by place ID. Returns raw place dicts.
    """
    # Choose cell radius:
    #   Small radius → more cells → more API calls but denser coverage
    #   Large radius → fewer calls → may miss places if >20 per cell
    # 5 km cells give good density vs call count balance.
    cell_r = min(5_000, total_radius_m)
    cells  = build_grid(centre_lat, centre_lon, total_radius_m, cell_r)

    print(f"     Grid: {len(cells)} search cell(s) × 20 results = up to "
          f"{len(cells)*20} candidates")

    seen, results = set(), []

    for idx, (clat, clon) in enumerate(cells, 1):
        body = {
            "includedTypes": ["electric_vehicle_charging_station"],
            "maxResultCount": 20,
            "rankPreference": "DISTANCE",
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": clat, "longitude": clon},
                    "radius": float(cell_r),
                }
            },
        }
        try:
            data = _post(NEARBY_URL, api_key, body, EV_FIELDS)
            for p in data.get("places", []):
                pid = p.get("id", "")
                if pid and pid not in seen:
                    seen.add(pid)
                    results.append(p)
        except requests.HTTPError as e:
            print(f"     ⚠  Cell {idx}/{len(cells)} error: {e}")
        if idx < len(cells):
            time.sleep(0.15)   # stay within QPS limits

    return results


# ── Telecom Towers: Text Search with locationBias ──────
TOWER_QUERIES = [
    "telecom tower",
    "cell tower",
    "mobile tower BTS",
    "communication tower",
    "antenna mast tower",
    "Jio tower",
    "Airtel tower",
    "BSNL tower",
]


def fetch_towers_google(api_key, centre_lat, centre_lon, total_radius_m):
    """
    Use Text Search (New) with locationBias circle.
    Key fix: Text Search uses locationBias (not locationRestriction) for circles.
    Also tries Nearby Search with includedTypes that may catch some towers.
    """
    bias_radius = min(total_radius_m, GOOGLE_MAX_RADIUS)
    seen, results = set(), []

    # ── Method 1: Text Search with keyword queries ──
    for query in TOWER_QUERIES:
        body = {
            "textQuery": query,
            "pageSize": 20,
            "locationBias": {              # ← must be locationBias, NOT locationRestriction
                "circle": {
                    "center": {"latitude": centre_lat, "longitude": centre_lon},
                    "radius": float(bias_radius),
                }
            },
        }
        try:
            data = _post(TEXT_URL, api_key, body, TOWER_FIELDS)
            added = 0
            for p in data.get("places", []):
                pid = p.get("id", "")
                # Filter: only keep results within our actual radius
                loc = p.get("location", {})
                plat, plon = loc.get("latitude"), loc.get("longitude")
                if plat and plon:
                    dist = haversine(centre_lat, centre_lon, plat, plon)
                    if dist > total_radius_m:
                        continue
                if pid and pid not in seen:
                    seen.add(pid)
                    results.append(p)
                    added += 1
            print(f"     '{query}' → {added} new result(s)")
        except requests.HTTPError as e:
            print(f"     ⚠  '{query}' failed: {e}")
        time.sleep(0.2)

    # ── Method 2: Nearby Search for infrastructure types ──
    infra_types = [
        ["transit_station"],           # sometimes catches tower sites
        ["telecommunications_service_provider"],  # if supported
    ]
    cell_r = min(total_radius_m, GOOGLE_MAX_RADIUS)

    for types in infra_types:
        body = {
            "includedTypes": types,
            "maxResultCount": 20,
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": centre_lat, "longitude": centre_lon},
                    "radius": float(cell_r),
                }
            },
        }
        try:
            data = _post(NEARBY_URL, api_key, body, TOWER_FIELDS)
            for p in data.get("places", []):
                pid = p.get("id", "")
                if pid and pid not in seen:
                    seen.add(pid)
                    results.append(p)
        except requests.HTTPError:
            pass   # silently skip unsupported types
        time.sleep(0.1)

    return results


# ══════════════════════════════════════════════════════
#  PARSE GOOGLE PLACE → CLEAN RECORD
# ══════════════════════════════════════════════════════
def parse_place(raw, centre_lat, centre_lon, kind):
    loc  = raw.get("location", {})
    plat = loc.get("latitude")
    plon = loc.get("longitude")
    dist = haversine(centre_lat, centre_lon, plat, plon) if plat and plon else None

    rec = {
        "source":       "Google Places",
        "place_id":     raw.get("id", ""),
        "name":         raw.get("displayName", {}).get("text", "(unnamed)"),
        "address":      raw.get("formattedAddress", ""),
        "lat":          plat,
        "lon":          plon,
        "distance_m":   dist,
        "primary_type": raw.get("primaryType", ""),
        "types":        raw.get("types", []),
        "rating":       raw.get("rating"),
        "rating_count": raw.get("userRatingCount"),
        "phone":        raw.get("nationalPhoneNumber", ""),
        "website":      raw.get("websiteUri", ""),
        "google_maps_url": raw.get("googleMapsUri", ""),
    }

    if kind == "ev":
        ev   = raw.get("evChargeOptions", {})
        rec["ev_connector_count"] = ev.get("connectorCount")
        rec["ev_connectors"] = [
            {
                "type":      c.get("type","").replace("EV_CONNECTOR_TYPE_",""),
                "count":     c.get("count"),
                "max_kw":    c.get("maxChargeRateKw"),
                "available": c.get("availableCount"),
                "out_of_service": c.get("outOfServiceCount"),
            }
            for c in ev.get("connectorAggregation", [])
        ]
        oh = raw.get("regularOpeningHours", {})
        rec["open_now"]     = oh.get("openNow")
        rec["opening_hours"]= oh.get("weekdayDescriptions", [])

    return rec


# ══════════════════════════════════════════════════════
#  OSM OVERPASS FALLBACK
# ══════════════════════════════════════════════════════
def fetch_osm(lat, lon, radius_m, want_towers, want_ev):
    circle = f"(around:{radius_m},{lat},{lon})"
    parts  = []

    if want_towers:
        for tag in [
            '["man_made"="mast"]["tower:type"="communication"]',
            '["man_made"="tower"]["tower:type"="communication"]',
            '["man_made"="communications_tower"]',
            '["telecom"]',
        ]:
            parts += [f"node{tag}{circle};", f"way{tag}{circle};"]

    if want_ev:
        parts += [
            f'node["amenity"="charging_station"]{circle};',
            f'way["amenity"="charging_station"]{circle};',
        ]

    query = f"[out:json][timeout:40];\n(\n  {''.join(parts)}\n);\nout center tags;"
    resp  = requests.post(OVERPASS_URL, data={"data": query}, timeout=45)
    resp.raise_for_status()

    towers, ev_list = [], []
    for elem in resp.json().get("elements", []):
        if elem["type"] == "node":
            elat, elon = elem.get("lat"), elem.get("lon")
        else:
            c = elem.get("center", {})
            elat, elon = c.get("lat"), c.get("lon")
        if elat is None:
            continue

        tags = elem.get("tags", {})
        dist = haversine(lat, lon, elat, elon)
        rec  = {
            "source":       "OpenStreetMap",
            "place_id":     f"{elem['type']}/{elem['id']}",
            "name":         tags.get("name") or tags.get("operator") or "(unnamed)",
            "address":      "",
            "lat": elat, "lon": elon, "distance_m": dist,
            "primary_type": tags.get("man_made") or tags.get("amenity",""),
            "types": [],
            "rating": None, "rating_count": None,
            "phone":   tags.get("phone",""),
            "website": tags.get("website",""),
            "google_maps_url": f"https://www.google.com/maps?q={elat},{elon}",
        }

        if tags.get("amenity") == "charging_station" and want_ev:
            rec.update({
                "ev_connector_count": tags.get("capacity"),
                "ev_connectors": [],
                "open_now": None,
                "opening_hours": [tags.get("opening_hours","")],
            })
            ev_list.append(rec)
        elif want_towers:
            towers.append(rec)

    towers.sort(key=lambda x: x["distance_m"])
    ev_list.sort(key=lambda x: x["distance_m"])
    return towers, ev_list


# ══════════════════════════════════════════════════════
#  ORCHESTRATOR
# ══════════════════════════════════════════════════════
def search_all(api_key, lat, lon, radius_m, want_towers, want_ev):
    towers, ev_list         = [], []
    google_towers_ok        = False
    google_ev_ok            = False

    if api_key:
        # ── EV Stations ──
        if want_ev:
            print("\n  ⚡  Fetching EV stations (Google Nearby Search — tiled grid) …")
            try:
                raw     = fetch_ev_google(api_key, lat, lon, radius_m)
                ev_list = [parse_place(p, lat, lon, "ev") for p in raw]
                # Keep only results inside actual requested radius
                ev_list = [r for r in ev_list
                           if r["distance_m"] is None or r["distance_m"] <= radius_m]
                ev_list.sort(key=lambda x: x.get("distance_m") or 0)
                google_ev_ok = True
                print(f"     ✔  {len(ev_list)} unique EV station(s) within radius")
            except Exception as e:
                print(f"     ⚠  Failed: {e}")

        # ── Telecom Towers ──
        if want_towers:
            print("\n  📡  Fetching telecom towers (Google Text Search) …")
            try:
                raw    = fetch_towers_google(api_key, lat, lon, radius_m)
                towers = [parse_place(p, lat, lon, "tower") for p in raw]
                towers = [r for r in towers
                          if r["distance_m"] is None or r["distance_m"] <= radius_m]
                towers.sort(key=lambda x: x.get("distance_m") or 0)
                google_towers_ok = True
                print(f"     ✔  {len(towers)} unique tower(s) within radius")
            except Exception as e:
                print(f"     ⚠  Failed: {e}")

    # ── OSM fallback for anything that failed ──
    need_osm_t  = want_towers and not google_towers_ok
    need_osm_ev = want_ev     and not google_ev_ok

    if need_osm_t or need_osm_ev:
        what = ("towers " if need_osm_t else "") + ("EV" if need_osm_ev else "")
        print(f"\n  🌍  OpenStreetMap fallback for: {what} …")
        try:
            osm_t, osm_ev = fetch_osm(lat, lon, radius_m, need_osm_t, need_osm_ev)
            if need_osm_t:  towers.extend(osm_t)
            if need_osm_ev: ev_list.extend(osm_ev)
            print(f"     ✔  OSM: {len(osm_t)} tower(s)  {len(osm_ev)} EV station(s)")
        except Exception as e:
            print(f"     ⚠  OSM also failed: {e}")

    # Always also run OSM for towers (supplements Google)
    if want_towers and google_towers_ok:
        print("\n  🌍  Supplementing towers with OpenStreetMap …")
        try:
            osm_t, _ = fetch_osm(lat, lon, radius_m, True, False)
            existing_coords = {(r["lat"], r["lon"]) for r in towers}
            added = 0
            for t in osm_t:
                if (t["lat"], t["lon"]) not in existing_coords:
                    towers.append(t)
                    added += 1
            print(f"     ✔  {added} additional OSM tower(s) added")
        except Exception as e:
            print(f"     ⚠  OSM supplement failed: {e}")

    towers.sort(key=lambda x: x.get("distance_m") or 999_999)
    ev_list.sort(key=lambda x: x.get("distance_m") or 999_999)
    return towers, ev_list


# ══════════════════════════════════════════════════════
#  DISPLAY
# ══════════════════════════════════════════════════════
def fmt_connectors(connectors):
    lines = []
    for c in connectors:
        ctype = c.get("type","UNKNOWN")
        s = f"{ctype} ×{c.get('count','?')}"
        if c.get("max_kw"):
            s += f" @ {c['max_kw']:.1f} kW"
        avail = c.get("available")
        if avail is not None:
            oos = c.get("out_of_service") or 0
            s += f"   [{avail} available, {oos} out-of-service]"
        lines.append(s)
    return ("\n" + " " * 22).join(lines)


def sep(char="═", n=67):
    print(char * n)


def print_results(towers, ev_list, lat, lon, save_json, prefix):
    print()

    # ── Towers ─────────────────────────────────────────
    sep(); print(f"  📡  TELECOM TOWERS  —  {len(towers)} found"); sep()
    if towers:
        for i, r in enumerate(towers, 1):
            d = f"{r['distance_m']:,} m" if r.get("distance_m") is not None else "—"
            print(f"\n  {i:>3}. {r['name']}")
            print(f"         Distance    : {d}")
            if r["address"]:
                print(f"         Address     : {r['address']}")
            print(f"         Coords      : {r['lat']:.6f}, {r['lon']:.6f}")
            if r["primary_type"]:
                print(f"         Type        : {r['primary_type']}")
            if r.get("types"):
                print(f"         All types   : {', '.join(r['types'][:5])}")
            if r.get("rating"):
                print(f"         Rating      : {r['rating']} ⭐  ({r.get('rating_count',0)} reviews)")
            if r.get("phone"):
                print(f"         Phone       : {r['phone']}")
            if r.get("website"):
                print(f"         Website     : {r['website']}")
            print(f"         Source      : {r['source']}")
            print(f"         Maps Link   : {r['google_maps_url']}")
    else:
        print("\n  No telecom towers found.")
        print("  Note: Google Maps has limited tower data — OSM data shown above if found.")

    # ── EV Stations ────────────────────────────────────
    print()
    sep(); print(f"  ⚡  EV CHARGING STATIONS  —  {len(ev_list)} found"); sep()
    if ev_list:
        for i, r in enumerate(ev_list, 1):
            d = f"{r['distance_m']:,} m" if r.get("distance_m") is not None else "—"
            open_tag = ("  🟢 OPEN"   if r.get("open_now") is True
                   else "  🔴 CLOSED" if r.get("open_now") is False
                   else "")
            print(f"\n  {i:>3}. {r['name']}{open_tag}")
            print(f"         Distance    : {d}")
            if r["address"]:
                print(f"         Address     : {r['address']}")
            print(f"         Coords      : {r['lat']:.6f}, {r['lon']:.6f}")
            if r.get("rating"):
                print(f"         Rating      : {r['rating']} ⭐  ({r.get('rating_count',0)} reviews)")
            if r.get("phone"):
                print(f"         Phone       : {r['phone']}")
            if r.get("website"):
                print(f"         Website     : {r['website']}")
            if r.get("ev_connector_count"):
                print(f"         Total ports : {r['ev_connector_count']}")
            if r.get("ev_connectors"):
                print(f"         Connectors  : {fmt_connectors(r['ev_connectors'])}")
            hours = [h for h in r.get("opening_hours", []) if h]
            if hours:
                print(f"         Hours       :")
                for h in hours:
                    print(f"                       {h}")
            print(f"         Source      : {r['source']}")
            print(f"         Maps Link   : {r['google_maps_url']}")
    else:
        print("\n  No EV charging stations found.")

    # ── Summary ────────────────────────────────────────
    print()
    sep("─")
    print(f"  TOTAL  →  {len(towers)} telecom tower(s)   |   {len(ev_list)} EV station(s)")
    sep("─")

    if save_json:
        fname = f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(fname, "w", encoding="utf-8") as f:
            json.dump({
                "meta": {"lat": lat, "lon": lon,
                         "generated": datetime.now().isoformat()},
                "telecom_towers": towers,
                "ev_stations": ev_list,
            }, f, indent=2, ensure_ascii=False)
        print(f"\n  💾  Saved → {fname}")


# ══════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════
def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║  Telecom Tower & EV Station Finder  v3                       ║
║  Primary  : Google Places API (New) — tiled grid search      ║
║  Fallback : OpenStreetMap Overpass API (free, no key)        ║
╚══════════════════════════════════════════════════════════════╝
""")

    api_key = os.environ.get("GOOGLE_PLACES_API_KEY","").strip()
    if not api_key:
        api_key = input(
            "  Google Places API key (Enter to skip → OSM only):\n  > "
        ).strip()
    print(f"\n  {'✅ Google API key loaded.' if api_key else '⚠  No key — OSM only.'}\n")

    try:
        lat = float(input("  Latitude  : ").strip())
        lon = float(input("  Longitude : ").strip())
        assert -90 <= lat <= 90 and -180 <= lon <= 180
    except (ValueError, AssertionError):
        print("  ❌ Invalid coordinates."); sys.exit(1)

    try:
        raw = input("  Radius in metres (default 10000): ").strip()
        radius_m = int(raw) if raw else 10_000
        assert 100 <= radius_m <= 200_000
    except (ValueError, AssertionError):
        print("  ❌ Radius must be 100–200,000 m."); sys.exit(1)

    print("\n  What to search for?")
    print("    1 → Telecom towers only")
    print("    2 → EV stations only")
    print("    3 → Both (default)")
    c = input("  > ").strip() or "3"
    want_towers = c in ("1","3")
    want_ev     = c in ("2","3")

    save = input("\n  Save results to JSON? [y/N]: ").strip().lower() == "y"

    # Estimate API calls for user awareness
    cell_r   = min(5_000, radius_m)
    n_cells  = len(build_grid(lat, lon, radius_m, cell_r)) if want_ev and api_key else 0
    n_tower_calls = len(TOWER_QUERIES) if want_towers and api_key else 0

    print(f"""
  ┌── Query ──────────────────────────────────────────────────┐
  │  Lat/Lon  : {lat}, {lon}
  │  Radius   : {radius_m:,} m  ({radius_m/1000:.1f} km)
  │  Find     : {"📡 Towers  " if want_towers else ""}{"⚡ EV Stations" if want_ev else ""}
  │  EV calls : {n_cells} grid cell(s) (≤{n_cells*20} candidates)
  │  Tower calls: {n_tower_calls} text queries + OSM supplement
  └───────────────────────────────────────────────────────────┘
""")

    towers, ev_list = search_all(api_key, lat, lon, radius_m, want_towers, want_ev)
    print_results(towers, ev_list, lat, lon, save, "results")


if __name__ == "__main__":
    main()