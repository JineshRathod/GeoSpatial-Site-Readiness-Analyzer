import { memo } from 'react'
import { Link } from 'react-router-dom'
import { MAP_STYLE_LABELS, type MapStyleId } from '../../../constants/mapStyles'
import { useDashboardStore } from '../../../store/dashboardStore'

const MAP_ORDER: MapStyleId[] = ['street', 'normal', 'satellite']

export const SettingsDockPanel = memo(function SettingsDockPanel() {
  const mapStyle = useDashboardStore((state) => state.mapStyle)
  const setMapStyle = useDashboardStore((state) => state.setMapStyle)
  const preferences = useDashboardStore((state) => state.preferences)
  const setPreferences = useDashboardStore((state) => state.setPreferences)

  return (
    <div className="space-y-4">
      <p className="text-[10px] text-ui-muted">Map style and unit preferences.</p>

      <div>
        <p className="mb-2 text-[10px] font-medium uppercase tracking-wide text-ui-muted">Basemap</p>
        <div className="flex flex-col gap-1">
          {MAP_ORDER.map((id) => (
            <button
              key={id}
              type="button"
              onClick={() => {
                setMapStyle(id)
                setPreferences({ mapDefaultView: id })
              }}
              className={`rounded-xl px-3 py-2 text-left text-xs transition ${
                mapStyle === id
                  ? 'bg-ui-accent/20 font-medium text-ui-accent'
                  : 'text-ui-text hover:bg-ui-hover'
              }`}
            >
              {MAP_STYLE_LABELS[id]}
            </button>
          ))}
        </div>
      </div>

      <div>
        <p className="mb-2 text-[10px] font-medium uppercase tracking-wide text-ui-muted">Units</p>
        <div className="flex gap-2">
          {(['km', 'mi'] as const).map((u) => (
            <button
              key={u}
              type="button"
              onClick={() => setPreferences({ units: u })}
              className={`flex-1 rounded-xl py-2 text-xs font-medium ${
                preferences.units === u
                  ? 'bg-ui-accent/20 text-ui-accent'
                  : 'bg-ui-glass/50 text-ui-muted hover:bg-ui-hover'
              }`}
            >
              {u === 'km' ? 'Kilometers' : 'Miles'}
            </button>
          ))}
        </div>
      </div>

      <Link
        to="/settings"
        className="block w-full rounded-xl border border-ui-border bg-ui-glass/50 py-2.5 text-center text-xs font-medium text-ui-text transition hover:bg-ui-hover"
      >
        Open full settings
      </Link>
    </div>
  )
})
