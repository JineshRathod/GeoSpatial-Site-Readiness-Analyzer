import { AnimatePresence, motion } from 'framer-motion'
import {
  AlertCircle,
  Building2,
  ChevronDown,
  Download,
  GitCompareArrows,
  Bookmark,
  Share2,
  Sparkles,
  Store,
  Train,
  X,
  MapPin,
  Wind,
  Thermometer,
  Droplets,
  Activity,
  Users,
  Map,
  Navigation,
  TreePine,
  ShieldCheck,
  Clock,
  TrendingUp,
  Radio,
} from 'lucide-react'
import { useRef, useState } from 'react'
import { Speedometer } from '../../components/charts/Speedometer'
import { GlassPanel } from '../../components/glass/GlassPanel'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/Toast'
import { SIDE_PANEL_HEIGHT, SIDE_PANEL_TOP, SIDE_PANEL_WIDTH } from '../../constants/dashboardPanelLayout'
import { useDashboardStore } from '../../store/dashboardStore'

// ── Helpers ────────────────────────────────────────────────────────────────

function MoreActionsMenu({ onClose }: { onClose: () => void }) {
  const { toast } = useToast()
  const actions = [
    {
      icon: Bookmark,
      label: 'Save Location',
      onClick: () => { toast('Location saved!'); onClose() },
    },
    {
      icon: Share2,
      label: 'Share',
      onClick: () => {
        navigator.clipboard?.writeText(window.location.href)
          .then(() => toast('Link copied!'))
          .catch(() => toast('Share link generated'))
        onClose()
      },
    },
  ]
  return (
    <motion.div
      initial={{ opacity: 0, y: -6, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -4, scale: 0.97 }}
      transition={{ duration: 0.18, ease: 'easeOut' }}
      className="surface-panel absolute right-0 top-full z-50 mt-2 w-48 overflow-hidden rounded-2xl p-1.5"
    >
      {actions.map(({ icon: Icon, label, onClick }) => (
        <button
          key={label}
          type="button"
          onClick={onClick}
          className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-xs font-medium text-ui-text transition hover:bg-ui-surface-hover"
        >
          <Icon className="h-4 w-4 shrink-0 text-ui-muted" />
          {label}
        </button>
      ))}
    </motion.div>
  )
}

// ── Accordion section ──────────────────────────────────────────────────────

function Section({
  icon: Icon,
  title,
  accent = false,
  defaultOpen = false,
  badge,
  children,
}: {
  icon: React.ElementType
  title: string
  accent?: boolean
  defaultOpen?: boolean
  badge?: string
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className={`rounded-xl border ${accent ? 'border-ui-accent/30 bg-ui-accent/5' : 'border-ui-border/40 bg-ui-surface-hover/20'} overflow-hidden`}>
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="flex w-full items-center gap-2.5 px-3.5 py-2.5 text-left transition hover:bg-white/5"
      >
        <Icon className={`h-3.5 w-3.5 shrink-0 ${accent ? 'text-ui-accent' : 'text-ui-muted'}`} />
        <span className="flex-1 text-[11px] font-bold uppercase tracking-wider text-ui-text">{title}</span>
        {badge && (
          <span className="rounded-full bg-ui-accent/20 px-2 py-0.5 text-[10px] font-semibold text-ui-accent">
            {badge}
          </span>
        )}
        <ChevronDown className={`h-3.5 w-3.5 text-ui-muted transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden"
          >
            <div className="px-3.5 pb-3.5 pt-1">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Stat row ──────────────────────────────────────────────────────────────

function StatRow({ label, value, unit, icon: Icon }: { label: string; value: string | number; unit?: string; icon?: React.ElementType }) {
  return (
    <div className="flex items-center justify-between py-1 border-b border-ui-border/20 last:border-0">
      <span className="flex items-center gap-1.5 text-[10px] text-ui-muted">
        {Icon && <Icon className="h-3 w-3" />}
        {label}
      </span>
      <span className="text-[11px] font-semibold text-ui-text tabular-nums">
        {value}{unit && <span className="ml-0.5 text-[9px] font-normal text-ui-muted">{unit}</span>}
      </span>
    </div>
  )
}

// ── AQI badge ─────────────────────────────────────────────────────────────

function AqiBadge({ aqi }: { aqi: number }) {
  const level =
    aqi <= 50 ? { label: 'Good', color: 'bg-emerald-500/20 text-emerald-400' } :
      aqi <= 100 ? { label: 'Moderate', color: 'bg-yellow-500/20 text-yellow-400' } :
        aqi <= 150 ? { label: 'Unhealthy', color: 'bg-orange-500/20 text-orange-400' } :
          { label: 'Hazardous', color: 'bg-red-500/20 text-red-400' }
  return (
    <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${level.color}`}>
      {level.label}
    </span>
  )
}

