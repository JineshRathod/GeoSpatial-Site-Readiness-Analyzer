export type LayerKey = 'population' | 'roads' | 'competitors' | 'zoning' | 'risk'

export type FilterKey =
  | 'populationWeight'
  | 'accessibilityWeight'
  | 'competitionWeight'
  | 'riskWeight'

export interface Coordinates {
  lng: number
  lat: number
}

export interface ScoreResponse {
  totalScore: number
  populationScore: number
  accessibilityScore: number
  competitionScore: number
  riskScore: number

  // ── Population Demographics ─────────────────────────────────
  population?: {
    total: number
    level: string
    sourceDetail: string
    iso3: string
    ageGroups: Record<string, number>
  }

  // ── Roads (Overpass) ────────────────────────────────────────
  roads?: {
    totalWays: number
    totalLengthKm: number
    intersections: number
    deadEnds: number
    topHighwayTypes: string[]
    elapsedSeconds: number
  }

  // ── Weather + AQI (Open-Meteo) ──────────────────────────────
  weather?: {
    avgTemperatureC: number
    avgPrecipitationMmDay: number
    avgWindSpeedKmh: number
    avgUsAqi: number
    avgPm25: number
    daysFetched: number
    elapsedSeconds: number
  }

  // ── Flood Risk (OpenTopoData) ───────────────────────────────
  flood?: {
    elevationM: number
    riskLevel: 'Low' | 'Medium' | 'High'
    elapsedSeconds: number
  }

  // ── Land Use / Zoning (Overpass) ────────────────────────────
  zoning?: {
    totalPolygons: number
    zoneBreakdown: Record<string, number>
    dominantZone: string
    commercialFriendly: boolean
    elapsedSeconds: number
  }

  // ── Isochrones ──────────────────────────────────────────────
  isochrones?: {
    source: string
    radii: { minutes: number; radiusM: number; areaSqKm: number }[]
    elapsedSeconds: number
  }

  // ── Competitors ─────────────────────────────────────────────
  competitors?: {
    olaMaps?: { total: number; sampleNames: string[]; elapsedSeconds: number; locations?: { lat: number; lon: number; name: string }[] }
    osm?: {
      total: number
      named: number
      sampleNames: string[]
      elapsedSeconds: number
      locations?: { lat: number; lon: number; name: string }[]
      /** When backend merges Ola + OSM into one list */
      sourceLabel?: string
    }
  }

  // ── Cell Towers ─────────────────────────────────────────────
  cellTowers?: {
    totalTowers: number
    coverageQuality: string
    coverageScore: number
    elapsedSeconds: number
  }
}

export interface NearbyItem {
  id: string
  title: string
  type: 'competitor' | 'poi' | 'transport'
  distanceKm: number
  lat?: number
  lng?: number
}

export interface AnalyzeAreaPayload {
  polygon: [number, number][]
}

export interface HistoryLocation {
  id: string
  name: string
  coordinates: Coordinates
}
