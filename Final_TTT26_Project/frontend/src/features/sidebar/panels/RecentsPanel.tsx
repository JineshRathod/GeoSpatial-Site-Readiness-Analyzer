import { MapPin } from 'lucide-react'
import { useDashboardStore } from '../../../store/dashboardStore'

const FALLBACK = [
  { id: 'r1', name: 'Andheri East', coordinates: { lat: 19.1136, lng: 72.8697 } },
  { id: 'r2', name: 'Thane West', coordinates: { lat: 19.1820, lng: 72.9781 } },
]

export function RecentsPanel() {
  const history = useDashboardStore((s) => s.history)
  const loadHistoryLocation = useDashboardStore((s) => s.loadHistoryLocation)
  const items = history.length ? history : FALLBACK

  return (
    <div>
      <p className="mb-2 text-[10px] text-ui-muted">{items.length} recent location{items.length !== 1 ? 's' : ''}</p>

      <ul className="space-y-1.5">
        {items.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              onClick={() => loadHistoryLocation(item)}
              className="flex w-full items-center gap-3 rounded-xl border border-ui-border bg-ui-glass/50 px-3 py-2.5 text-left transition hover:bg-ui-hover"
            >
              <MapPin className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
              <div className="min-w-0">
                <p className="truncate text-xs font-medium text-ui-text">{item.name}</p>
                <p className="text-[10px] text-ui-muted">{item.coordinates.lat.toFixed(4)}, {item.coordinates.lng.toFixed(4)}</p>
              </div>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