// ── Risk badge ────────────────────────────────────────────────────────────

function RiskBadge({ risk }: { risk: string }) {
  const color =
    risk === 'Low' ? 'bg-emerald-500/20 text-emerald-400' :
      risk === 'Medium' ? 'bg-yellow-500/20 text-yellow-400' :
        'bg-red-500/20 text-red-400'
  return <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${color}`}>{risk}</span>
}

// ── Zone chip ─────────────────────────────────────────────────────────────

function ZoneChip({ zone, count }: { zone: string; count: number }) {
  const label = zone.replace(/_/g, ' ').replace('natural ', '').replace('leisure ', '')
  return (
    <div className="flex items-center justify-between rounded-lg bg-ui-surface-hover/50 px-2 py-1">
      <span className="text-[10px] capitalize text-ui-muted">{label}</span>
      <span className="text-[10px] font-bold text-ui-text">{count}</span>
    </div>
  )
}

/* ── Main component ──────────────────────────────────────────── */
export function InsightsPanel({ mobile = false }: { mobile?: boolean }) {
  const selectedCoordinates = useDashboardStore((s) => s.selectedCoordinates)
  const selectedLocationLabel = useDashboardStore((s) => s.selectedLocationLabel)
  const score = useDashboardStore((s) => s.score)
  const nearby = useDashboardStore((s) => s.nearby)
  const insightsLoading = useDashboardStore((s) => s.insightsLoading)
  const insightsError = useDashboardStore((s) => s.insightsError)
  const open = useDashboardStore((s) => s.insightsOpenMobile)
  const setOpen = useDashboardStore((s) => s.setInsightsOpenMobile)
  const setActivePanel = useDashboardStore((s) => s.setActivePanel)
  const { toast } = useToast()

  const [moreOpen, setMoreOpen] = useState(false)
  const moreRef = useRef<HTMLDivElement>(null)

  if (!selectedCoordinates) return null

  /** Location picked but user has not started analysis yet — hide panel entirely. */
  const analysisIdle = !insightsLoading && !insightsError && !score
  if (analysisIdle) return null

  // ── Error state ─────────────────────────────────────────────
  if (insightsError) {
    const errorPanel = (
      <GlassPanel className="flex items-start gap-4 p-6 shadow-xl">
        <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-amber-400" />
        <div>
          <p className="text-sm font-semibold text-ui-text">Something went wrong</p>
          <p className="mt-1 text-xs text-ui-muted">{insightsError}</p>
          <button
            type="button"
            onClick={() => toast('Retry by selecting the map again')}
            className="mt-4 rounded-xl border border-ui-border bg-ui-glass px-4 py-2 text-xs font-medium hover:bg-ui-surface-hover transition-colors"
          >
            Dismiss
          </button>
        </div>
      </GlassPanel>
    )
    if (!mobile) return <DesktopWrapper>{errorPanel}</DesktopWrapper>
    return <MobileWrapper open={open} setOpen={setOpen}>{errorPanel}</MobileWrapper>
  }

  // ── Loading state (only while a fetch is in flight — not before "Start Analyzing") ──
  if (insightsLoading) {
    const loadPanel = (
      <GlassPanel className="space-y-6 p-6 shadow-xl">
        <div className="flex items-center gap-3">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-ui-accent/30 border-t-ui-accent" />
          <p className="text-sm font-semibold text-ui-text">Analysing location…</p>
        </div>
        <Skeleton className="mx-auto h-44 w-44 rounded-full" />
        <div className="space-y-3">
          <Skeleton className="h-2 w-full rounded-full" />
          <Skeleton className="h-2 w-5/6 rounded-full" />
          <Skeleton className="h-2 w-4/6 rounded-full" />
        </div>
      </GlassPanel>
    )
    if (!mobile) return <DesktopWrapper>{loadPanel}</DesktopWrapper>
    return <MobileWrapper open={open} setOpen={setOpen}>{loadPanel}</MobileWrapper>
  }

  if (!score) return null

  const getNearbyIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case 'competitor': return <Store className="h-4 w-4" />
      case 'transport': return <Train className="h-4 w-4" />
      default: return <Building2 className="h-4 w-4" />
    }
  }

  // ── PDF Download ────────────────────────────────────────────
  const handleDownloadPDF = () => {
    const bar = (val: number, color = '#6366f1') =>
      `<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
        <span style="width:120px;font-size:12px;color:#555">${''}</span>
        <div style="flex:1;background:#e5e7eb;border-radius:4px;height:14px;overflow:hidden">
          <div style="width:${val}%;height:100%;background:${color};border-radius:4px"></div>
        </div>
        <span style="width:32px;font-size:12px;font-weight:600;color:#111;text-align:right">${val}</span>
      </div>`

    const scoreRows = [
      { label: 'Population',    value: score.populationScore,    color: '#6366f1' },
      { label: 'Accessibility', value: score.accessibilityScore, color: '#0ea5e9' },
      { label: 'Competition',   value: score.competitionScore,   color: '#f59e0b' },
      { label: 'Risk',          value: score.riskScore,          color: '#ef4444' },
    ]

    const barChartSVG = `
      <svg viewBox="0 0 340 160" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:340px;display:block;margin:0 auto">
        ${scoreRows.map((r, i) => {
          const barW = (r.value / 100) * 280
          const y = i * 36 + 10
          return `
            <text x="0" y="${y + 18}" font-size="11" fill="#555" font-family="sans-serif">${r.label}</text>
            <rect x="90" y="${y + 4}" width="280" height="18" rx="4" fill="#e5e7eb"/>
            <rect x="90" y="${y + 4}" width="${barW}" height="18" rx="4" fill="${r.color}"/>
            <text x="${90 + barW + 6}" y="${y + 18}" font-size="11" font-weight="bold" fill="#111" font-family="sans-serif">${r.value}</text>
          `
        }).join('')}
      </svg>`

    const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <title>GeoSpatial Analysis Report</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    * { margin:0; padding:0; box-sizing:border-box; }
    body { font-family:'Inter',sans-serif; background:#f9fafb; color:#111; padding:40px; }
    .page { max-width:720px; margin:0 auto; background:#fff; border-radius:16px; padding:40px; box-shadow:0 4px 24px rgba(0,0,0,0.08); }
    h1 { font-size:22px; font-weight:700; color:#111; border-bottom:3px solid #6366f1; padding-bottom:10px; margin-bottom:6px; }
    .subtitle { font-size:13px; color:#6b7280; margin-bottom:28px; }
    h2 { font-size:15px; font-weight:700; color:#1f2937; margin:28px 0 12px; display:flex; align-items:center; gap:8px; }
    h2::before { content:''; display:inline-block; width:4px; height:16px; border-radius:2px; background:#6366f1; }
    .score-big { font-size:48px; font-weight:700; color:#6366f1; text-align:center; margin:12px 0 4px; }
    .score-label { text-align:center; font-size:13px; color:#6b7280; margin-bottom:24px; }
    .grid2 { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:16px; }
    .card { background:#f3f4f6; border-radius:10px; padding:16px; }
    .card-title { font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.08em; color:#6b7280; margin-bottom:10px; }
    .row { display:flex; justify-content:space-between; font-size:12px; padding:5px 0; border-bottom:1px solid #e5e7eb; }
    .row:last-child { border:none; }
    .row span:first-child { color:#555; }
    .row span:last-child { font-weight:600; color:#111; }
    .badge { display:inline-block; padding:2px 8px; border-radius:999px; font-size:10px; font-weight:700; }
    .badge-green { background:#dcfce7; color:#166534; }
    .badge-yellow { background:#fef9c3; color:#854d0e; }
    .badge-red { background:#fee2e2; color:#991b1b; }
    .ai-box { background:linear-gradient(135deg,#ede9fe,#f5f3ff); border-left:4px solid #8b5cf6; border-radius:10px; padding:16px; margin-top:28px; }
    .ai-title { font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.08em; color:#7c3aed; margin-bottom:8px; }
    .ai-text { font-size:13px; color:#374151; line-height:1.7; }
    .meta { font-size:10px; color:#9ca3af; margin-top:32px; text-align:center; }
    @media print { body{padding:0} .page{box-shadow:none;border-radius:0} }
  </style>
</head>
<body>
<div class="page">
  <h1>GeoSpatial Site Readiness Report</h1>
  <p class="subtitle">📍 ${selectedLocationLabel} &nbsp;|&nbsp; Generated ${new Date().toLocaleString()}</p>

  <h2>Overall Score</h2>
  <div class="score-big">${score.totalScore.toFixed(1)}<span style="font-size:22px;color:#9ca3af">/100</span></div>
  <p class="score-label">Site Readiness Index</p>

  <h2>Score Breakdown</h2>
  ${barChartSVG}
  <div style="margin-top:16px">
    ${scoreRows.map(r => `
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
        <span style="width:110px;font-size:12px;color:#555">${r.label}</span>
        <div style="flex:1;background:#e5e7eb;border-radius:4px;height:12px;overflow:hidden">
          <div style="width:${r.value}%;height:100%;background:${r.color};border-radius:4px"></div>
        </div>
        <span style="width:28px;font-size:12px;font-weight:700;color:#111;text-align:right">${r.value}</span>
      </div>
    `).join('')}
  </div>

  <h2>Environment &amp; Infrastructure</h2>
  <div class="grid2">
    ${score.weather ? `
    <div class="card">
      <div class="card-title">Weather &amp; Air Quality</div>
      <div class="row"><span>Avg Temperature</span><span>${score.weather.avgTemperatureC.toFixed(1)} °C</span></div>
      <div class="row"><span>Precipitation</span><span>${score.weather.avgPrecipitationMmDay.toFixed(2)} mm/day</span></div>
      <div class="row"><span>Wind Speed</span><span>${score.weather.avgWindSpeedKmh.toFixed(1)} km/h</span></div>
      <div class="row"><span>PM2.5</span><span>${score.weather.avgPm25.toFixed(1)} µg/m³</span></div>
      <div class="row"><span>US AQI</span><span>
        <span class="badge ${score.weather.avgUsAqi <= 50 ? 'badge-green' : score.weather.avgUsAqi <= 100 ? 'badge-yellow' : 'badge-red'}">${score.weather.avgUsAqi.toFixed(0)}</span>
      </span></div>
      <div class="row"><span>Days Sampled</span><span>${score.weather.daysFetched}</span></div>
    </div>` : ''}
    ${score.flood ? `
    <div class="card">
      <div class="card-title">Flood &amp; Elevation</div>
      <div class="row"><span>Elevation</span><span>${score.flood.elevationM.toFixed(1)} m asl</span></div>
      <div class="row"><span>Flood Risk</span><span>
        <span class="badge ${score.flood.riskLevel === 'Low' ? 'badge-green' : score.flood.riskLevel === 'Medium' ? 'badge-yellow' : 'badge-red'}">${score.flood.riskLevel}</span>
      </span></div>
    </div>` : ''}
    ${score.roads ? `
    <div class="card">
      <div class="card-title">Road Network</div>
      <div class="row"><span>Total Length</span><span>${score.roads.totalLengthKm.toFixed(1)} km</span></div>
      <div class="row"><span>Total Ways</span><span>${score.roads.totalWays.toLocaleString()}</span></div>
      <div class="row"><span>Intersections</span><span>${score.roads.intersections.toLocaleString()}</span></div>
      <div class="row"><span>Dead-ends</span><span>${score.roads.deadEnds.toLocaleString()}</span></div>
      <div class="row"><span>Dominant Type</span><span>${score.roads.topHighwayTypes[0] ?? '—'}</span></div>
    </div>` : ''}
    ${score.zoning ? `
    <div class="card">
      <div class="card-title">Land Use / Zoning</div>
      <div class="row"><span>Dominant Zone</span><span>${score.zoning.dominantZone.replace(/_/g,' ')}</span></div>
      <div class="row"><span>Total Polygons</span><span>${score.zoning.totalPolygons.toLocaleString()}</span></div>
      <div class="row"><span>Commercial Friendly</span><span>
        <span class="badge ${score.zoning.commercialFriendly ? 'badge-green' : 'badge-red'}">${score.zoning.commercialFriendly ? 'Yes' : 'No'}</span>
      </span></div>
    </div>` : ''}
  </div>

  ${score.competitors ? `
  <h2>Competitor Overview</h2>
  <div class="grid2">
    ${score.competitors.olaMaps ? `
    <div class="card">
      <div class="card-title">Ola Maps (${score.competitors.olaMaps.total} found)</div>
      ${score.competitors.olaMaps.sampleNames.slice(0,5).map(n => `<div class="row"><span>${n}</span></div>`).join('')}
    </div>` : ''}
    ${score.competitors.osm ? `
    <div class="card">
      <div class="card-title">OSM (${score.competitors.osm.total} found)</div>
      ${score.competitors.osm.sampleNames.slice(0,5).map(n => `<div class="row"><span>${n}</span></div>`).join('')}
    </div>` : ''}
  </div>` : ''}

  <div class="ai-box">
    <div class="ai-title">✦ AI Summary</div>
    <p class="ai-text">
      ${score.zoning?.commercialFriendly ? 'High potential retail zone. ' : 'Moderate commercial potential. '}
      ${score.weather && score.weather.avgUsAqi <= 100 ? 'Air quality is acceptable. ' : 'Air quality may be a concern for outdoor operations. '}
      ${score.flood?.riskLevel === 'Low' ? 'Flood risk is minimal. ' : `${score.flood?.riskLevel} flood risk detected — consider mitigation. `}
      ${score.roads ? `Well-connected area with ${score.roads.topHighwayTypes[0]} roads dominating.` : 'Road connectivity data unavailable.'}
    </p>
  </div>

  <p class="meta">GeoSpatial Site Readiness Analyzer &nbsp;·&nbsp; ${new Date().toLocaleDateString()}</p>
</div>
<script>window.onload=()=>{window.print();setTimeout(()=>window.close(),1000)}</script>
</body></html>`

    const win = window.open('', '_blank', 'width=800,height=900')
    if (win) {
      win.document.write(html)
      win.document.close()
      toast('PDF report ready — save as PDF from the print dialog')
    } else {
      toast('Allow pop-ups to download the report')
    }
  }

  // ── Full results panel ───────────────────────────────────────
  const contentPanel = (
    <GlassPanel className="flex flex-col gap-4 p-5 shadow-[0_8px_32px_rgba(0,0,0,0.45)] border border-white/10 relative overflow-visible backdrop-blur-2xl">
      {/* Inner glow */}
      <div className="absolute top-[-20%] right-[-20%] w-[140%] h-[140%] bg-[radial-gradient(ellipse_at_top_right,rgba(18,78,102,0.1),transparent_50%)] pointer-events-none" />

      {/* Header */}
      <div className="flex items-start justify-between gap-3 relative z-10">
        <div>
          <p className="text-[10px] uppercase tracking-wider text-ui-muted font-bold flex items-center gap-1">
            <MapPin className="h-3 w-3" /> Location
          </p>
          <p className="text-sm font-semibold text-ui-text mt-1 leading-tight">{selectedLocationLabel}</p>
        </div>
        <div className="relative shrink-0" ref={moreRef}>
          <button
            type="button"
            onClick={() => setMoreOpen((v) => !v)}
            className="flex items-center gap-1.5 rounded-full border border-ui-border bg-ui-surface-hover/30 px-3 py-1.5 text-[11px] font-medium text-ui-text transition hover:bg-ui-surface-hover"
          >
            More
            <ChevronDown className={`h-3.5 w-3.5 transition-transform duration-200 ${moreOpen ? 'rotate-180' : ''}`} />
          </button>
          <AnimatePresence>
            {moreOpen && <MoreActionsMenu onClose={() => setMoreOpen(false)} />}
          </AnimatePresence>
        </div>
      </div>

      <div className="h-px w-full bg-gradient-to-r from-ui-border via-ui-border/50 to-transparent" />

      {/* BLOCK 1: Score */}
      <div className="relative z-10">
        <Speedometer score={score.totalScore} />
      </div>

      <div className="h-px w-full bg-gradient-to-r from-transparent via-ui-border/50 to-transparent" />

      {/* BLOCK 2: Score Breakdown */}
      <div className="space-y-3 relative z-10">
        <p className="text-[10px] font-bold uppercase tracking-wider text-ui-muted">Score Breakdown</p>
        {[
          { label: 'Population', value: score.populationScore },
          { label: 'Accessibility', value: score.accessibilityScore },
          { label: 'Competition', value: score.competitionScore },
          { label: 'Risk', value: score.riskScore },
        ].map((item) => (
          <div key={item.label}>
            <div className="mb-1.5 flex justify-between text-xs">
              <span className="text-ui-muted font-medium">{item.label}</span>
              <span className="font-semibold text-ui-text">{item.value}</span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-ui-border/40">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${item.value}%` }}
                transition={{ duration: 1.2, ease: [0.22, 1, 0.36, 1] }}
                className="h-full rounded-full bg-gradient-to-r from-ui-accent to-[#86EFAC]"
              />
            </div>
          </div>
        ))}
      </div>

      <div className="h-px w-full bg-gradient-to-r from-transparent via-ui-border/50 to-transparent" />

      {/* BLOCK 3: Rich Data Sections */}
      <div className="space-y-2 relative z-10">

        {/* Population */}
        {score.population && (
          <Section icon={Users} title="Population Demographics" defaultOpen>
            <div className="space-y-0.5">
              <StatRow label="Total Est. Population" value={score.population.total.toLocaleString()} />
              <StatRow label="Density Level" value={score.population.level} />
              <div className="flex items-center justify-between py-1 border-b border-ui-border/20">
                <span className="text-[10px] text-ui-muted">Source Provider</span>
                <span className="text-[10px] font-medium text-ui-text bg-ui-surface-hover/50 px-1.5 py-0.5 rounded capitalize">
                  {score.population.sourceDetail.split('_').join(' ')}
                </span>
              </div>
            </div>
            {Object.keys(score.population.ageGroups).length > 0 && (
              <div className="mt-3">
                <p className="text-[9px] font-bold uppercase tracking-widest text-ui-muted mb-1.5 hidden md:block">Age Distribution Profile</p>
                <div className="grid grid-cols-2 gap-1.5">
                  {Object.entries(score.population.ageGroups).map(([group, val]) => {
                    const pct = (val / Math.max(1, score.population!.total)) * 100
                    return (
                      <div key={group} className="flex items-center justify-between bg-ui-surface-hover/30 rounded px-2 py-1 border border-ui-border/20">
                        <span className="text-[10px] text-ui-muted">{group.replace('_', '-')}</span>
                        <span className="text-[10px] font-bold text-ui-accent">{pct.toFixed(1)}%</span>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </Section>
        )}

        {/* Roads */}
        {score.roads && (
          <Section icon={Navigation} title="Road Network" badge={`${score.roads.totalWays.toLocaleString()} ways`}>
            <div className="space-y-0.5">
              <StatRow label="Total Length" value={score.roads.totalLengthKm.toFixed(1)} unit="km" />
              <StatRow label="Intersections" value={score.roads.intersections.toLocaleString()} />
              <StatRow label="Dead-ends" value={score.roads.deadEnds.toLocaleString()} />
              <StatRow label="Elapsed" value={score.roads.elapsedSeconds.toFixed(1)} unit="s" />
            </div>
            <div className="mt-2 flex flex-wrap gap-1">
              {score.roads.topHighwayTypes.map((t) => (
                <span key={t} className="rounded-full bg-ui-accent/10 px-2 py-0.5 text-[10px] font-medium capitalize text-ui-accent">
                  {t}
                </span>
              ))}
            </div>
          </Section>
        )}

        {/* Weather + AQI */}
        {score.weather && (
          <Section icon={Wind} title="Weather & Air Quality" defaultOpen>
            <div className="space-y-0.5">
              <div className="flex items-center justify-between py-1 border-b border-ui-border/20">
                <span className="flex items-center gap-1.5 text-[10px] text-ui-muted">
                  <Activity className="h-3 w-3" />
                  US AQI
                </span>
                <div className="flex items-center gap-1.5">
                  <span className="text-[11px] font-semibold text-ui-text tabular-nums">{score.weather.avgUsAqi.toFixed(0)}</span>
                  <AqiBadge aqi={score.weather.avgUsAqi} />
                </div>
              </div>
            </div>
          </Section>
        )}

        {/* Flood Risk */}
        {score.flood && (
          <Section icon={ShieldCheck} title="Flood & Elevation">
            <div className="space-y-0.5">
              <StatRow label="Elevation" value={score.flood.elevationM.toFixed(1)} unit="m asl" />
              <div className="flex items-center justify-between py-1 border-b border-ui-border/20 last:border-0">
                <span className="text-[10px] text-ui-muted">Flood Risk</span>
                <RiskBadge risk={score.flood.riskLevel} />
              </div>
            </div>
          </Section>
        )}


        {/* Zoning */}
        {score.zoning && (
          <Section icon={Map} title="Land Use / Zoning" badge={`${score.zoning.totalPolygons.toLocaleString()} polygons`}>
            <div className="space-y-0.5 mb-2">
              <StatRow label="Dominant Zone" value={score.zoning.dominantZone.replace(/_/g, ' ')} />
              <div className="flex items-center justify-between py-1 border-b border-ui-border/20">
                <span className="text-[10px] text-ui-muted">Commercial Friendly</span>
                <span className={`text-[10px] font-bold ${score.zoning.commercialFriendly ? 'text-emerald-400' : 'text-red-400'}`}>
                  {score.zoning.commercialFriendly ? '✓ Yes' : '✗ No'}
                </span>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-1">
              {Object.entries(score.zoning.zoneBreakdown)
                .sort(([, a], [, b]) => b - a)
                .slice(0, 6)
                .map(([zone, count]) => (
                  <ZoneChip key={zone} zone={zone} count={count} />
                ))}
            </div>
          </Section>
        )}

        {/* Competitors — full list (scrollable); merged Ola+OSM uses osm.sourceLabel */}
        {score.competitors && (
          <Section
            icon={TrendingUp}
            title="Competition"
            badge={`${(score.competitors.olaMaps?.total ?? 0) + (score.competitors.osm?.total ?? 0)} found`}
            defaultOpen
          >
            {score.competitors.olaMaps && (
              <div className="mb-3">
                <p className="text-[9px] font-bold uppercase tracking-widest text-ui-muted mb-1">
                  Ola Maps ({score.competitors.olaMaps.total})
                </p>
                <div className="max-h-48 overflow-y-auto rounded-xl border border-ui-border/40 bg-ui-surface-hover/20 p-2 scrollbar-hide">
                  <div className="flex flex-wrap gap-1">
                    {score.competitors.olaMaps.sampleNames.map((n, i) => (
                      <span key={`ola-${i}-${n.slice(0, 24)}`} className="rounded-lg bg-ui-surface-hover/60 px-2 py-0.5 text-[10px] text-ui-text">
                        {n}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}
            {score.competitors.osm && (
              <div>
                <p className="text-[9px] font-bold uppercase tracking-widest text-ui-muted mb-1">
                  {score.competitors.osm.sourceLabel ?? `OpenStreetMap (${score.competitors.osm.total})`}
                </p>
                <div className="max-h-64 overflow-y-auto rounded-xl border border-ui-border/40 bg-ui-surface-hover/20 p-2 scrollbar-hide">
                  <div className="flex flex-col gap-1">
                    {score.competitors.osm.sampleNames.map((n, i) => (
                      <span
                        key={`osm-${i}-${n.slice(0, 32)}`}
                        className="rounded-lg bg-ui-surface-hover/60 px-2 py-1 text-[10px] leading-snug text-ui-text"
                      >
                        {n}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </Section>
        )}

        {/* Cell Towers */}
        {score.cellTowers && (
          <Section icon={Radio} title="Telecom Connectivity" badge={`${score.cellTowers.totalTowers} towers`}>
            <div className="space-y-0.5 mb-2">
              <StatRow label="Coverage Quality" value={score.cellTowers.coverageQuality} />
              <StatRow label="Coverage Score" value={`${score.cellTowers.coverageScore} / 100`} />
            </div>
          </Section>
        )}

        {/* Nearby POIs */}
        {nearby.length > 0 && (
          <Section icon={TreePine} title="Nearby POIs">
            <div className="flex flex-col gap-1.5">
              {nearby.map((item) => (
                <div
                  key={item.id}
                  className="group flex items-center gap-3 rounded-xl border border-ui-border/40 bg-ui-surface-hover/40 p-2.5 text-xs transition-all duration-300 hover:scale-[1.02] hover:border-ui-accent/50 hover:bg-ui-surface-hover hover:shadow-lg"
                >
                  <div className="flex h-7 w-7 items-center justify-center rounded-full bg-ui-accent/10 text-ui-accent transition-colors group-hover:bg-ui-accent/20">
                    {getNearbyIcon(item.type)}
                  </div>
                  <div>
                    <p className="font-semibold text-ui-text">{item.title}</p>
                    <p className="text-[10px] uppercase text-ui-muted mt-0.5">{item.type} · {item.distanceKm} km</p>
                  </div>
                </div>
              ))}
            </div>
          </Section>
        )}
      </div>

      {/* BLOCK 4: AI Summary */}
      <div className="relative z-10 rounded-xl border-y border-r border-l-4 border-l-purple-500 border-y-purple-500/20 border-r-purple-500/20 bg-gradient-to-r from-purple-500/10 to-transparent p-4 shadow-[inset_0_0_12px_rgba(139,92,246,0.08)]">
        <div className="flex items-center gap-1.5 text-purple-400 mb-2">
          <Sparkles className="h-4 w-4" />
          <span className="font-bold text-[10px] uppercase tracking-widest">AI Summary</span>
        </div>
        <p className="text-xs leading-relaxed text-ui-text/90">
          {score.zoning?.commercialFriendly
            ? 'High potential retail zone. '
            : 'Moderate commercial potential. '}
          {score.weather && score.weather.avgUsAqi <= 100
            ? 'Air quality is acceptable. '
            : 'Air quality may be a concern for outdoor operations. '}
          {score.flood?.riskLevel === 'Low'
            ? 'Flood risk is minimal. '
            : `${score.flood?.riskLevel} flood risk detected — consider mitigation. `}
          {score.roads
            ? `Well-connected area with ${score.roads.topHighwayTypes[0]} roads dominating.`
            : 'Road connectivity data unavailable.'}
        </p>
      </div>

      {/* BLOCK 5: Actions */}
      <div className="flex gap-3 relative z-10">
        <button
          type="button"
          onClick={handleDownloadPDF}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-ui-accent px-4 py-3 text-xs font-bold text-white transition-all hover:bg-[#155d7a] hover:shadow-[0_4px_12px_rgba(18,78,102,0.3)] active:scale-[0.98]"
        >
          <Download className="h-4 w-4" />
          Download PDF
        </button>
        <button
          type="button"
          onClick={() => setActivePanel('compare')}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-orange-500 bg-transparent px-4 py-3 text-xs font-bold text-orange-400 transition-all hover:bg-orange-500/10 active:scale-[0.98]"
        >
          <GitCompareArrows className="h-4 w-4" />
          Compare
        </button>
      </div>
    </GlassPanel>
  )

  if (!mobile) return <DesktopWrapper>{contentPanel}</DesktopWrapper>
  return <MobileWrapper open={open} setOpen={setOpen}>{contentPanel}</MobileWrapper>
}

// Helpers — same width/height as Controls panel (`dashboardPanelLayout`)
function DesktopWrapper({ children }: { children: React.ReactNode }) {
  const clearLocationSession = useDashboardStore((s) => s.clearLocationSession)

  return (
    <aside
      className={`absolute right-4 ${SIDE_PANEL_TOP} z-20 flex ${SIDE_PANEL_HEIGHT} ${SIDE_PANEL_WIDTH} flex-col overflow-hidden rounded-3xl border border-ui-border/50 shadow-[0_16px_48px_var(--shadow)]`}
    >
      <div className="relative min-h-0 flex-1 overflow-hidden rounded-3xl">
        <button
          type="button"
          onClick={clearLocationSession}
          className="absolute right-1 top-1 z-30 flex h-8 w-8 items-center justify-center rounded-full border border-white/15 bg-black/45 text-ui-muted shadow-lg backdrop-blur-md transition hover:border-white/25 hover:bg-white/10 hover:text-ui-text"
          aria-label="Clear location and pick again"
        >
          <X className="h-4 w-4" />
        </button>
        <div className="h-full overflow-y-auto overflow-x-hidden scrollbar-hide pb-4 pr-1 pt-1">
          <motion.div
            initial={{ x: 40, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
          >
            {children}
          </motion.div>
        </div>
      </div>
    </aside>
  )
}

function MobileWrapper({ open, setOpen, children }: { open: boolean; setOpen: (v: boolean) => void; children: React.ReactNode }) {
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="glass absolute bottom-4 right-4 z-30 flex items-center gap-1.5 rounded-full px-4 py-2 text-sm text-ui-text shadow-lg"
      >
        <Sparkles className="h-3.5 w-3.5 text-ui-accent" />
        Insights
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ y: 30, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 20, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            className="absolute inset-x-2 bottom-2 z-40 max-h-[85vh] overflow-y-auto rounded-3xl"
          >
            {children}
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-xl bg-ui-surface-hover py-3 text-xs font-semibold text-ui-text"
            >
              <X className="h-4 w-4" />
              Close
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
