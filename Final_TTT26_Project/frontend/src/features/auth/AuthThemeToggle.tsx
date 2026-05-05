import { Map, Satellite, Sun } from 'lucide-react'
import { MAP_STYLE_LABELS, type MapStyleId } from '../../constants/mapStyles'
import { useDashboardStore } from '../../store/dashboardStore'
import { mapStyleToUiTheme } from '../../theme/uiTheme'
import { cn } from '../../lib/utils'

const MODES: { id: MapStyleId; icon: typeof Map; short: string }[] = [
  { id: 'street', icon: Map, short: 'Dark' },
  { id: 'normal', icon: Sun, short: 'Light' },
  { id: 'satellite', icon: Satellite, short: 'Sat' },
]

/** Legacy compact control — mirrors basemap + global `uiTheme` via `setUiTheme`. */
export function AuthThemeToggle() {
  const mapStyle = useDashboardStore((s) => s.mapStyle)
  const setUiTheme = useDashboardStore((s) => s.setUiTheme)

  return (
    <div className="pointer-events-auto flex flex-col items-end gap-1" role="group" aria-label="Map theme">
      <span className="hidden text-[10px] font-medium uppercase tracking-wide text-ui-muted sm:block">Theme</span>
      <div className="flex rounded-2xl border border-ui-border bg-ui-glass p-1 shadow-lg backdrop-blur-xl">
        {MODES.map(({ id, icon: Icon, short }) => {
          const active = mapStyle === id
          return (
            <button
              key={id}
              type="button"
              onClick={() => setUiTheme(mapStyleToUiTheme(id))}
              title={MAP_STYLE_LABELS[id]}
              aria-pressed={active}
              className={cn(
                'flex items-center gap-1.5 rounded-xl px-2.5 py-2 text-xs font-medium transition',
                active
                  ? 'bg-ui-accent/20 text-ui-accent ring-1 ring-ui-accent/30'
                  : 'text-ui-muted hover:bg-ui-hover hover:text-ui-text',
              )}
            >
              <Icon className="h-3.5 w-3.5 shrink-0 opacity-90" aria-hidden />
              <span className="hidden sm:inline">{MAP_STYLE_LABELS[id]}</span>
              <span className="sm:hidden">{short}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
