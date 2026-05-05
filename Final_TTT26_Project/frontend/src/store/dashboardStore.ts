import { create } from 'zustand'
import type { Coordinates, HistoryLocation, NearbyItem, ScoreResponse } from '../types/geo'
import type { MapStyleId } from '../constants/mapStyles'
import { mapStyleToUiTheme, uiThemeToMapStyle, type UiTheme } from '../theme/uiTheme'

const MAP_STYLE_STORAGE_KEY = 'geo-dashboard-map-style'

function readPersistedMapStyle(): MapStyleId {
  try {
    const v = localStorage.getItem(MAP_STYLE_STORAGE_KEY)
    if (v === 'street' || v === 'normal' || v === 'satellite') return v
  } catch {
    /* private mode / SSR */
  }
  return 'street'
}

function persistMapStyle(style: MapStyleId) {
  try {
    localStorage.setItem(MAP_STYLE_STORAGE_KEY, style)
  } catch {
    /* ignore */
  }
}

export type SidebarPanelKey =
  | 'askai'
  | 'saved'
  | 'recents'
  | 'controls'   // ← unified: layers + analysis + filters + weights
  | 'compare'
  | 'history'
  | 'settings'
  | null

export type DistanceUnit = 'km' | 'mi'

interface UserState {
  isAuthenticated: boolean
  name: string
  email: string
  role: string
}

interface DashboardState {
  // ── Location ─────────────────────────────────────────────────
  selectedCoordinates: Coordinates | null
  selectedLocationLabel: string | null
  /** Compare mode: second pin (Zone B). Zone A is `selectedCoordinates`. */
  compareZoneBCoordinates: Coordinates | null
  compareZoneBLabel: string | null
  compareScoreB: ScoreResponse | null

  // ── Search ───────────────────────────────────────────────────
  searchQuery: string

  // ── Panel ────────────────────────────────────────────────────
  activePanel: SidebarPanelKey
  panelAnchorY: number          // px from top of viewport where the icon was clicked
  insightsOpenMobile: boolean
  /** True after Start Analyzing: hides the tool dock; controls use compact height with insights. Reset on new map pick. */
  insightsDockHidden: boolean

  // ── Category ─────────────────────────────────────────────────
  activeCategory: string
  setActiveCategory: (cat: string) => void

  // ── Layers ───────────────────────────────────────────────────
  selectedLayers: string[]

  // ── Weights ──────────────────────────────────────────────────
  weights: {
    population: number
    accessibility: number
    competition: number
    risk: number
  }

  // ── Filters ──────────────────────────────────────────────────
  geoFilters: {
    minPopulation: number
    maxCompetitors: number
    distanceThreshold: number
    strictMode: boolean
  }

  // ── Analysis tools ───────────────────────────────────────────
  analysisTools: {
    areaCrop: boolean
    radius: number
    locationPicker: boolean
  }

  // ── Insights ─────────────────────────────────────────────────
  history: HistoryLocation[]
  score: ScoreResponse | null
  nearby: NearbyItem[]
  insightsLoading: boolean
  insightsError: string | null

  // ── Map ──────────────────────────────────────────────────────
  mapStyle: MapStyleId
  /** Synced with map basemap; drives global CSS variables (`data-theme` on `<html>`). */
  uiTheme: UiTheme

  // ── User ─────────────────────────────────────────────────────
  user: UserState
  preferences: {
    mapDefaultView: MapStyleId
    units: DistanceUnit
    notificationsEmail: boolean
    notificationsPush: boolean
  }

