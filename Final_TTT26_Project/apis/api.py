"""FastAPI backend using latest no-hardware analysis functions.

Changelog:
    - /analyze now runs all sub-calls CONCURRENTLY (ThreadPoolExecutor)
      → latency drops from ~30-45s sequential to ~8-12s parallel
    - Integrated real Population Data Portal (JWT bearer)
    - Integrated Cell Tower API (Unwired Labs) with coverage score
    - Cell tower coverage_score feeds into composite scoring
    - Fixed WorldPop geojson bug: str() → json.dumps()
    - Fixed EONET radius: was radius_km*5, now radius_km
    - Fixed weather _safe_avg: no more division on empty lists
    - Fixed _google_place_autocomplete: concurrent detail fetches
    - Fixed weight validation: raises 400 if all weights are 0
    - Fixed _age_split: added SAU/AUS profiles, used in api.py too
"""

import os
import time
import math
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from no_hardware_backend import (
    OSM_BUSINESS_TAGS,
    OPENCAGE_API_KEY,
    OPENROUTESERVICE_API_KEY,
    FOURSQUARE_API_KEY,
    GOOGLE_PLACES_API_KEY,
    CELL_TOWER_API_KEY,
    POPULATION_API_BEARER,
    test_road_score,
    test_competitors_osm,
    test_competitors_google,
    test_competitors_ola,
    _is_india,
    test_weather_aqi,
    test_population,
    test_cell_towers,
    test_land_use,
    test_flood_risk,
    test_isochrones,
    _overpass_query,
    _haversine_km,
    _age_split_estimate,
    _population_from_data_portal,
    _population_from_worldpop,
    _population_from_geonames,
    _iso3_from_latlon,
    _safe_avg,
)


def _osm_name_en(tags: Optional[dict]) -> str:
    """Prefer English names from OSM (`name:en`) for UI consistency."""
    if not tags:
        return ""
    return (tags.get("name:en") or tags.get("name") or "").strip()


