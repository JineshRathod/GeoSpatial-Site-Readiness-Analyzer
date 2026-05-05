import type { NearbyItem, ScoreResponse } from '../types/geo'

/** Base URL — swap this env var once backend is live. */
const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`)
  return res.json() as Promise<T>
}

function roadTopTypes(roads: Record<string, unknown> | undefined): string[] {
  if (!roads) return []
  const direct = roads.top_highway_types
  if (Array.isArray(direct)) return direct as string[]
  const br = roads.highway_breakdown
  if (br && typeof br === 'object' && !Array.isArray(br)) {
    return Object.keys(br as Record<string, number>).slice(0, 12)
  }
  return []
}

function roadLengthKm(roads: Record<string, unknown> | undefined): number {
  if (!roads) return 0
  const a = roads.total_length_km ?? roads.road_score_km
  const n = typeof a === 'number' ? a : parseFloat(String(a ?? 0))
  return Number.isFinite(n) ? n : 0
}

// ── Public API surface (API-ready endpoints) ─────────────────────────────

/**
 * POST /analyze  { lat, lon, business_type, radius }
 */
export async function getScore(
  coords: { lat: number; lng: number },
  businessType = 'retail',
  radiusM = 2000,
  weights?: { population: number; accessibility: number; competition: number; risk: number }
): Promise<ScoreResponse> {
  const payload: Record<string, unknown> = {
    lat: coords.lat,
    lon: coords.lng,
    business_type: businessType,
    radius: radiusM,
  }
  if (weights) {
    payload.weight_population = weights.population
    payload.weight_roads = weights.accessibility
    payload.weight_competitors = weights.competition
    payload.weight_weather = weights.risk
  }

  const rawData = await apiFetch<Record<string, unknown>>('/analyze', {
    method: 'POST',
    body: JSON.stringify(payload),
  })

  const results = rawData.results as Record<string, unknown> | undefined
  const roadsRaw = results?.roads as Record<string, unknown> | undefined
  const comp = (results?.competitors || {}) as Record<string, unknown>
  const src = String(comp.source || '').toLowerCase()
  /** Backend merges India runs: one combined list */
  const mergedOlaOsm = src.includes('ola') && src.includes('osm')
  const namesFull = Array.isArray(comp.named_list) ? (comp.named_list as string[]) : []
  const locs = Array.isArray(comp.locations)
    ? (comp.locations as { lat?: number; lon?: number; name?: string }[])
    : []

  let competitors: ScoreResponse['competitors']

  if (mergedOlaOsm) {
    competitors = {
      olaMaps: undefined,
      osm: {
        total: Number(comp.total_count ?? 0),
        named: Number(comp.named_count ?? namesFull.length),
        sampleNames: namesFull,
        locations: locs.map((c) => ({
          lat: Number(c.lat),
          lon: Number(c.lon),
          name: String(c.name ?? ''),
        })),
        elapsedSeconds: Number(comp.elapsed_s ?? 0),
        sourceLabel: 'Ola Maps + OpenStreetMap (deduped)',
      },
    }
  } else {
    const isOla = src.includes('ola')
    const isOsm = src.includes('osm') || src.includes('overpass')
    const shortList = namesFull.length > 0 ? namesFull : (Array.isArray(comp.named_list) ? comp.named_list as string[] : [])
    competitors = {
      olaMaps: isOla && !isOsm
        ? {
            total: Number(comp.total_count ?? 0),
            sampleNames: shortList,
            locations: locs.map((c) => ({
              lat: Number(c.lat),
              lon: Number(c.lon),
              name: String(c.name ?? ''),
            })),
            elapsedSeconds: Number(comp.elapsed_s ?? 0),
          }
        : undefined,
      osm: isOsm && !isOla
        ? {
            total: Number(comp.total_count ?? 0),
            named: Number(comp.named_count ?? 0),
            sampleNames: shortList,
            locations: locs.map((c) => ({
              lat: Number(c.lat),
              lon: Number(c.lon),
              name: String(c.name ?? ''),
            })),
            elapsedSeconds: Number(comp.elapsed_s ?? 0),
          }
        : undefined,
    }
    // Pure OSM without 'osm' in string (edge case)
    if (!competitors.olaMaps && !competitors.osm && namesFull.length > 0) {
      competitors = {
        osm: {
          total: Number(comp.total_count ?? 0),
          named: Number(comp.named_count ?? 0),
          sampleNames: namesFull,
          locations: locs.map((c) => ({
            lat: Number(c.lat),
            lon: Number(c.lon),
            name: String(c.name ?? ''),
          })),
          elapsedSeconds: Number(comp.elapsed_s ?? 0),
        },
      }
    }
  }

  return {
    totalScore: (rawData.scoring as Record<string, unknown>)?.composite_score as number ?? 60,
    populationScore: ((rawData.scoring as Record<string, unknown>)?.sub_scores as Record<string, number>)?.population ?? 50,
    accessibilityScore: ((rawData.scoring as Record<string, unknown>)?.sub_scores as Record<string, number>)?.roads ?? 50,
    competitionScore: ((rawData.scoring as Record<string, unknown>)?.sub_scores as Record<string, number>)?.competitors ?? 50,
    riskScore: ((rawData.scoring as Record<string, unknown>)?.sub_scores as Record<string, number>)?.weather ?? 90,

    population: results?.population
      ? {
          total: Number((results.population as Record<string, unknown>).population ?? 0),
          level: String((results.population as Record<string, unknown>).level ?? 'Unknown'),
          sourceDetail: String((results.population as Record<string, unknown>).source_detail ?? 'Unknown'),
          iso3: String((results.population as Record<string, unknown>).iso3 ?? 'IND'),
          ageGroups: ((results.population as Record<string, unknown>).age_groups ?? {}) as Record<string, number>,
        }
      : undefined,

    roads: {
      totalWays: Number(roadsRaw?.total_ways ?? 0),
      totalLengthKm: roadLengthKm(roadsRaw),
      intersections: Number(roadsRaw?.intersections ?? 0),
      deadEnds: Number(roadsRaw?.dead_ends ?? 0),
      topHighwayTypes: roadTopTypes(roadsRaw),
      elapsedSeconds: Number(roadsRaw?.elapsed_s ?? 0),
    },
    weather: {
      avgTemperatureC: Number((results?.weather as Record<string, unknown>)?.avg_temperature_c ?? 0),
      avgPrecipitationMmDay: Number((results?.weather as Record<string, unknown>)?.avg_precipitation_mm_day ?? 0),
      avgWindSpeedKmh: Number((results?.weather as Record<string, unknown>)?.avg_wind_speed_kmh ?? 0),
      avgUsAqi: Number((results?.weather as Record<string, unknown>)?.avg_us_aqi ?? 0),
      avgPm25: Number((results?.weather as Record<string, unknown>)?.avg_pm2_5 ?? 0),
      daysFetched: Number((results?.weather as Record<string, unknown>)?.days_fetched ?? 0),
      elapsedSeconds: Number((results?.weather as Record<string, unknown>)?.elapsed_s ?? 0),
    },
    flood: {
      elevationM: Number((results?.flood_risk as Record<string, unknown>)?.elevation_m ?? 0),
      riskLevel: ((results?.flood_risk as Record<string, unknown>)?.risk_level ?? 'Low') as 'Low' | 'Medium' | 'High',
      elapsedSeconds: Number((results?.flood_risk as Record<string, unknown>)?.elapsed_s ?? 0),
    },
    zoning: {
      totalPolygons: Number((results?.land_use as Record<string, unknown>)?.total_polygons ?? 0),
      zoneBreakdown: ((results?.land_use as Record<string, unknown>)?.zone_breakdown ?? {}) as Record<string, number>,
      dominantZone: String((results?.land_use as Record<string, unknown>)?.dominant_zone ?? 'Unknown'),
      commercialFriendly: Boolean((results?.land_use as Record<string, unknown>)?.commercial_friendly ?? false),
      elapsedSeconds: Number((results?.land_use as Record<string, unknown>)?.elapsed_s ?? 0),
    },
    isochrones: {
      source: String((results?.isochrones as Record<string, unknown>)?.source ?? 'approx'),
      radii: (Array.isArray((results?.isochrones as Record<string, unknown>)?.radii)
        ? (results?.isochrones as { radii: { minutes: number; radiusM: number; areaSqKm: number }[] }).radii
        : []),
      elapsedSeconds: Number((results?.isochrones as Record<string, unknown>)?.elapsed_s ?? 0),
    },
    competitors,
    cellTowers: results?.cell_towers
      ? {
          totalTowers: Number((results.cell_towers as Record<string, unknown>).total_towers ?? 0),
          coverageQuality: String((results.cell_towers as Record<string, unknown>).coverage_quality ?? 'Unknown'),
          coverageScore: Number((results.cell_towers as Record<string, unknown>).coverage_score ?? 0),
          elapsedSeconds: Number((results.cell_towers as Record<string, unknown>).elapsed_s ?? 0),
        }
      : undefined,
  }
}

/** GET /landmarks?lat=…&lon=…&radius=… (meters, 100–10000) */
export async function getNearby(
  coords?: { lat: number; lng: number },
  radiusM = 2000,
): Promise<NearbyItem[]> {
  if (!coords) return []
  try {
    const r = Math.min(10000, Math.max(100, Math.round(radiusM)))
    const data = await apiFetch<{ landmarks?: Array<Record<string, unknown>> }>(
      `/landmarks?lat=${coords.lat}&lon=${coords.lng}&radius=${r}`,
    )
    return (data.landmarks || []).map((l, i) => {
      const lon = (l.lon ?? l.lng) as number | undefined
      return {
        id: `l${i}`,
        title: String(l.name || l.label || 'POI'),
        type: 'poi',
        distanceKm: Number(l.distance_m ?? 0) / 1000,
        lat: l.lat as number | undefined,
        lng: lon,
      }
    })
  } catch {
    return []
  }
}

/** POST /compare — never throws; returns a safe default on network error */
export async function compareLocations(payload: {
  zoneA: { lat: number; lng: number }
  zoneB: { lat: number; lng: number }
}): Promise<{ status: string; message: string }> {
  try {
    return await apiFetch('/compare', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  } catch {
    return { status: 'error', message: 'Backend unreachable — comparison queued locally.' }
  }
}

/** GET /history */
export async function getHistory(): Promise<{ id: string; name: string; lat: number; lng: number; score: number }[]> {
  try {
    return await apiFetch('/history')
  } catch {
    return []
  }
}

export async function autocompleteLocation(query: string, lat?: number, lon?: number) {
  if (!query.trim()) return []
  try {
    const params = new URLSearchParams()
    params.set('q', query)
    if (lat !== undefined && lon !== undefined) {
      params.set('lat', lat.toString())
      params.set('lon', lon.toString())
    }
    const data = await apiFetch<{ results?: unknown[] }>(`/geocode/autocomplete?${params.toString()}`)
    return data.results || []
  } catch {
    return []
  }
}

export async function geocodeLocation(query: string) {
  if (!query.trim()) return []
  try {
    const data = await apiFetch<{ results?: unknown[] }>(`/geocode?q=${encodeURIComponent(query)}`)
    return data.results || []
  } catch {
    return []
  }
}
