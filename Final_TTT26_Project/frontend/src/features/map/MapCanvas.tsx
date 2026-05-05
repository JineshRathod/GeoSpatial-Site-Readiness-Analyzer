import { AnimatePresence, motion } from 'framer-motion'
import maplibregl, { type MapMouseEvent } from 'maplibre-gl'
import { memo, useCallback, useEffect, useRef, useState, type MutableRefObject } from 'react'
import { Sparkles } from 'lucide-react'
import { getStyleForMapStyleId } from '../../constants/mapStyles'
import { useDashboardStore } from '../../store/dashboardStore'
import type { ScoreResponse } from '../../types/geo'
import { getNearby, getScore } from '../../services/api'

const CENTER: [number, number] = [72.5714, 23.0225]

function createGeoJSONCircle(center: [number, number], radiusInMeters: number, points = 64) {
  const coords = []
  const km = radiusInMeters / 1000
  const distanceX = km / (111.320 * Math.cos(center[1] * Math.PI / 180))
  const distanceY = km / 110.574
  for (let i = 0; i < points; i++) {
    const theta = (i / points) * (2 * Math.PI)
    const x = distanceX * Math.cos(theta)
    const y = distanceY * Math.sin(theta)
    coords.push([center[0] + x, center[1] + y])
  }
  coords.push(coords[0])
  return {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        geometry: { type: 'Polygon', coordinates: [coords] },
        properties: {}
      }
    ]
  }
}

function coordLon(loc: { lon?: number; lng?: number }): number | undefined {
  const v = loc.lon ?? loc.lng
  if (v === undefined || v === null) return undefined
  const n = Number(v)
  return Number.isFinite(n) ? n : undefined
}

function cleanDisplayName(raw: string): string | null {
  const t = raw.trim()
  if (!t || /^unnamed$/i.test(t)) return null
  return t
}

function pickCompetitorTitle(
  sc: ScoreResponse | null,
  loc: { name?: string },
  sourceIndex: number,
  zone: 'a' | 'b',
): string {
  const direct = cleanDisplayName(String(loc.name ?? ''))
  if (direct) return direct
  const ola = sc?.competitors?.olaMaps?.sampleNames
  const osm = sc?.competitors?.osm?.sampleNames
  const pool = [...(ola ?? []), ...(osm ?? [])]
  const fb = pool[sourceIndex]?.trim()
  if (fb) return fb
  return zone === 'b' ? `Competitor (zone B) #${sourceIndex + 1}` : `Competitor #${sourceIndex + 1}`
}

function openPoiPopup(
  map: maplibregl.Map,
  popupRef: MutableRefObject<maplibregl.Popup | null>,
  lng: number,
  lat: number,
  kindLabel: string,
  title: string,
  metaLines: string[],
) {
  popupRef.current?.remove()
  const root = document.createElement('div')
  root.className = 'map-poi-popup-inner'
  root.style.cssText =
    'padding:2px 2px 0;font:13px/1.35 system-ui,sans-serif;max-width:280px;color:var(--text,#0f172a)'

  const kind = document.createElement('div')
  kind.style.cssText =
    'font-size:10px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;color:#64748b'
  kind.textContent = kindLabel
  root.appendChild(kind)

  const h = document.createElement('div')
  h.style.cssText = 'font-weight:600;margin-top:4px'
  h.textContent = title
  root.appendChild(h)

  for (const line of metaLines) {
    const t = line.trim()
    if (!t) continue
    const m = document.createElement('div')
    m.style.cssText = 'font-size:11px;color:#64748b;margin-top:4px;line-height:1.35'
    m.textContent = line
    root.appendChild(m)
  }

  const c = document.createElement('div')
  c.style.cssText = 'font-size:10px;font-family:ui-monospace,monospace;color:#94a3b8;margin-top:6px'
  c.textContent = `${lat.toFixed(5)}, ${lng.toFixed(5)}`
  root.appendChild(c)

  const popup = new maplibregl.Popup({
    closeButton: true,
    closeOnClick: true,
    maxWidth: '280px',
    offset: 20,
    anchor: 'bottom',
  })
    .setLngLat([lng, lat])
    .setDOMContent(root)
    .addTo(map)
  popupRef.current = popup
}