app = FastAPI(
    title="GeoSpatial Site Readiness Analyzer",
    version="1.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalysisRequest(BaseModel):
    lat: float
    lon: float
    radius: int = 2000
    run_roads: bool = True
    run_competitors: bool = True
    run_weather: bool = True
    run_population: bool = True
    run_cell_towers: bool = False   # NEW
    business_type: Optional[str] = "restaurant"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    competitor_source: str = "osm"
    run_telecom_towers: bool = False
    run_ev_stations: bool = False
    weight_roads: float = 0.20
    weight_competitors: float = 0.20
    weight_weather: float = 0.15
    weight_population: float = 0.25
    weight_cell_coverage: float = 0.10  # NEW — only used when run_cell_towers=True
    weight_land_use: float = 0.10       # NEW — rewards commercial zones

    @field_validator("lat")
    @classmethod
    def validate_lat(cls, v):
        if not (-90 <= v <= 90):
            raise ValueError("lat must be between -90 and 90")
        return v

    @field_validator("lon")
    @classmethod
    def validate_lon(cls, v):
        if not (-180 <= v <= 180):
            raise ValueError("lon must be between -180 and 180")
        return v

    @field_validator("radius")
    @classmethod
    def validate_radius(cls, v):
        if not (100 <= v <= 50000):
            raise ValueError("radius must be between 100 and 50000 m")
        return v


def _rating(score: float) -> str:
    if score >= 80:
        return "Excellent"
    if score >= 60:
        return "Good"
    if score >= 40:
        return "Moderate"
    return "Poor"


def _score(results: dict, req: AnalysisRequest) -> dict:
    roads = results.get("roads", {}).get("road_score_km", 0) or 0
    comps = results.get("competitors", {}).get("total_count", 0) or 0
    aqi   = results.get("weather", {}).get("avg_us_aqi")
    pop   = results.get("population", {}).get("population", 0) or 0

    road_score = min(100.0, (roads / 50.0) * 100.0)

    if comps == 0:
        comp_score = 40.0
    elif comps <= 20:
        comp_score = 80.0
    elif comps <= 50:
        comp_score = 60.0
    else:
        comp_score = 35.0

    weather_score = 60.0 if aqi is None else max(0.0, min(100.0, 110.0 - float(aqi)))
    pop_score     = min(100.0, (pop / 200_000.0) * 100.0) if pop else 15.0

    # NEW: Cell tower coverage score (0-100 from API)
    cell_score = results.get("cell_towers", {}).get("coverage_score", 0) or 0

    # NEW: Land use commercial score
    land_use = results.get("land_use", {})
    dominant = land_use.get("dominant_zone", "")
    commercial_friendly = land_use.get("commercial_friendly", False)
    land_score = 80.0 if commercial_friendly else (
        50.0 if dominant in ("residential", "retail") else 30.0
    )

    sub = {
        "roads":         round(road_score,    1),
        "competitors":   round(comp_score,    1),
        "weather":       round(weather_score, 1),
        "population":    round(pop_score,     1),
        "cell_coverage": round(cell_score,    1),
        "land_use":      round(land_score,    1),
    }

    weights = {
        "roads":         req.weight_roads,
        "competitors":   req.weight_competitors,
        "weather":       req.weight_weather,
        "population":    req.weight_population,
        "cell_coverage": req.weight_cell_coverage if req.run_cell_towers else 0.0,
        "land_use":      req.weight_land_use,
    }

    total_w = sum(weights.values())
    # BUG FIX: raise error instead of silently returning 0 when weights all zero
    if total_w <= 0:
        raise ValueError("All scoring weights are zero — check weight_* parameters")

    weighted_sum = sum(sub[k] * weights[k] for k in sub)
    composite    = round(weighted_sum / total_w, 1)

    return {
        "composite_score": composite,
        "rating":          _rating(composite),
        "sub_scores":      sub,
        "weights_used":    {k: v for k, v in weights.items() if v > 0},
    }


OLA_MAPS_API_KEY = os.getenv("OLA_MAPS_API_KEY", os.getenv("KRUTRIM_API_KEY", ""))

def _geocode_olamaps(query: str) -> list:
    if not OLA_MAPS_API_KEY:
        return []
    try:
        resp = requests.get(
            "https://api.olamaps.io/places/v1/geocode",
            params={"address": query, "api_key": OLA_MAPS_API_KEY},
            timeout=15
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        results = data.get("geocodingResults", [])
        out = []
        for row in results:
            geom = row.get("geometry", {}).get("location", {})
            if geom.get("lat") and geom.get("lng"):
                out.append({
                    "lat": float(geom["lat"]),
                    "lon": float(geom["lng"]),
                    "display_name": row.get("formatted_address", ""),
                    "source": "ola_maps"
                })
        return out
    except Exception:
        return []

def _olamaps_autocomplete(query: str) -> list:
    if not OLA_MAPS_API_KEY:
        return []
    try:
        resp = requests.get(
            "https://api.olamaps.io/places/v1/autocomplete",
            params={"input": query, "api_key": OLA_MAPS_API_KEY},
            timeout=15
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        out = []
        for row in data.get("predictions", []):
            loc = row.get("geometry", {}).get("location", {})
            if loc.get("lat") and loc.get("lng"):
                out.append({
                    "lat": float(loc["lat"]),
                    "lon": float(loc["lng"]),
                    "display_name": row.get("description", ""),
                    "source": "ola_maps"
                })
        return out
    except Exception:
        return []


def _geocode_nominatim(query: str) -> list:
    url     = "https://nominatim.openstreetmap.org/search"
    headers = {
        "User-Agent":      "GeoSpatialSiteAnalyzer/1.2",
        "Accept-Language": "en,en-US;q=0.9",
    }
    params = {"q": query, "format": "json", "limit": 10, "addressdetails": 1}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [
        {
            "lat":          float(row["lat"]),
            "lon":          float(row["lon"]),
            "display_name": row.get("display_name", ""),
            "source":       "nominatim",
        }
        for row in data
    ]


def _geocode_opencage(query: str) -> list:
    if not (OPENCAGE_API_KEY or "").strip():
        return []
    try:
        resp = requests.get(
            "https://api.opencagedata.com/geocode/v1/json",
            params={
                "q":              query,
                "key":            OPENCAGE_API_KEY,
                "limit":          10,
                "no_annotations": 1,
                "language":       "en",
            },
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        return []
    out = []
    for row in payload.get("results") or []:
        geom = row.get("geometry") or {}
        lat, lon = geom.get("lat"), geom.get("lng")
        if lat is None or lon is None:
            continue
        label = row.get("formatted") or row.get("formatted_address") or ""
        out.append({"lat": float(lat), "lon": float(lon), "display_name": label, "source": "opencage"})
    return out


def _google_maps_search_key() -> str:
    return (
        (os.getenv("GOOGLE_MAPS_SEARCH_API_KEY") or "").strip()
        or (GOOGLE_PLACES_API_KEY or "").strip()
    )


def _google_place_details(place_id: str, key: str) -> Optional[dict]:
    try:
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/place/details/json",
            params={
                "place_id": place_id,
                "fields":   "geometry,formatted_address,name",
                "key":      key,
                "language": "en",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None
    if data.get("status") != "OK":
        return None
    result = data.get("result") or {}
    geom   = result.get("geometry") or {}
    loc    = geom.get("location") or {}
    lat, lng = loc.get("lat"), loc.get("lng")
    if lat is None or lng is None:
        return None
    display = result.get("formatted_address") or result.get("name") or ""
    return {"lat": float(lat), "lon": float(lng), "display_name": display,
            "place_id": place_id, "source": "google"}


def _google_place_autocomplete(
    query: str,
    bias_lat: Optional[float] = None,
    bias_lon: Optional[float] = None,
) -> list:
    key = _google_maps_search_key()
    if not key or not (query or "").strip():
        return []
    params = {"input": query.strip(), "key": key, "language": "en"}
    if bias_lat is not None and bias_lon is not None:
        params["location"] = f"{bias_lat},{bias_lon}"
        params["radius"]   = 50000
    try:
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/place/autocomplete/json",
            params=params, timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []
    status = data.get("status")
    if status not in ("OK", "ZERO_RESULTS"):
        return []
    predictions = data.get("predictions") or []

    # PERF FIX: was serial N HTTP calls; now concurrent
    place_ids = [p["place_id"] for p in predictions[:10] if p.get("place_id")]
    out: List[dict] = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(_google_place_details, pid, key): pid for pid in place_ids}
        for future in as_completed(futures):
            row = future.result()
            if row:
                out.append(row)
    return out


def _safe_float(value):
    if value is None:
        return None
    try:
        return float(str(value).split()[0])
    except Exception:
        return None


# ─────────────────────────────────────────────────────────
#  POPULATION  (mirrors no_hardware_backend priority chain)
# ─────────────────────────────────────────────────────────

def get_population_latest(lat: float, lon: float, radius_m: int) -> dict:
    """
    Priority chain:
      1. Real Population Data Portal (JWT)
      2. WorldPop Stats API (free, geojson fixed)
      3. GeoNames demo (fallback)
    """
    iso3 = _iso3_from_latlon(lat, lon)
    pop  = 0
    source_detail = "unavailable"

    # 1. Data Portal
    portal = _population_from_data_portal(lat, lon, radius_m)
    if portal and portal["population"] > 0:
        pop           = portal["population"]
        source_detail = portal["source_detail"]

    # 2. WorldPop (BUG FIX: uses json.dumps internally now)
    if pop <= 0:
        wp = _population_from_worldpop(lat, lon, radius_m, iso3)
        if wp and wp["population"] > 0:
            pop           = wp["population"]
            source_detail = wp["source_detail"]

    # 3. GeoNames
    if pop <= 0:
        gn = _population_from_geonames(lat, lon, radius_m)
        if gn and gn["population"] > 0:
            pop           = gn["population"]
            source_detail = gn["source_detail"]

    level = (
        "Very High — Dense urban" if pop > 100_000 else
        "High — Urban"            if pop > 50_000  else
        "Moderate — Semi-urban"   if pop > 10_000  else
        "Low — Suburban/rural"    if pop > 1_000   else
        "Very Low — Sparse"
    )

    return {
        "population":      pop,
        "level":           level,
        "radius_m":        radius_m,
        "iso3":            iso3,
        "source_detail":   source_detail,
        "source":          "data_portal_worldpop_geonames",
        "age_groups":      _age_split_estimate(iso3, pop),
        "age_groups_note": "Estimated from country demographic profile",
    }


# ─────────────────────────────────────────────────────────
#  LANDMARKS
# ─────────────────────────────────────────────────────────

def get_landmarks(lat: float, lon: float, radius: int = 2000) -> dict:
    overpass = """
[out:json][timeout:30];
(
  node["amenity"="hospital"](around:{r},{lat},{lon}); way["amenity"="hospital"](around:{r},{lat},{lon});
  node["amenity"="school"](around:{r},{lat},{lon}); way["amenity"="school"](around:{r},{lat},{lon});
  node["amenity"="college"](around:{r},{lat},{lon}); way["amenity"="college"](around:{r},{lat},{lon});
  node["amenity"="bank"](around:{r},{lat},{lon}); way["amenity"="bank"](around:{r},{lat},{lon});
  node["amenity"="pharmacy"](around:{r},{lat},{lon}); way["amenity"="pharmacy"](around:{r},{lat},{lon});
  node["amenity"="bus_station"](around:{r},{lat},{lon}); way["amenity"="bus_station"](around:{r},{lat},{lon});
  node["railway"="station"](around:{r},{lat},{lon}); way["railway"="station"](around:{r},{lat},{lon});
  node["amenity"="police"](around:{r},{lat},{lon}); way["amenity"="police"](around:{r},{lat},{lon});
  node["shop"="supermarket"](around:{r},{lat},{lon}); way["shop"="supermarket"](around:{r},{lat},{lon});
);
out center tags;
""".format(r=radius, lat=lat, lon=lon)
    try:
        elements = _overpass_query(overpass, timeout=45).get("elements", [])
    except Exception as exc:
        return {"landmarks": [], "total_count": 0, "source": "osm_overpass", "error": str(exc)}

    out = []
    for el in elements:
        center = el.get("center", {}) if el.get("type") == "way" else el
        tlat, tlon = center.get("lat"), center.get("lon")
        if tlat is None or tlon is None:
            continue
        tags  = el.get("tags", {})
        label = tags.get("amenity") or tags.get("railway") or tags.get("shop") or "poi"
        out.append({
            "name":       _osm_name_en(tags) or label.title(),
            "label":      label.replace("_", " ").title(),
            "lat":        tlat,
            "lon":        tlon,
            "distance_m": round(_haversine_km(lat, lon, tlat, tlon) * 1000),
            "source":     "osm",
        })
    out.sort(key=lambda x: x["distance_m"])
    return {"landmarks": out[:3], "total_count": len(out), "source": "osm_overpass"}


# ─────────────────────────────────────────────────────────
#  NATURAL HAZARDS
# ─────────────────────────────────────────────────────────

def get_natural_hazards(lat: float, lon: float, radius_km: int = 300) -> dict:
    hazards: List[dict] = []
    errors: Dict[str, str] = {}

    try:
        usgs = requests.get(
            "https://earthquake.usgs.gov/fdsnws/event/1/query",
            params={"format": "geojson", "latitude": lat, "longitude": lon,
                    "maxradiuskm": radius_km, "limit": 20},
            timeout=15,
        ).json()
        for f in usgs.get("features", []):
            coords = f.get("geometry", {}).get("coordinates", [None, None, None])
            if coords[1] is None or coords[0] is None:
                continue
            hazards.append({
                "type":       "earthquake",
                "title":      f.get("properties", {}).get("title"),
                "magnitude":  f.get("properties", {}).get("mag"),
                "time_ms":    f.get("properties", {}).get("time"),
                "lat":        coords[1],
                "lon":        coords[0],
                "distance_km": round(_haversine_km(lat, lon, coords[1], coords[0]), 1),
                "source":     "usgs",
            })
    except Exception as exc:
        errors["usgs_earthquakes"] = str(exc)

    try:
        eonet = requests.get("https://eonet.gsfc.nasa.gov/api/v3/events?status=open&limit=50", timeout=15).json()
        for ev in eonet.get("events", []):
            geos = ev.get("geometry") or []
            if not geos:
                continue
            c = geos[-1].get("coordinates")
            if not isinstance(c, list) or len(c) < 2:
                continue
            ev_lon, ev_lat = c[0], c[1]
            dist = _haversine_km(lat, lon, ev_lat, ev_lon)
            # BUG FIX: was radius_km * 5 — events 1500 km away were included
            if dist <= radius_km:
                categories = ",".join([x.get("title", "") for x in ev.get("categories", [])])
                hazards.append({
                    "type":        "event",
                    "title":       ev.get("title"),
                    "category":    categories,
                    "lat":         ev_lat,
                    "lon":         ev_lon,
                    "distance_km": round(dist, 1),
                    "source":      "nasa_eonet",
                })
    except Exception as exc:
        errors["nasa_eonet"] = str(exc)

    hazards.sort(key=lambda x: x.get("distance_km", 999999))
    return {"hazards": hazards[:50], "total_count": len(hazards),
            "source": "usgs+nasa_eonet", "errors": errors}


# ─────────────────────────────────────────────────────────
#  TELECOM TOWERS (OSM)
# ─────────────────────────────────────────────────────────

def get_telecom_towers(lat: float, lon: float, radius: int = 2000) -> dict:
    query = f"""
[out:json][timeout:30];
(
  node["man_made"="mast"]["tower:type"="communication"](around:{radius},{lat},{lon});
  node["man_made"="tower"]["tower:type"="communication"](around:{radius},{lat},{lon});
  node["man_made"="communications_tower"](around:{radius},{lat},{lon});
  way["man_made"="mast"]["tower:type"="communication"](around:{radius},{lat},{lon});
  way["man_made"="tower"]["tower:type"="communication"](around:{radius},{lat},{lon});
);
out center tags;
"""
    try:
        elements = _overpass_query(query, timeout=45).get("elements", [])
    except Exception as exc:
        return {"towers": [], "total_count": 0, "source": "osm_overpass", "error": str(exc)}

    towers = []
    for el in elements:
        tags   = el.get("tags", {})
        center = el.get("center", {}) if el.get("type") == "way" else el
        tlat, tlon = center.get("lat"), center.get("lon")
        if tlat is None or tlon is None:
            continue
        towers.append({
            "lat":        tlat,
            "lon":        tlon,
            "name":       _osm_name_en(tags) or "Telecom Tower",
            "operator":   tags.get("operator"),
            "height_m":   _safe_float(tags.get("height")),
            "technology": tags.get("tower:type") or tags.get("telecom") or "communication",
            "osm_id":     el.get("id"),
        })
    return {"towers": towers, "total_count": len(towers), "source": "osm_overpass"}


# ─────────────────────────────────────────────────────────
#  EV STATIONS (OSM)
# ─────────────────────────────────────────────────────────

def get_ev_stations(lat: float, lon: float, radius: int = 2000) -> dict:
    query = f"""
[out:json][timeout:30];
(
  node["amenity"="charging_station"](around:{radius},{lat},{lon});
  way["amenity"="charging_station"](around:{radius},{lat},{lon});
);
out center tags;
"""
    try:
        elements = _overpass_query(query, timeout=45).get("elements", [])
    except Exception as exc:
        return {"stations": [], "total_count": 0, "source": "osm_overpass", "error": str(exc)}

    stations = []
    for el in elements:
        tags   = el.get("tags", {})
        center = el.get("center", {}) if el.get("type") == "way" else el
        slat, slon = center.get("lat"), center.get("lon")
        if slat is None or slon is None:
            continue
        stations.append({
            "lat":           slat,
            "lon":           slon,
            "name":          _osm_name_en(tags) or tags.get("brand") or "EV Charging Station",
            "operator":      tags.get("operator") or tags.get("brand"),
            "network":       tags.get("network"),
            "capacity":      _safe_float(tags.get("capacity")),
            "fee":           tags.get("fee"),
            "opening_hours": tags.get("opening_hours"),
            "access":        tags.get("access"),
            "osm_id":        el.get("id"),
        })
    return {"stations": stations, "total_count": len(stations), "source": "osm_overpass"}


# ═══════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════

@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": "1.2.0",
        "api_keys": {
            "ola_maps":             bool(OLA_MAPS_API_KEY),
            "google_places":        bool(GOOGLE_PLACES_API_KEY),
            "google_maps_search":   bool(_google_maps_search_key()),
            "foursquare":           bool(FOURSQUARE_API_KEY),
            "opencage":             bool(OPENCAGE_API_KEY),
            "openrouteservice":     bool(OPENROUTESERVICE_API_KEY),
            "cell_tower":           bool(CELL_TOWER_API_KEY),
            "population_portal":    bool(POPULATION_API_BEARER),
        },
        "backend_mode": "no_hardware",
    }


@app.get("/business-types")
def business_types():
    return {"business_types": list(OSM_BUSINESS_TAGS.keys()), "count": len(OSM_BUSINESS_TAGS)}


@app.get("/geocode")
def geocode(
    q: str = Query(..., description="Address or place name to search"),
    international: bool = Query(False),
):
    results = []
    if OLA_MAPS_API_KEY:
        results = _geocode_olamaps(q)
    
    if not results:
        if international and (OPENCAGE_API_KEY or "").strip():
            results = _geocode_opencage(q) or _geocode_nominatim(q)
        else:
            results = _geocode_nominatim(q) or _geocode_opencage(q)
            
    if not results:
        raise HTTPException(status_code=404, detail=f"No results found for: {q}")
    return {"query": q, "results": results}


@app.get("/geocode/autocomplete")
def geocode_autocomplete(
    q: str = Query(...),
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
):
    bias_lat, bias_lon = lat, lon
    if bias_lat is not None and bias_lon is not None:
        if not (math.isfinite(bias_lat) and math.isfinite(bias_lon)):
            bias_lat, bias_lon = None, None
            
    if OLA_MAPS_API_KEY:
        results = _olamaps_autocomplete(q)
        if results:
            return {"query": q, "results": results}
            
    results = _google_place_autocomplete(q, bias_lat, bias_lon)
    return {"query": q, "results": results}


@app.get("/api-status")
def api_status():
    return {
        "OLA_MAPS_API_KEY":           {"configured": bool(OLA_MAPS_API_KEY)},
        "GOOGLE_MAPS_SEARCH_API_KEY": {"configured": bool((os.getenv("GOOGLE_MAPS_SEARCH_API_KEY") or "").strip())},
        "GOOGLE_PLACES_API_KEY":      {"configured": bool(GOOGLE_PLACES_API_KEY)},
        "google_maps_search_active":  {"configured": bool(_google_maps_search_key())},
        "FOURSQUARE_API_KEY":         {"configured": bool(FOURSQUARE_API_KEY)},
        "OPENCAGE_API_KEY":           {"configured": bool(OPENCAGE_API_KEY)},
        "OPENROUTESERVICE_API_KEY":   {"configured": bool(OPENROUTESERVICE_API_KEY)},
        "CELL_TOWER_API_KEY":         {"configured": bool(CELL_TOWER_API_KEY)},
        "POPULATION_API_BEARER":      {"configured": bool(POPULATION_API_BEARER)},
    }


@app.get("/telecom-towers")
def telecom_towers(
    lat: float = Query(...),
    lon: float = Query(...),
    radius: int = Query(2000, ge=100, le=10000),
):
    return {"location": {"lat": lat, "lon": lon, "radius": radius},
            **get_telecom_towers(lat, lon, radius)}


@app.get("/ev-stations")
def ev_stations(
    lat: float = Query(...),
    lon: float = Query(...),
    radius: int = Query(2000, ge=100, le=10000),
):
    return {"location": {"lat": lat, "lon": lon, "radius": radius},
            **get_ev_stations(lat, lon, radius)}


@app.get("/landmarks")
def landmarks(
    lat: float = Query(...),
    lon: float = Query(...),
    radius: int = Query(2000, ge=100, le=10000),
):
    return {"location": {"lat": lat, "lon": lon, "radius": radius},
            **get_landmarks(lat, lon, radius)}


@app.get("/natural-hazards")
def natural_hazards(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_km: int = Query(300, ge=50, le=2000),
):
    return {"location": {"lat": lat, "lon": lon, "radius_km": radius_km},
            **get_natural_hazards(lat, lon, radius_km)}


@app.get("/cell-towers")
def cell_towers_endpoint(
    lat: float = Query(...),
    lon: float = Query(...),
    radius: int = Query(2000, ge=100, le=10000),
):
    """Cell tower density and coverage quality near a location."""
    result = test_cell_towers(lat, lon, radius)
    return {"location": {"lat": lat, "lon": lon, "radius": radius}, **result}


@app.get("/population")
def population_endpoint(
    lat: float = Query(...),
    lon: float = Query(...),
    radius: int = Query(2000, ge=100, le=10000),
):
    """Population estimate using Data Portal → WorldPop → GeoNames fallback chain."""
    result = get_population_latest(lat, lon, radius)
    return {"location": {"lat": lat, "lon": lon, "radius": radius}, **result}


@app.post("/analyze")
def analyze(req: AnalysisRequest):
    started      = time.time()
    results      = {}
    errors       = {}
    business_type = (req.business_type or "restaurant").lower()

    start = req.start_date or (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")
    end   = req.end_date   or (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

    # ── Build concurrent task map ─────────────────────────
    def _run_roads():
        return test_road_score(req.lat, req.lon, req.radius)

    def _run_competitors():
        if _is_india(req.lat, req.lon) and OLA_MAPS_API_KEY:
            comp_ola = test_competitors_ola(req.lat, req.lon, req.radius, business_type) or {}
            comp_osm = test_competitors_osm(req.lat, req.lon, req.radius, business_type) or {}
            
            c_list = []
            c_list.extend(comp_ola.get("competitors", []))
            c_list.extend(comp_osm.get("competitors", []))
            
            e_ola = comp_ola.get("elapsed_s", 0)
            e_osm = comp_osm.get("elapsed_s", 0)
            named_count = sum(1 for c in c_list if c.get("name") and c["name"].strip() != "Unnamed")
            
            return {
                "total_count": len(c_list),
                "named_count": named_count,
                "named_list": [c.get("name") for c in c_list if c.get("name") and c.get("name").strip() != "Unnamed"],
                "competitors": c_list,
                "elapsed_s": round(max(e_ola, e_osm) if e_ola and e_osm else (e_ola + e_osm), 2),
                "source": "ola_maps + osm_overpass",
                "business_type": business_type,
            }

        if req.competitor_source == "google":
            comp = test_competitors_google(req.lat, req.lon, req.radius, business_type)
            return comp or test_competitors_osm(req.lat, req.lon, req.radius, business_type)

        return test_competitors_osm(req.lat, req.lon, req.radius, business_type)

    def _run_weather():
        return test_weather_aqi(req.lat, req.lon, start, end)

    def _run_population():
        return get_population_latest(req.lat, req.lon, req.radius)

    def _run_cell_towers():
        return test_cell_towers(req.lat, req.lon, req.radius)

    def _run_land_use():
        return test_land_use(req.lat, req.lon, min(req.radius, 1000))

    def _run_flood():
        return test_flood_risk(req.lat, req.lon)

    def _run_isochrones():
        return test_isochrones(req.lat, req.lon)

    def _run_landmarks():
        return get_landmarks(req.lat, req.lon, min(req.radius, 3000))

    def _run_hazards():
        return get_natural_hazards(req.lat, req.lon, 300)

    def _run_telecom():
        return get_telecom_towers(req.lat, req.lon, req.radius)

    def _run_ev():
        return get_ev_stations(req.lat, req.lon, req.radius)

    # PERF: Map task key → callable; always-on tasks + conditional
    task_map: Dict[str, callable] = {
        "land_use":       _run_land_use,
        "flood_risk":     _run_flood,
        "isochrones":     _run_isochrones,
        "landmarks":      _run_landmarks,
        "natural_hazards": _run_hazards,
    }
    if req.run_roads:
        task_map["roads"] = _run_roads
    if req.run_competitors:
        task_map["competitors"] = _run_competitors
    if req.run_weather:
        task_map["weather"] = _run_weather
    if req.run_population:
        task_map["population"] = _run_population
    if req.run_cell_towers:
        task_map["cell_towers"] = _run_cell_towers
    if req.run_telecom_towers:
        task_map["telecom_towers"] = _run_telecom
    if req.run_ev_stations:
        task_map["ev_stations"] = _run_ev

    # PERF: Run all I/O tasks concurrently — drops 30-45s → ~8-12s
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_key = {executor.submit(fn): key for key, fn in task_map.items()}
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                results[key] = future.result()
            except Exception as exc:
                errors[key] = str(exc)

    # Scoring (after all results collected)
    try:
        scoring = _score(results, req)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    return {
        "location": {"lat": req.lat, "lon": req.lon, "radius": req.radius},
        "scoring":  scoring,
        "results":  results,
        "errors":   errors,
        "elapsed_s": round(time.time() - started, 2),
        "config":   {
            "competitor_source": req.competitor_source,
            "business_type":    business_type,
            "weather_range":    {"start": start, "end": end},
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)