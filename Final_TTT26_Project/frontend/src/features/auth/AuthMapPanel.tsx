import { memo, useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

/* ── 10 Indian metro cities ──────────────────────────────────────────────── */
const CITIES = [
  {
    name: 'Delhi NCR',
    region: 'National Capital Region',
    center: [77.2090, 28.6139] as [number, number],
    zoom: 13.2, pitch: 55, bearing: 18,
    fact: '🏛️ Delhi is home to the world\'s largest monolithic rock structure — the Qutb Minar, built in 1193 AD.',
  },
  {
    name: 'Mumbai',
    region: 'Maharashtra',
    center: [72.8652, 19.0596] as [number, number],   // BKC
    zoom: 13.4, pitch: 58, bearing: 24,
    fact: '🎬 Mumbai produces over 1,000 films a year — more than any other city on the planet.',
  },
  {
    name: 'Kolkata',
    region: 'West Bengal',
    center: [88.3502, 22.5448] as [number, number],   // Howrah Bridge area
    zoom: 13.5, pitch: 52, bearing: -12,
    fact: '🌉 The Howrah Bridge carries over 100,000 vehicles and 150,000 pedestrians every single day.',
  },
  {
    name: 'Chennai',
    region: 'Tamil Nadu',
    center: [80.2707, 13.0569] as [number, number],   // T. Nagar / Marina
    zoom: 13.3, pitch: 50, bearing: 8,
    fact: '🏖️ Marina Beach in Chennai is the world\'s second-longest urban beach at 13 km.',
  },
  {
    name: 'Bengaluru',
    region: 'Karnataka',
    center: [77.5946, 12.9716] as [number, number],   // MG Road
    zoom: 13.2, pitch: 54, bearing: -20,
    fact: '🌳 Bengaluru has over 1,000 parks and lakes, earning it the title of "Garden City of India".',
  },
  {
    name: 'Hyderabad',
    region: 'Telangana',
    center: [78.3741, 17.4401] as [number, number],   // HITEC City
    zoom: 13.0, pitch: 56, bearing: 30,
    fact: '💎 The famous Golconda Fort near Hyderabad was once traded for the Koh-i-Noor diamond.',
  },
  {
    name: 'Ahmedabad',
    region: 'Gujarat',
    center: [72.5714, 23.0225] as [number, number],   // CBD
    zoom: 13.5, pitch: 52, bearing: 14,
    fact: '🧵 Ahmedabad is Asia\'s first city to receive UNESCO World Heritage City status.',
  },
  {
    name: 'Pune',
    region: 'Maharashtra',
    center: [73.8553, 18.5204] as [number, number],   // Koregaon Park
    zoom: 13.4, pitch: 50, bearing: -8,
    fact: '📚 Pune has the highest concentration of engineering and management colleges in India.',
  },
  {
    name: 'Surat',
    region: 'Gujarat',
    center: [72.8311, 21.1702] as [number, number],   // Ring Road
    zoom: 13.2, pitch: 48, bearing: 22,
    fact: '💍 Surat processes over 90% of the world\'s rough diamonds, making it the diamond capital of the world.',
  },
  {
    name: 'Jaipur',
    region: 'Rajasthan',
    center: [75.8235, 26.9124] as [number, number],   // Pink City
    zoom: 13.0, pitch: 53, bearing: -15,
    fact: '🌸 Jaipur is called the Pink City because its entire Old City was painted pink in 1876 to welcome the Prince of Wales.',
  },
] as const

const STATS = [
  { label: 'Sites Analysed', value: '12,400+', color: '#22d3ee' },
  { label: 'AI Score Avg',   value: '91.3',    color: '#34d399' },
  { label: 'Cities Covered', value: '340',     color: '#67e8f9' },
]

/* ── Component ───────────────────────────────────────────────────────────── */
export const AuthMapPanel = memo(function AuthMapPanel() {
  // Pick a random city once — stable within a session, changes on refresh
  const [cityIdx] = useState(() => Math.floor(Math.random() * CITIES.length))
  const city = CITIES[cityIdx]

  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef       = useRef<maplibregl.Map | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const el = containerRef.current
    if (!el || mapRef.current) return

    const map = new maplibregl.Map({
      container:        el,
      style:            MAP_STYLE,
      center:           city.center,
      zoom:             city.zoom,
      pitch:            city.pitch,
      bearing:          city.bearing,
      interactive:      false,
      attributionControl: false,
    })
    mapRef.current = map
    map.on('load', () => setReady(true))

    return () => {
      map.remove()
      mapRef.current = null
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])   // city is stable (picked once on mount)

  const C = '#22d3ee'           // primary cyan
  const C2 = 'rgba(34,211,238,' // cyan with alpha prefix

  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden' }}>
      {/* Map */}
      <div ref={containerRef} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />

      {/* Loading placeholder */}
      {!ready && (
        <div style={{
          position: 'absolute', inset: 0, zIndex: 2,
          background: 'linear-gradient(135deg,#080c14 0%,#0d1520 100%)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{
            width: 36, height: 36, borderRadius: '50%',
            border: `2px solid ${C2}0.18)`,
            borderTopColor: C,
            animation: 'mpSpin .75s linear infinite',
          }} />
        </div>
      )}

      {/* Gradient overlays */}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 3,
        background: 'linear-gradient(to top, rgba(8,12,20,0.9) 0%, rgba(8,12,20,0.2) 50%, transparent 100%)' }} />
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 3,
        background: 'linear-gradient(to right, rgba(8,12,20,0.55) 0%, transparent 32%)' }} />

      {/* ── Top-left live badge ─────────────────────────────────── */}
      <div style={{
        position: 'absolute', top: 20, left: 20, zIndex: 10,
        display: 'flex', alignItems: 'center', gap: 8,
        background: 'rgba(8,12,20,0.80)', backdropFilter: 'blur(16px)',
        border: `1px solid ${C2}0.18)`,
        borderRadius: 12, padding: '7px 14px',
      }}>
        <span style={{
          width: 6, height: 6, borderRadius: '50%', background: C,
          flexShrink: 0, animation: 'mpPulse 2.4s ease-in-out infinite',
          boxShadow: `0 0 6px ${C}`,
        }} />
        <span style={{
          fontSize: 10, fontWeight: 700,
          color: 'rgba(255,255,255,0.82)',
          letterSpacing: '0.1em', textTransform: 'uppercase',
        }}>
          Live · {city.name}
        </span>
      </div>

      {/* ── City name card — top right ──────────────────────────── */}
      <div style={{
        position: 'absolute', top: 20, right: 20, zIndex: 10,
        background: 'rgba(8,12,20,0.78)', backdropFilter: 'blur(16px)',
        border: `1px solid ${C2}0.14)`,
        borderRadius: 12, padding: '10px 14px', maxWidth: 180,
      }}>
        <p style={{ margin: 0, fontSize: 13, fontWeight: 700, color: C, letterSpacing: '-0.02em' }}>
          {city.name}
        </p>
        <p style={{ margin: '3px 0 0', fontSize: 10, color: 'rgba(255,255,255,0.42)', lineHeight: 1.5 }}>
          {city.region} · India
        </p>
      </div>

      {/* ── Centre pulse marker ─────────────────────────────────── */}
      <div style={{
        position: 'absolute', top: '50%', left: '50%',
        transform: 'translate(-50%,-50%)',
        pointerEvents: 'none', zIndex: 9,
      }}>
        <div style={{ position: 'relative', width: 18, height: 18, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ position: 'absolute', width: 42, height: 42, borderRadius: '50%',
            background: `${C2}0.18)`, animation: 'mpPing 2.2s ease-out infinite' }} />
          <div style={{ position: 'absolute', width: 26, height: 26, borderRadius: '50%',
            background: `${C2}0.10)`, animation: 'mpPing 2.2s ease-out infinite .5s' }} />
          <div style={{ width: 13, height: 13, borderRadius: '50%', background: C,
            boxShadow: `0 0 0 3px ${C2}0.28), 0 0 24px ${C2}0.5)` }} />
        </div>
      </div>

      {/* ── Fun fact card ───────────────────────────────────────── */}
      <div style={{
        position: 'absolute', bottom: 100, left: 16, right: 16, zIndex: 10,
        background: 'rgba(8,12,20,0.82)', backdropFilter: 'blur(20px)',
        border: `1px solid ${C2}0.22)`,
        borderRadius: 14, padding: '12px 16px',
        animation: 'mpSlide .6s cubic-bezier(.22,1,.36,1) .2s both',
      }}>
        <p style={{ margin: '0 0 4px', fontSize: 9, fontWeight: 700,
          color: C, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
          Did You Know?
        </p>
        <p style={{ margin: 0, fontSize: 12, color: 'rgba(255,255,255,0.72)', lineHeight: 1.65 }}>
          {city.fact}
        </p>
      </div>

      {/* ── Bottom stat cards ───────────────────────────────────── */}
      <div style={{
        position: 'absolute', bottom: 22, left: 16, right: 16, zIndex: 10,
        display: 'flex', gap: 8,
      }}>
        {STATS.map((s, i) => (
          <div key={s.label} style={{
            flex: 1, borderRadius: 14,
            background: 'rgba(8,12,20,0.82)', backdropFilter: 'blur(18px)',
            border: `1px solid ${C2}0.10)`,
            padding: '12px 14px',
            animation: `mpSlide .5s cubic-bezier(.22,1,.36,1) ${.35 + i * .08}s both`,
          }}>
            <p style={{ margin: 0, fontSize: 19, fontWeight: 800, color: s.color, letterSpacing: '-0.03em' }}>
              {s.value}
            </p>
            <p style={{ margin: '3px 0 0', fontSize: 9, fontWeight: 600,
              color: 'rgba(255,255,255,0.35)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              {s.label}
            </p>
          </div>
        ))}
      </div>

      {/* Attribution */}
      <div style={{
        position: 'absolute', bottom: 5, right: 8, zIndex: 10,
        fontSize: 9, color: 'rgba(255,255,255,0.22)',
        background: 'rgba(0,0,0,0.3)', borderRadius: 4, padding: '2px 5px',
      }}>
        © CARTO · OpenStreetMap
      </div>

      <style>{`
        @keyframes mpSpin  { to { transform: rotate(360deg); } }
        @keyframes mpPulse { 0%,100%{opacity:1} 50%{opacity:.28} }
        @keyframes mpPing  { 0%{transform:scale(.8);opacity:.75} 100%{transform:scale(2.6);opacity:0} }
        @keyframes mpSlide { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:none} }
      `}</style>
    </div>
  )
})