  // ── Actions ──────────────────────────────────────────────────
  setSearchQuery: (query: string) => void
  setSelectedLocation: (coords: Coordinates, label: string) => void
  setCompareZoneB: (coords: Coordinates, label: string) => void
  clearCompareZoneB: () => void
  setCompareScoreB: (score: ScoreResponse | null) => void
  /** Clear pin, insights, compare B, and restore dock — user can pick a new location. */
  clearLocationSession: () => void
  setInsightsOpenMobile: (value: boolean) => void
  loadHistoryLocation: (item: HistoryLocation) => void
  setInsightsData: (score: ScoreResponse, nearby: NearbyItem[]) => void
  beginInsightsFetch: () => void
  setInsightsError: (message: string) => void
  setActivePanel: (panel: SidebarPanelKey) => void
  setPanelAnchorY: (y: number) => void
  /** Open the controls panel without toggling — used by map click. */
  openControlsPanel: () => void
  /** Force-close whatever panel is currently open. */
  closeActivePanel: () => void
  toggleSelectedLayer: (layer: string) => void
  setWeight: (key: keyof DashboardState['weights'], value: number) => void
  setGeoFilter: (key: keyof DashboardState['geoFilters'], value: number | boolean) => void
  setAnalysisTool: (key: keyof DashboardState['analysisTools'], value: number | boolean) => void
  setMapStyle: (style: MapStyleId) => void
  setUiTheme: (theme: UiTheme) => void
  setPreferences: (partial: Partial<DashboardState['preferences']>) => void
  login: (payload: Pick<UserState, 'name' | 'email' | 'role'>) => void
  logout: () => void
}

