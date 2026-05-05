import { motion } from 'framer-motion'
import {
  Sparkles,
  Bookmark,
  Clock,
  SlidersHorizontal,
  GitCompareArrows,
  History,
  Settings,
} from 'lucide-react'
import { memo, useRef } from 'react'
import type { ComponentType } from 'react'
import { useDashboardStore, type SidebarPanelKey } from '../../store/dashboardStore'

type ToolKey = Exclude<SidebarPanelKey, null>
type ToolDef = { key: ToolKey; label: string; icon: ComponentType<{ className?: string }> }

// ── Groups ────────────────────────────────────────────────────────────────
const GROUP_TOP: ToolDef[] = [
  { key: 'askai',   label: 'Ask AI',   icon: Sparkles  },
  { key: 'saved',   label: 'Saved',    icon: Bookmark  },
  { key: 'recents', label: 'Recents',  icon: Clock     },
]

const GROUP_MID: ToolDef[] = [
  { key: 'controls', label: 'Controls', icon: SlidersHorizontal },
]

const GROUP_BOT: ToolDef[] = [
  { key: 'compare',  label: 'Compare',  icon: GitCompareArrows },
  { key: 'history',  label: 'History',  icon: History          },
  { key: 'settings', label: 'Settings', icon: Settings         },
]

// ── Icon button ───────────────────────────────────────────────────────────
function DockIconButton({
  def,
  active,
  onClick,
}: {
  def: ToolDef
  active: boolean
  onClick: (anchorY: number) => void
}) {
  const Icon = def.icon
  const btnRef = useRef<HTMLButtonElement>(null)

  const handleClick = () => {
    if (btnRef.current) {
      const rect = btnRef.current.getBoundingClientRect()
      // Centre of the button in viewport coords
      onClick(rect.top + rect.height / 2)
    } else {
      onClick(0)
    }
  }

  return (
    <div className="group relative flex justify-center">
      <motion.button
        ref={btnRef}
        type="button"
        whileHover={{ scale: 1.12 }}
        whileTap={{ scale: 0.92 }}
        aria-label={def.label}
        aria-pressed={active}
        onClick={handleClick}
        className={`relative flex h-11 w-11 shrink-0 items-center justify-center rounded-full transition duration-200 ${
          active
            ? 'bg-ui-accent/20 text-ui-accent ring-1 ring-ui-accent/40'
            : 'text-ui-muted hover:bg-white/10 hover:text-ui-text'
        }`}
      >
        {active && (
          <span
            className="pointer-events-none absolute inset-0 rounded-full bg-gradient-to-b from-ui-accent/25 to-transparent opacity-90"
            aria-hidden
          />
        )}
        <Icon className="relative h-[18px] w-[18px]" />
      </motion.button>

      {/* Tooltip */}
      <span className="header-map-pill pointer-events-none absolute left-full top-1/2 z-50 ml-3 hidden -translate-y-1/2 whitespace-nowrap rounded-lg px-2.5 py-1.5 text-[11px] font-medium text-ui-text opacity-0 shadow-xl backdrop-blur-md transition-opacity duration-150 group-hover:opacity-100 md:block">
        {def.label}
      </span>
    </div>
  )
}

const Divider = () => (
  <div
    className="h-px w-8 bg-gradient-to-r from-transparent via-ui-border to-transparent"
    aria-hidden
  />
)

// ── Desktop pill dock ─────────────────────────────────────────────────────
export const ToolDock = memo(function ToolDock({ mobile = false }: { mobile?: boolean }) {
  const activePanel    = useDashboardStore((s) => s.activePanel)
  const setActivePanel = useDashboardStore((s) => s.setActivePanel)
  const setPanelAnchorY = useDashboardStore((s) => s.setPanelAnchorY)

  // Controls panel never anchors to the icon — it always floats at the top
  const ANCHOR_EXEMPT: ToolKey[] = ['controls']

  const onSelect = (key: ToolKey, anchorY: number) => {
    if (!ANCHOR_EXEMPT.includes(key)) {
      setPanelAnchorY(anchorY)
    }
    setActivePanel(key)
  }

  // Mobile: horizontal scrollable bar at bottom
  if (mobile) {
    const all = [...GROUP_TOP, ...GROUP_MID, ...GROUP_BOT]
    return (
      <nav
        className="fixed bottom-3 left-3 right-3 z-30 flex items-center gap-2 overflow-x-auto rounded-2xl border border-ui-border bg-ui-glass py-2 pl-3 pr-2 shadow-lg backdrop-blur-xl scrollbar-hide"
        aria-label="Geo tools"
      >
        {all.map((def) => (
          <DockIconButton
            key={def.key}
            def={def}
            active={activePanel === def.key}
            onClick={(y) => onSelect(def.key, y)}
          />
        ))}
      </nav>
    )
  }

  // Desktop: floating vertical pill
  return (
    <nav
      className="surface-dock fixed left-4 top-1/2 z-30 flex w-14 min-w-[56px] -translate-y-1/2 flex-col items-center gap-3 rounded-full py-4"
      aria-label="GeoSpatial tool dock"
    >
      {GROUP_TOP.map((def) => (
        <DockIconButton
          key={def.key}
          def={def}
          active={activePanel === def.key}
          onClick={(y) => onSelect(def.key, y)}
        />
      ))}
      <Divider />
      {GROUP_MID.map((def) => (
        <DockIconButton
          key={def.key}
          def={def}
          active={activePanel === def.key}
          onClick={(y) => onSelect(def.key, y)}
        />
      ))}
      <Divider />
      {GROUP_BOT.map((def) => (
        <DockIconButton
          key={def.key}
          def={def}
          active={activePanel === def.key}
          onClick={(y) => onSelect(def.key, y)}
        />
      ))}
    </nav>
  )
})
