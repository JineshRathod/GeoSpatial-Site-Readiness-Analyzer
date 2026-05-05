import { memo, useState } from 'react'
import { MapPin, Navigation } from 'lucide-react'
import { useDashboardStore } from '../../../store/dashboardStore'

// ── Reusable primitives ────────────────────────────────────────────────────

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-2.5 text-[10px] font-semibold uppercase tracking-widest text-ui-muted">
      {children}
    </p>
  )
}

function Divider() {
  return <div className="h-px bg-gradient-to-r from-transparent via-ui-border to-transparent" />
}

function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label: string
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full transition-colors duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-ui-accent/50 ${
        checked ? 'bg-ui-accent' : 'bg-ui-border'
      }`}
      aria-label={label}
    >
      <span
        className={`inline-block h-3.5 w-3.5 translate-x-0.5 rounded-full bg-white shadow-sm transition-transform duration-200 ${
          checked ? 'translate-x-[18px]' : ''
        }`}
      />
    </button>
  )
}

function SliderRow({
  label,
  value,
  min,
  max,
  unit = '',
  onChange,
}: {
  label: string
  value: number
  min: number
  max: number
  unit?: string
  onChange: (v: number) => void
}) {
  return (
    <div>
      <div className="mb-1.5 flex justify-between">
        <span className="text-xs text-ui-text">{label}</span>
        <span className="text-xs font-semibold text-ui-accent">
          {value}{unit}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="geo-slider"
        aria-label={label}
      />
    </div>
  )
}

// ── Layer config ───────────────────────────────────────────────────────────

const LAYER_DEFS: { key: string; label: string; color: string }[] = [
  { key: 'Density',     label: 'Population Heatmap', color: 'bg-blue-400' },
  { key: 'Competitors', label: 'Competitors',         color: 'bg-rose-400' },
  { key: 'Roads',       label: 'Transport Network',   color: 'bg-amber-400' },
  { key: 'Flood',       label: 'Risk Zones',          color: 'bg-purple-400' },
]

const WEIGHT_CONFIG: {
  key: 'population' | 'accessibility' | 'competition' | 'risk'
  label: string
}[] = [
  { key: 'population',    label: 'Population'    },
  { key: 'accessibility', label: 'Accessibility' },
  { key: 'competition',   label: 'Competition'   },
  { key: 'risk',          label: 'Risk'          },
]

// ── Main panel ─────────────────────────────────────────────────────────────

export const ControlsPanel = memo(function ControlsPanel() {
  const selectedCoordinates   = useDashboardStore((s) => s.selectedCoordinates)
  const selectedLocationLabel = useDashboardStore((s) => s.selectedLocationLabel)
  const analysisTools         = useDashboardStore((s) => s.analysisTools)
  const setAnalysisTool       = useDashboardStore((s) => s.setAnalysisTool)
  const geoFilters            = useDashboardStore((s) => s.geoFilters)
  const setGeoFilter          = useDashboardStore((s) => s.setGeoFilter)
  const weights               = useDashboardStore((s) => s.weights)
  const setWeight             = useDashboardStore((s) => s.setWeight)
  const selectedLayers        = useDashboardStore((s) => s.selectedLayers)
  const toggleSelectedLayer   = useDashboardStore((s) => s.toggleSelectedLayer)

  const [weightsExpanded, setWeightsExpanded] = useState(true)
  const [layersExpanded,  setLayersExpanded]  = useState(true)

  return (
    <div className="space-y-5">

      {/* ── SECTION 1: LOCATION ─────────────────────────────── */}
      <div>
        <SectionLabel>Location</SectionLabel>
        {selectedCoordinates ? (
          <div className="rounded-xl border border-ui-border bg-ui-glass/50 p-3">
            <div className="flex items-start gap-2.5">
              <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-ui-accent/15">
                <MapPin className="h-3 w-3 text-ui-accent" />
              </div>
              <div className="min-w-0">
                <p className="truncate text-xs font-semibold text-ui-text">
                  {selectedLocationLabel}
                </p>
                <p className="mt-0.5 text-[10px] tabular-nums text-ui-muted">
                  {selectedCoordinates.lat.toFixed(5)}, {selectedCoordinates.lng.toFixed(5)}
                </p>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-2.5 rounded-xl border border-dashed border-ui-border bg-ui-glass/20 p-3">
            <Navigation className="h-3.5 w-3.5 shrink-0 text-ui-muted" />
            <p className="text-xs text-ui-muted">Click the map to select a location</p>
          </div>
        )}

        {/* Pick on Map toggle */}
        <div className="mt-2.5 flex items-center justify-between rounded-xl border border-ui-border bg-ui-glass/40 px-3 py-2">
          <span className="text-xs text-ui-text">Pick on Map</span>
          <Toggle
            checked={analysisTools.locationPicker}
            onChange={(v) => setAnalysisTool('locationPicker', v)}
            label="Toggle location picker"
          />
        </div>
      </div>

      <Divider />

      {/* ── SECTION 2: ANALYSIS TOOLS ───────────────────────── */}
      <div>
        <SectionLabel>Analysis Tools</SectionLabel>
        <div className="space-y-2.5">
          {/* Area Crop */}
          <div className="flex items-center justify-between rounded-xl border border-ui-border bg-ui-glass/40 px-3 py-2">
            <div>
              <p className="text-xs font-medium text-ui-text">Area Crop</p>
              <p className="text-[10px] text-ui-muted">Restrict to drawn polygon</p>
            </div>
            <Toggle
              checked={analysisTools.areaCrop}
              onChange={(v) => setAnalysisTool('areaCrop', v)}
              label="Toggle area crop"
            />
          </div>

          <div className="rounded-xl border border-ui-border bg-ui-glass/40 px-3 py-2.5">
            <SliderRow
              label="Analysis radius"
              value={analysisTools.radius}
              min={1}
              max={20}
              unit=" km"
              onChange={(v) => {
                setAnalysisTool('radius', v)
                setGeoFilter('distanceThreshold', v)
              }}
            />
            <p className="mt-1.5 text-[10px] leading-snug text-ui-muted">
              Used for the map ring, site analysis API, and nearby POI search.
            </p>
            <div className="mt-1 flex justify-between text-[10px] text-ui-muted">
              <span>1 km</span>
              <span>20 km</span>
            </div>
          </div>
        </div>
      </div>

      <Divider />

      {/* ── SECTION 3: FILTERS (strict mode only) ───────────── */}
      <div>
        <SectionLabel>Filters</SectionLabel>
        <div className="flex items-center justify-between rounded-xl border border-ui-border bg-ui-glass/40 px-3 py-2">
          <div>
            <p className="text-xs font-medium text-ui-text">Strict Mode</p>
            <p className="text-[10px] text-ui-muted">Exclude borderline candidates</p>
          </div>
          <Toggle
            checked={geoFilters.strictMode}
            onChange={(v) => setGeoFilter('strictMode', v)}
            label="Toggle strict mode"
          />
        </div>
      </div>

      <Divider />

      {/* ── SECTION 4: WEIGHTS ──────────────────────────────── */}
      <div>
        <button
          type="button"
          onClick={() => setWeightsExpanded((v) => !v)}
          className="mb-2.5 flex w-full items-center justify-between"
        >
          <SectionLabel>Scoring Weights</SectionLabel>
          <span className="text-[10px] text-ui-muted">{weightsExpanded ? '▲' : '▼'}</span>
        </button>
        {weightsExpanded && (
          <div className="space-y-3 rounded-xl border border-ui-border bg-ui-glass/40 px-3 py-3">
            {WEIGHT_CONFIG.map(({ key, label }) => (
              <SliderRow
                key={key}
                label={label}
                value={weights[key]}
                min={0}
                max={100}
                onChange={(v) => setWeight(key, v)}
              />
            ))}
          </div>
        )}
      </div>

      <Divider />

      {/* ── SECTION 5: LAYERS ───────────────────────────────── */}
      <div>
        <button
          type="button"
          onClick={() => setLayersExpanded((v) => !v)}
          className="mb-2.5 flex w-full items-center justify-between"
        >
          <SectionLabel>Map Layers</SectionLabel>
          <span className="text-[10px] text-ui-muted">{layersExpanded ? '▲' : '▼'}</span>
        </button>
        {layersExpanded && (
          <div className="space-y-1.5">
            {LAYER_DEFS.map(({ key, label, color }) => {
              const active = selectedLayers.includes(key)
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => toggleSelectedLayer(key)}
                  className={`flex w-full items-center gap-3 rounded-xl border px-3 py-2 text-left text-xs transition ${
                    active
                      ? 'border-ui-border bg-ui-glass/60 text-ui-text'
                      : 'border-transparent bg-ui-glass/20 text-ui-muted hover:bg-ui-glass/40 hover:text-ui-text'
                  }`}
                >
                  <span className={`h-2 w-2 rounded-full ${active ? color : 'bg-ui-border'} shrink-0`} />
                  {label}
                  <span className="ml-auto text-[10px] text-ui-muted">
                    {active ? 'ON' : 'OFF'}
                  </span>
                </button>
              )
            })}
          </div>
        )}
      </div>

    </div>
  )
})