export const useDashboardStore = create<DashboardState>((set) => ({
  selectedCoordinates: null,
  selectedLocationLabel: null,
  compareZoneBCoordinates: null,
  compareZoneBLabel: null,
  compareScoreB: null,
  searchQuery: '',
  insightsOpenMobile: false,
  insightsDockHidden: false,
  activePanel: null,
  panelAnchorY: 0,
  activeCategory: 'restaurant',
  selectedLayers: ['Density', 'Roads', 'Flood'],
  weights: {
    population: 75,
    accessibility: 72,
    competition: 55,
    risk: 48,
  },
  geoFilters: {
    minPopulation: 50000,
    maxCompetitors: 8,
    distanceThreshold: 5,
    strictMode: false,
  },
  analysisTools: {
    areaCrop: false,
    radius: 2,
    locationPicker: true,
  },
  history: [],
  score: null,
  nearby: [],
  insightsLoading: false,
  insightsError: null,
  mapStyle: readPersistedMapStyle(),
  uiTheme: mapStyleToUiTheme(readPersistedMapStyle()),
  user: {
    isAuthenticated: true,
    name: 'Jaimin',
    email: 'jaimin@example.com',
    role: 'Analyst',
  },
  preferences: {
    mapDefaultView: 'street',
    units: 'km',
    notificationsEmail: true,
    notificationsPush: false,
  },

  setSearchQuery: (query) => set({ searchQuery: query }),
  setSelectedLocation: (coords, label) =>
    set({
      selectedCoordinates: coords,
      selectedLocationLabel: label,
      insightsDockHidden: false,
      compareZoneBCoordinates: null,
      compareZoneBLabel: null,
      compareScoreB: null,
      // New pin → fresh insights; restores Start Analyzing CTA
      score: null,
      nearby: [],
      insightsError: null,
      insightsLoading: false,
    }),
  setCompareZoneB: (coords, label) =>
    set({ compareZoneBCoordinates: coords, compareZoneBLabel: label, compareScoreB: null }),
  clearCompareZoneB: () => set({ compareZoneBCoordinates: null, compareZoneBLabel: null, compareScoreB: null }),
  setCompareScoreB: (score) => set({ compareScoreB: score }),
  clearLocationSession: () =>
    set({
      selectedCoordinates: null,
      selectedLocationLabel: null,
      compareZoneBCoordinates: null,
      compareZoneBLabel: null,
      compareScoreB: null,
      score: null,
      nearby: [],
      insightsLoading: false,
      insightsError: null,
      insightsDockHidden: false,
      insightsOpenMobile: false,
    }),
  setInsightsOpenMobile: (value) => set({ insightsOpenMobile: value }),
  loadHistoryLocation: (item) =>
    set({
      selectedCoordinates: item.coordinates,
      selectedLocationLabel: item.name,
      insightsOpenMobile: true,
      activePanel: 'controls',
      compareZoneBCoordinates: null,
      compareZoneBLabel: null,
      score: null,
      nearby: [],
      insightsError: null,
      insightsLoading: false,
    }),
  setInsightsData: (score, nearby) =>
    set({ score, nearby, insightsLoading: false, insightsError: null }),
  beginInsightsFetch: () =>
    set({
      insightsLoading: true,
      insightsError: null,
      score: null,
      nearby: [],
      insightsDockHidden: true,
    }),
  setInsightsError: (message) => set({ insightsLoading: false, insightsError: message }),
  setActivePanel: (panel) =>
    set((state) => {
      const next: SidebarPanelKey = state.activePanel === panel ? null : panel
      const leavingCompare = state.activePanel === 'compare' && next !== 'compare'
      return {
        activePanel: next,
        ...(leavingCompare
          ? { compareZoneBCoordinates: null, compareZoneBLabel: null, compareScoreB: null }
          : {}),
      }
    }),
  setPanelAnchorY: (y) => set({ panelAnchorY: y }),
  openControlsPanel: () => set({ activePanel: 'controls' }),
  closeActivePanel: () => set({ activePanel: null }),
  setActiveCategory: (cat) => set((state) => {
    let newWeights = { ...state.weights };
    switch(cat) {
      case 'restaurant':
      case 'cafe':
        newWeights = { population: 75, accessibility: 72, competition: 55, risk: 48 };
        break;
      case 'ev_stations':
        newWeights = { population: 60, accessibility: 90, competition: 40, risk: 30 };
        break;
      case 'telecom_towers':
        newWeights = { population: 85, accessibility: 40, competition: 30, risk: 60 };
        break;
      case 'pharmacy':
      case 'hospital':
        newWeights = { population: 80, accessibility: 85, competition: 50, risk: 20 };
        break;
      case 'supermarket':
      case 'hardware':
        newWeights = { population: 90, accessibility: 70, competition: 60, risk: 40 };
        break;
      case 'hotel':
        newWeights = { population: 50, accessibility: 80, competition: 70, risk: 40 };
        break;
      case 'bank':
        newWeights = { population: 85, accessibility: 85, competition: 40, risk: 30 };
        break;
      default:
        newWeights = { population: 70, accessibility: 70, competition: 50, risk: 50 };
        break;
    }
    return { activeCategory: cat, weights: newWeights };
  }),
  toggleSelectedLayer: (layer) =>
    set((state) => ({
      selectedLayers: state.selectedLayers.includes(layer)
        ? state.selectedLayers.filter((v) => v !== layer)
        : [...state.selectedLayers, layer],
    })),
  setWeight: (key, value) =>
    set((state) => ({ weights: { ...state.weights, [key]: value } })),
  setGeoFilter: (key, value) =>
    set((state) => ({ geoFilters: { ...state.geoFilters, [key]: value } })),
  setAnalysisTool: (key, value) =>
    set((state) => ({ analysisTools: { ...state.analysisTools, [key]: value } })),
  setMapStyle: (style) => {
    persistMapStyle(style)
    set({ mapStyle: style, uiTheme: mapStyleToUiTheme(style) })
  },
  setUiTheme: (theme) => {
    const map = uiThemeToMapStyle(theme)
    persistMapStyle(map)
    set({ uiTheme: theme, mapStyle: map })
  },
  setPreferences: (partial) =>
    set((state) => ({ preferences: { ...state.preferences, ...partial } })),
  login: (payload) =>
    set({
      user: {
        isAuthenticated: true,
        name: payload.name,
        email: payload.email,
        role: payload.role,
      },
    }),
  logout: () =>
    set({
      user: { isAuthenticated: false, name: '', email: '', role: '' },
    }),
}))
