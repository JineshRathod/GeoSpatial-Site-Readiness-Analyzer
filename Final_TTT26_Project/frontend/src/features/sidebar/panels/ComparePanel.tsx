import { GitCompareArrows, Loader2, MapPin, X } from 'lucide-react'
import { memo, useState, useEffect } from 'react'
import { getScore } from '../../../services/api'
import type { ScoreResponse } from '../../../types/geo'
import { useDashboardStore } from '../../../store/dashboardStore'
import { useToast } from '../../../components/ui/Toast'

export const ComparePanel = memo(function ComparePanel() {
  const selectedCoordinates     = useDashboardStore((s) => s.selectedCoordinates)
  const selectedLocationLabel   = useDashboardStore((s) => s.selectedLocationLabel)
  const compareZoneBCoordinates = useDashboardStore((s) => s.compareZoneBCoordinates)
  const compareZoneBLabel       = useDashboardStore((s) => s.compareZoneBLabel)
  const clearCompareZoneB       = useDashboardStore((s) => s.clearCompareZoneB)
  const setCompareScoreB        = useDashboardStore((s) => s.setCompareScoreB)
  const { toast } = useToast()
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<{ zoneA: ScoreResponse, zoneB: ScoreResponse } | null>(null)

  useEffect(() => {
    setResult(null)
    setCompareScoreB(null)
  }, [selectedCoordinates, compareZoneBCoordinates])

  const handleRunComparison = async () => {
    if (!selectedCoordinates) {
      toast('Click the map to select Zone A first')
      return
    }
    if (!compareZoneBCoordinates) {
      toast('With this panel open, click the map again to drop the purple pin for Zone B')
      return
    }
    setLoading(true)
    try {
      const st = useDashboardStore.getState()
      const radiusM = st.analysisTools.radius * 1000
      const [resA, resB] = await Promise.all([
        getScore(selectedCoordinates, st.activeCategory, radiusM, st.weights),
        getScore(compareZoneBCoordinates, st.activeCategory, radiusM, st.weights)
      ])
      setResult({ zoneA: resA, zoneB: resB })
      st.setCompareScoreB(resB)
      toast('✓ Comparison complete!')
    } catch (e) {
      toast('Error running comparison.')
    } finally {
      setLoading(false)
    }
  }

  const canCompare = !!(selectedCoordinates && compareZoneBCoordinates)

  return (
    <div className="space-y-3">
      <p className="text-xs text-ui-muted">
        Zone A is your main map pin (cyan). With this panel open, click the map again to set Zone B (purple pin).
      </p>

      <div className="grid gap-2">
        {/* Zone A */}
        <div className="rounded-xl border border-ui-border bg-ui-glass/50 p-3">
          <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-ui-muted">Zone A</p>
          {selectedCoordinates ? (
            <div className="flex items-start gap-2">
              <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ui-accent" />
              <div className="min-w-0">
                <p className="truncate text-xs font-medium text-ui-text">{selectedLocationLabel}</p>
                <p className="text-[10px] tabular-nums text-ui-muted">
                  {selectedCoordinates.lat.toFixed(4)}, {selectedCoordinates.lng.toFixed(4)}
                </p>
              </div>
            </div>
          ) : (
            <p className="text-xs text-ui-muted">Click the map to set Zone A</p>
          )}
        </div>

        <div className="flex items-center justify-center py-0.5 text-ui-muted">
          <GitCompareArrows className="h-4 w-4" />
        </div>

        {/* Zone B */}
        <div className="rounded-xl border border-dashed border-ui-border bg-ui-glass/30 p-3">
          <div className="mb-1 flex items-center justify-between gap-2">
            <p className="text-[10px] font-medium uppercase tracking-wide text-ui-muted">Zone B</p>
            {compareZoneBCoordinates && (
              <button
                type="button"
                onClick={() => clearCompareZoneB()}
                className="flex h-6 w-6 items-center justify-center rounded-full text-ui-muted transition hover:bg-ui-surface-hover hover:text-ui-text"
                aria-label="Clear Zone B"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
          {compareZoneBCoordinates ? (
            <div className="flex items-start gap-2">
              <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0 text-violet-400" />
              <div className="min-w-0">
                <p className="truncate text-xs font-medium text-ui-text">{compareZoneBLabel}</p>
                <p className="text-[10px] tabular-nums text-ui-muted">
                  {compareZoneBCoordinates.lat.toFixed(4)}, {compareZoneBCoordinates.lng.toFixed(4)}
                </p>
              </div>
            </div>
          ) : (
            <p className="text-xs text-ui-muted">Click the map (purple pin) while this panel is open</p>
          )}
        </div>
      </div>

      <button
        type="button"
        onClick={handleRunComparison}
        disabled={loading || !canCompare}
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-orange-500/20 py-2.5 text-xs font-semibold text-orange-400 transition hover:bg-orange-500/30 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? (
          <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Running Analysis…</>
        ) : (
          <><GitCompareArrows className="h-3.5 w-3.5" /> Run Comparison</>
        )}
      </button>

      {result && (
        <div className="mt-4 space-y-4 border-t border-ui-border/50 pt-5">
          <p className="text-[10px] uppercase font-bold text-ui-muted text-center tracking-widest">Comparison Results</p>
          
          <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 text-center bg-ui-glass/30 rounded-xl p-3 border border-ui-border/30">
            <div>
              <p className="text-[10px] text-ui-accent mb-0.5 uppercase">Zone A</p>
              <div className="text-ui-text font-bold text-xl">{result.zoneA.totalScore.toFixed(0)}</div>
            </div>
            <div className="text-[9px] text-ui-muted uppercase tracking-widest">Overall<br/>Match</div>
            <div>
              <p className="text-[10px] text-violet-400 mb-0.5 uppercase">Zone B</p>
              <div className="text-ui-text font-bold text-xl">{result.zoneB.totalScore.toFixed(0)}</div>
            </div>
          </div>
          
          <div className="space-y-4 rounded-xl border border-ui-border/30 bg-ui-glass/30 p-4">
            {[
              { label: 'Population', key: 'populationScore' as const },
              { label: 'Accessibility', key: 'accessibilityScore' as const },
              { label: 'Competition', key: 'competitionScore' as const },
              { label: 'Risk factor', key: 'riskScore' as const },
            ].map((m) => (
              <div key={m.label} className="text-xs">
                <p className="text-[10px] text-ui-muted text-center mb-1.5 uppercase tracking-wide">{m.label}</p>
                <div className="flex items-center gap-2">
                  <div className="w-7 text-right tabular-nums text-ui-text font-bold">{result.zoneA[m.key].toFixed(0)}</div>
                  <div className="flex-1 flex gap-[2px] h-2.5">
                    <div className="flex-1 bg-ui-surface-hover/50 rounded-l-full flex justify-end overflow-hidden">
                       <div className="h-full bg-ui-accent" style={{ width: `${result.zoneA[m.key]}%` }} />
                    </div>
                    <div className="flex-1 bg-ui-surface-hover/50 rounded-r-full overflow-hidden">
                       <div className="h-full bg-violet-400" style={{ width: `${result.zoneB[m.key]}%` }} />
                    </div>
                  </div>
                  <div className="w-7 text-left tabular-nums text-ui-text font-bold">{result.zoneB[m.key].toFixed(0)}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
})