function placeOrUpdateMarker(
  map: maplibregl.Map,
  markerRef: MutableRefObject<maplibregl.Marker | null>,
  coords: { lng: number; lat: number } | null,
  variant: 'primary' | 'compare' = 'primary',
) {
  markerRef.current?.remove()
  markerRef.current = null
  if (!coords) return

  const el = document.createElement('div')
  const primary = `
    width:20px;height:20px;border-radius:50%;
    background:#06b6d4;
    box-shadow:0 0 0 4px rgba(6,182,212,0.3),0 0 16px rgba(6,182,212,0.4);
  `
  const compare = `
    width:18px;height:18px;border-radius:50%;
    background:#a855f7;
    box-shadow:0 0 0 4px rgba(168,85,247,0.35),0 0 14px rgba(168,85,247,0.45);
  `
  el.style.cssText = (variant === 'primary' ? primary : compare) + 'cursor:pointer;'
  const marker = new maplibregl.Marker({ element: el })
    .setLngLat([coords.lng, coords.lat])
    .addTo(map)
  markerRef.current = marker
}

function MapCanvasInner() {
  const mapRef          = useRef<maplibregl.Map | null>(null)
  const mapContainerRef = useRef<HTMLDivElement | null>(null)
  const markerRef       = useRef<maplibregl.Marker | null>(null)
  const markerBRef      = useRef<maplibregl.Marker | null>(null)
  const extraMarkersRef = useRef<maplibregl.Marker[]>([])
  const poiPopupRef     = useRef<maplibregl.Popup | null>(null)
  const mapReadyRef     = useRef(false)

  const selectedCoordinates   = useDashboardStore((s) => s.selectedCoordinates)
  const compareZoneBCoordinates = useDashboardStore((s) => s.compareZoneBCoordinates)
  const insightsLoading       = useDashboardStore((s) => s.insightsLoading)
  const score                 = useDashboardStore((s) => s.score)
  const compareScoreB         = useDashboardStore((s) => s.compareScoreB)
  const nearbyData            = useDashboardStore((s) => s.nearby)
  const mapStyle              = useDashboardStore((s) => s.mapStyle)
  const radiusKm              = useDashboardStore((s) => s.analysisTools.radius)
  const activeCategory        = useDashboardStore((s) => s.activeCategory)
  const beginInsightsFetch    = useDashboardStore((s) => s.beginInsightsFetch)
  const setInsightsData       = useDashboardStore((s) => s.setInsightsData)
  const setInsightsError      = useDashboardStore((s) => s.setInsightsError)
  const setInsightsOpenMobile = useDashboardStore((s) => s.setInsightsOpenMobile)
  const openControlsPanel     = useDashboardStore((s) => s.openControlsPanel)
  const closeActivePanel      = useDashboardStore((s) => s.closeActivePanel)

  const [analyzing, setAnalyzing] = useState(false)
  // Use a ref so the startAnalyzing callback doesn't go stale
  const analyzingRef = useRef(false)

  // ── Initialize map ──────────────────────────────────────────────
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return

    const initialStyle = useDashboardStore.getState().mapStyle
    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: getStyleForMapStyleId(initialStyle),
      center: CENTER,
      zoom: 11.5,
      attributionControl: false,
    })

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right')

    map.on('click', (event: MapMouseEvent) => {
      poiPopupRef.current?.remove()
      poiPopupRef.current = null

      const { lng, lat } = event.lngLat
      const label = `Lat ${lat.toFixed(4)}, Lng ${lng.toFixed(4)}`
      const st = useDashboardStore.getState()

      // Compare: second click sets Zone B without changing Zone A
      if (st.activePanel === 'compare' && st.selectedCoordinates) {
        placeOrUpdateMarker(map, markerBRef, { lng, lat }, 'compare')
        st.setCompareZoneB({ lng, lat }, label)
        map.flyTo({ center: [lng, lat], zoom: 13, speed: 0.9 })
        return
      }

      // 🔒 Results lock: if analysis results are visible, ignore accidental
      // map clicks — the user must press X to clear before picking a new location
      if (st.score !== null || st.insightsLoading) return

      markerBRef.current?.remove()
      markerBRef.current = null
      placeOrUpdateMarker(map, markerRef, { lng, lat }, 'primary')
      map.flyTo({ center: [lng, lat], zoom: 13, speed: 0.9 })
      openControlsPanel()
      st.setSelectedLocation({ lng, lat }, label)
    })

    map.on('load', () => {
      mapReadyRef.current = true
      const st = useDashboardStore.getState()
      placeOrUpdateMarker(map, markerRef, st.selectedCoordinates, 'primary')
      placeOrUpdateMarker(map, markerBRef, st.compareZoneBCoordinates, 'compare')
      if (st.selectedCoordinates) {
        map.flyTo({ center: [st.selectedCoordinates.lng, st.selectedCoordinates.lat], zoom: 13, speed: 0.9 })
      }
    })

    mapRef.current = map
    return () => {
      mapReadyRef.current = false
      poiPopupRef.current?.remove()
      poiPopupRef.current = null
      markerRef.current?.remove()
      markerRef.current = null
      markerBRef.current?.remove()
      markerBRef.current = null
      extraMarkersRef.current.forEach(m => m.remove())
      extraMarkersRef.current = []
      map.remove()
      mapRef.current = null
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Style changes ────────────────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReadyRef.current) return
    map.setStyle(getStyleForMapStyleId(mapStyle))
    map.once('style.load', () => {
      const st = useDashboardStore.getState()
      placeOrUpdateMarker(map, markerRef, st.selectedCoordinates, 'primary')
      placeOrUpdateMarker(map, markerBRef, st.compareZoneBCoordinates, 'compare')
    })
  }, [mapStyle])

  // ── Primary marker + fly when coords set from outside or cleared ──
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReadyRef.current) return
    const run = () => {
      if (!selectedCoordinates) {
        markerRef.current?.remove()
        markerRef.current = null
        return
      }
      placeOrUpdateMarker(map, markerRef, selectedCoordinates, 'primary')
      if (score) {
        map.flyTo({ center: [selectedCoordinates.lng, selectedCoordinates.lat], zoom: 12.5, speed: 0.9 })
      } else {
        map.flyTo({ center: [selectedCoordinates.lng, selectedCoordinates.lat], zoom: 13, speed: 0.9 })
      }
    }
    if (!map.isStyleLoaded()) { map.once('style.load', run) } else { run() }
  }, [selectedCoordinates])

  // ── Compare Zone B marker ──
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReadyRef.current) return
    const run = () => {
      placeOrUpdateMarker(map, markerBRef, compareZoneBCoordinates, 'compare')
    }
    if (!map.isStyleLoaded()) { map.once('style.load', run) } else { run() }
  }, [compareZoneBCoordinates])

  // ── Cursor feedback: locked when results are visible ─────────────
  useEffect(() => {
    const canvas = mapRef.current?.getCanvas()
    if (!canvas) return
    // When results are shown, revert to normal grab cursor so the user knows
    // the map is in "view" mode. Crosshair = pick mode (no score yet).
    canvas.style.cursor = (score !== null || insightsLoading) ? '' : 'crosshair'
  }, [score, insightsLoading])

  // ── Render Radius and Competitors ──────────────────────────────
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReadyRef.current) return

    // clear markers + anchored popup
    poiPopupRef.current?.remove()
    poiPopupRef.current = null
    extraMarkersRef.current.forEach(m => m.remove())
    extraMarkersRef.current = []

    const draw = () => {
      if (score && selectedCoordinates) {
        // Draw Radius
        const rLayerSrc = map.getSource('radius') as maplibregl.GeoJSONSource
        const geoJSON = createGeoJSONCircle([selectedCoordinates.lng, selectedCoordinates.lat], radiusKm * 1000) as any
        console.log('[MapCanvas] Drawing Radius:', radiusKm, 'km', geoJSON)
        
        if (rLayerSrc) {
          rLayerSrc.setData(geoJSON)
        } else {
          map.addSource('radius', { type: 'geojson', data: geoJSON })
          map.addLayer({
            id: 'radius-fill',
            type: 'fill',
            source: 'radius',
            paint: { 'fill-color': '#06b6d4', 'fill-opacity': 0.1 }
          })
          map.addLayer({
            id: 'radius-line',
            type: 'line',
            source: 'radius',
            paint: { 'line-color': '#06b6d4', 'line-width': 2, 'line-dasharray': [4, 2] }
          })
        }

        // Add Competitors Locations if present
        const olaLocs = score.competitors?.olaMaps?.locations || []
        const osmLocs = score.competitors?.osm?.locations || []
        const allLocs = [...olaLocs, ...osmLocs]
        
        const seen = new Set<string>()
        console.log('[MapCanvas] Drawing Competitors:', allLocs.length)
        allLocs.forEach((loc, sourceIndex) => {
          const ln = coordLon(loc)
          if (!loc || loc.lat == null || ln == null) return
          const key = `${Number(loc.lat).toFixed(4)},${ln.toFixed(4)}`
          if (seen.has(key)) return
          seen.add(key)

          const title = pickCompetitorTitle(score, loc, sourceIndex, 'a')
          const catLabel = activeCategory.replace(/_/g, ' ')
          const el = document.createElement('div')
          el.className = 'w-3 h-3 rounded-full bg-red-500 border border-white shadow shadow-black/50'
          el.title = title
          el.style.cursor = 'pointer'
          el.addEventListener('click', (e) => {
            e.stopPropagation()
            e.preventDefault()
            openPoiPopup(map, poiPopupRef, ln, loc.lat, 'Competitor', title, [
              `${catLabel} · ${radiusKm} km search radius`,
            ])
          })
          const marker = new maplibregl.Marker({ element: el })
            .setLngLat([ln, loc.lat])
            .addTo(map)
          extraMarkersRef.current.push(marker)
        })

        // Add Landmarks (Nearby)
        if (nearbyData) {
          console.log('[MapCanvas] Drawing Landmarks:', nearbyData.length)
          nearbyData.forEach(l => {
            if (!l.lat || !l.lng) return
            const el = document.createElement('div')
            el.className = 'w-3 h-3 rounded bg-amber-400 border border-white shadow shadow-black/50'
            el.title = l.title
            el.style.cursor = 'pointer'
            el.addEventListener('click', (e) => {
              e.stopPropagation()
              e.preventDefault()
              openPoiPopup(map, poiPopupRef, l.lng!, l.lat!, 'Nearby place', l.title, [
                `${l.type} · ${l.distanceKm.toFixed(2)} km from site`,
              ])
            })
            const marker = new maplibregl.Marker({ element: el })
              .setLngLat([l.lng, l.lat])
              .addTo(map)
            extraMarkersRef.current.push(marker)
          })
        }
      } else {
        if (map.getLayer('radius-line')) map.removeLayer('radius-line')
        if (map.getLayer('radius-fill')) map.removeLayer('radius-fill')
        if (map.getSource('radius')) map.removeSource('radius')
      }

      // ── Draw Zone B ──
      if (compareScoreB && compareZoneBCoordinates) {
        const rLayerSrcB = map.getSource('radius-b') as maplibregl.GeoJSONSource
        const geoJSONB = createGeoJSONCircle([compareZoneBCoordinates.lng, compareZoneBCoordinates.lat], radiusKm * 1000) as any
        
        if (rLayerSrcB) {
          rLayerSrcB.setData(geoJSONB)
        } else {
          map.addSource('radius-b', { type: 'geojson', data: geoJSONB })
          map.addLayer({
            id: 'radius-b-fill',
            type: 'fill',
            source: 'radius-b',
            paint: { 'fill-color': '#c084fc', 'fill-opacity': 0.1 }
          })
          map.addLayer({
            id: 'radius-b-line',
            type: 'line',
            source: 'radius-b',
            paint: { 'line-color': '#c084fc', 'line-width': 2, 'line-dasharray': [4, 2] }
          })
        }

        // Add Zone B Competitors
        const olaLocsB = compareScoreB.competitors?.olaMaps?.locations || []
        const osmLocsB = compareScoreB.competitors?.osm?.locations || []
        const allLocsB = [...olaLocsB, ...osmLocsB]
        
        const seenB = new Set<string>()
        const catLabel = activeCategory.replace(/_/g, ' ')
        allLocsB.forEach((loc, sourceIndex) => {
          const ln = coordLon(loc)
          if (!loc || loc.lat == null || ln == null) return
          const key = `${Number(loc.lat).toFixed(4)},${ln.toFixed(4)}`
          if (seenB.has(key)) return
          seenB.add(key)

          const title = pickCompetitorTitle(compareScoreB, loc, sourceIndex, 'b')
          const el = document.createElement('div')
          el.className = 'w-3 h-3 rounded-full bg-violet-500 border border-white shadow shadow-black/50'
          el.title = title
          el.style.cursor = 'pointer'
          el.addEventListener('click', (e) => {
            e.stopPropagation()
            e.preventDefault()
            openPoiPopup(map, poiPopupRef, ln, loc.lat, 'Competitor', title, [
              `Compare zone B · ${catLabel} · ${radiusKm} km`,
            ])
          })
          const marker = new maplibregl.Marker({ element: el })
            .setLngLat([ln, loc.lat])
            .addTo(map)
          extraMarkersRef.current.push(marker)
        })
      } else {
        if (map.getLayer('radius-b-line')) map.removeLayer('radius-b-line')
        if (map.getLayer('radius-b-fill')) map.removeLayer('radius-b-fill')
        if (map.getSource('radius-b')) map.removeSource('radius-b')
      }
    }
    
    if (map.isStyleLoaded()) {
      draw()
    } else {
      map.once('style.load', draw)
    }

  }, [score, selectedCoordinates, nearbyData, radiusKm, compareScoreB, compareZoneBCoordinates, activeCategory])

  // ── Start Analyzing ─────────────────────────────────────────────
  const startAnalyzing = useCallback(async () => {
    const coords = useDashboardStore.getState().selectedCoordinates
    if (!coords || analyzingRef.current) return
    const curRadius = useDashboardStore.getState().analysisTools.radius * 1000
    const activeCat = useDashboardStore.getState().activeCategory
    const weights = useDashboardStore.getState().weights
    
    analyzingRef.current = true
    setAnalyzing(true)
    beginInsightsFetch()
    setInsightsOpenMobile(true)
    closeActivePanel()
    try {
      const [scoreResult, nearbyResult] = await Promise.all([
        getScore(coords, activeCat, curRadius, weights),
        getNearby(coords, curRadius),
      ])
      setInsightsData(scoreResult, nearbyResult)
    } catch {
      setInsightsError('Could not load insights. Try again.')
    } finally {
      analyzingRef.current = false
      setAnalyzing(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [beginInsightsFetch, setInsightsData, setInsightsError, setInsightsOpenMobile, closeActivePanel])

  return (
    <div className="relative h-full w-full">
      <div ref={mapContainerRef} className="h-full w-full" />

      {/* ── "Start Analyzing" CTA — shown whenever a location is selected ── */}
      <AnimatePresence>
        {selectedCoordinates && !analyzing && !insightsLoading && (
          <motion.div
            key="analyze-btn"
            initial={{ y: 20, opacity: 0, scale: 0.95 }}
            animate={{ y: 0, opacity: 1, scale: 1 }}
            exit={{ y: 12, opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
            className="absolute bottom-16 left-1/2 z-20 -translate-x-1/2"
          >
            <button
              type="button"
              onClick={startAnalyzing}
              title={score ? 'Re-run analysis for this location' : 'Analyse this location'}
              className="glass flex items-center gap-2 rounded-full px-5 py-3 text-sm font-semibold text-ui-text shadow-2xl transition hover:scale-105 active:scale-95"
              style={{ boxShadow: '0 8px 32px rgba(6,182,212,0.25)' }}
            >
              <Sparkles className="h-4 w-4 text-ui-accent" />
              {score ? 'Analyze again' : 'Start Analyzing'}
            </button>
          </motion.div>
        )}

        {analyzing && (
          <motion.div
            key="analyzing"
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute bottom-16 left-1/2 z-20 -translate-x-1/2"
          >
            <div className="glass flex items-center gap-2.5 rounded-full px-5 py-3 text-sm font-medium text-ui-muted shadow-xl">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-ui-accent/30 border-t-ui-accent" />
              Analysing…
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default memo(MapCanvasInner)
