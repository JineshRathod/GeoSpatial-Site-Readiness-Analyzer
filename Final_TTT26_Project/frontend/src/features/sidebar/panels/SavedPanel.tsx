import { MapPin, Trash2 } from 'lucide-react'
import { useState } from 'react'

const INIT = [
  { id: 's1', name: 'Bandra Kurla Complex', coords: '19.0656° N, 72.8708° E', tag: 'Commercial' },
  { id: 's2', name: 'Kohinoor Square', coords: '19.0178° N, 72.8478° E', tag: 'Retail' },
  { id: 's3', name: 'Powai Tech Park', coords: '19.1197° N, 72.9066° E', tag: 'Tech' },
]

export function SavedPanel() {
  const [items, setItems] = useState(INIT)

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <p className="text-[10px] text-ui-muted">{items.length} saved site{items.length !== 1 ? 's' : ''}</p>
      </div>

      {items.length === 0 && (
        <p className="py-6 text-center text-xs text-ui-muted">No saved sites yet.</p>
      )}

      <ul className="space-y-2">
        {items.map((item) => (
          <li key={item.id} className="group flex items-start gap-3 rounded-xl border border-ui-border bg-ui-glass/60 p-2.5">
            <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ui-accent" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-semibold text-ui-text">{item.name}</p>
              <p className="mt-0.5 truncate text-[10px] text-ui-muted">{item.coords}</p>
              <span className="mt-1 inline-block rounded-full border border-ui-border px-2 py-0.5 text-[9px] font-medium text-ui-muted">{item.tag}</span>
            </div>
            <button type="button" onClick={() => setItems((s) => s.filter((x) => x.id !== item.id))}
              className="shrink-0 rounded-lg p-1 text-ui-muted opacity-0 transition hover:bg-red-500/15 hover:text-red-400 group-hover:opacity-100">
              <Trash2 className="h-3 w-3" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
