import { memo } from 'react'
import { useDashboardStore } from '../../../store/dashboardStore'

const scoreColor = (score: number) =>
  score >= 70 ? 'bg-emerald-400' : score >= 40 ? 'bg-amber-400' : 'bg-rose-400'

export const HistoryPanel = memo(function HistoryPanel() {
  const history             = useDashboardStore((state) => state.history)
  const loadHistoryLocation = useDashboardStore((state) => state.loadHistoryLocation)

  if (history.length === 0) {
    return (
      <p className="py-6 text-center text-xs text-ui-muted">
        No analysis history yet. Analyze a location to see it here.
      </p>
    )
  }

  return (
    <div className="space-y-2">
      <p className="text-[10px] text-ui-muted">Previously analyzed locations.</p>
      <div className="max-h-72 space-y-1.5 overflow-y-auto scrollbar-hide pr-0.5">
        {history.map((item) => {
          const score = 0 // Actually we don't have score in item anymore, we can placeholder to 0 until API updates it
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => loadHistoryLocation(item)}
              className="w-full rounded-lg border border-ui-border bg-ui-glass/40 px-3 py-2 text-left text-xs text-ui-text transition hover:bg-ui-hover active:scale-[0.98]"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate font-medium">{item.name}</span>
                <span className="shrink-0 rounded-full border border-ui-border bg-ui-glass px-2 py-0.5 text-[11px] tabular-nums text-ui-muted">
                  {score}/100
                </span>
              </div>
              <div className="mt-1.5 flex items-center gap-2">
                <span className={`inline-block h-2 w-2 rounded-full ${scoreColor(score)}`} />
                <span className="text-[10px] tabular-nums text-ui-muted">
                  {item.coordinates.lat.toFixed(4)}, {item.coordinates.lng.toFixed(4)}
                </span>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
})
