import { AnimatePresence, motion } from 'framer-motion'
import { X } from 'lucide-react'
import { lazy, memo, Suspense, useMemo } from 'react'
import { sidePanelAsideClasses } from '../../constants/dashboardPanelLayout'
import { useDashboardStore } from '../../store/dashboardStore'
import { ToolDock } from './ToolDock'
import { ControlsPanel } from './panels/ControlsPanel'

// ── Lazy-loaded panels ────────────────────────────────────────────────────
const AskAIPanel        = lazy(() => import('./panels/AskAIPanel').then((m) => ({ default: m.AskAIPanel })))
const SavedPanel        = lazy(() => import('./panels/SavedPanel').then((m) => ({ default: m.SavedPanel })))
const RecentsPanel      = lazy(() => import('./panels/RecentsPanel').then((m) => ({ default: m.RecentsPanel })))
const ComparePanel      = lazy(() => import('./panels/ComparePanel').then((m) => ({ default: m.ComparePanel })))
const HistoryPanel      = lazy(() => import('./panels/HistoryPanel').then((m) => ({ default: m.HistoryPanel })))
const SettingsDockPanel = lazy(() => import('./panels/SettingsDockPanel').then((m) => ({ default: m.SettingsDockPanel })))

const panelByKey = {
  askai:    AskAIPanel,
  saved:    SavedPanel,
  recents:  RecentsPanel,
  compare:  ComparePanel,
  history:  HistoryPanel,
  settings: SettingsDockPanel,
} as const

const PANEL_TITLES: Record<string, string> = {
  askai:    'Ask AI',
  saved:    'Saved Sites',
  recents:  'Recents',
  controls: 'Controls',
  compare:  'Compare Zones',
  history:  'History',
  settings: 'Quick Settings',
}

// Panels that should NOT anchor to the icon click position — always float at top
const ANCHOR_EXEMPT = new Set(['controls'])

// Panel max-height in px (must match CSS below)
const PANEL_MAX_H = 560
// Vertical padding from viewport edges
const EDGE_PAD = 16
/** Never anchor floating panels under the header row */
const PANEL_MIN_TOP_PX = 108

function PanelSkeleton() {
  return (
    <div className="space-y-3 p-1">
      <div className="h-4 w-24 animate-pulse rounded bg-ui-border/40" />
      <div className="h-20 animate-pulse rounded-xl bg-ui-border/25" />
      <div className="h-20 animate-pulse rounded-xl bg-ui-border/25" />
    </div>
  )
}

export const SidebarContainer = memo(function SidebarContainer({ mobile = false }: { mobile?: boolean }) {
  const activePanel    = useDashboardStore((state) => state.activePanel)
  const setActivePanel = useDashboardStore((state) => state.setActivePanel)
  const panelAnchorY   = useDashboardStore((state) => state.panelAnchorY)
  const insightsDockHidden = useDashboardStore((state) => state.insightsDockHidden)

  const Panel =
    activePanel && activePanel !== 'controls' ? panelByKey[activePanel] : null

  /**
   * Compute the panel top position:
   * - Controls panel → fixed top-4 (16px), never anchored
   * - All others → try to centre on the icon, clamped within viewport
   */
  const panelTop = useMemo(() => {
    if (!activePanel || ANCHOR_EXEMPT.has(activePanel)) return EDGE_PAD
    const vh = typeof window !== 'undefined' ? window.innerHeight : 720
    const halfPanel = PANEL_MAX_H / 2
    // Start centred on the icon, then clamp
    const ideal = panelAnchorY - halfPanel
    return Math.max(PANEL_MIN_TOP_PX, Math.min(ideal, vh - PANEL_MAX_H - EDGE_PAD))
  }, [activePanel, panelAnchorY])

  /* ─── Mobile bottom sheet ──────────────────────────────────────── */
  if (mobile) {
    return (
      <>
        <ToolDock mobile />
        <AnimatePresence initial={false}>
          {Panel && (
            <motion.div
              key={activePanel}
              initial={{ y: 32, opacity: 0, scale: 0.96 }}
              animate={{ y: 0, opacity: 1, scale: 1 }}
              exit={{ y: 24, opacity: 0, scale: 0.98 }}
              transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
              className="surface-panel fixed inset-x-3 bottom-[5.25rem] z-30 max-h-[min(72vh,560px)] overflow-y-auto rounded-2xl border p-4 text-ui-text"
            >
              {/* Mobile header */}
              <div className="mb-3 flex items-center justify-between">
                <p className="text-sm font-semibold text-ui-text">
                  {activePanel ? PANEL_TITLES[activePanel] : ''}
                </p>
                <button
                  type="button"
                  onClick={() => setActivePanel(activePanel)}
                  className="flex h-7 w-7 items-center justify-center rounded-full bg-ui-hover text-ui-muted transition hover:text-ui-text"
                  aria-label="Close panel"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
              <Suspense fallback={<PanelSkeleton />}>
                <Panel />
              </Suspense>
            </motion.div>
          )}
        </AnimatePresence>
      </>
    )
  }

  /* ─── Desktop: panel anchored to the clicked icon ──────────────── */
  const controlsCompact = insightsDockHidden && activePanel === 'controls'
  const compareFullLayout = activePanel === 'compare'

  return (
    <>
      {!insightsDockHidden && <ToolDock />}

      {/* ── Controls panel: full-height with dock, or compact height aligned with insights ── */}
      <AnimatePresence>
        {activePanel === 'controls' && (
          <motion.aside
            key="controls-panel"
            initial={{ x: -320, opacity: 0 }}
            animate={{ x: 0,    opacity: 1 }}
            exit={{    x: -320, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 340, damping: 30, mass: 0.9 }}
            className={[
              'surface-panel fixed z-[38] flex flex-col overflow-hidden rounded-2xl border border-white/8 text-ui-text shadow-[0_12px_48px_rgba(0,0,0,0.45)] backdrop-blur-2xl',
              sidePanelAsideClasses,
              controlsCompact ? 'left-4' : 'left-20',
            ].join(' ')}
          >
            {/* ── Sticky header ── */}
            <div
              className={
                controlsCompact
                  ? 'shrink-0 border-b border-white/8 px-4 py-3'
                  : 'shrink-0 border-b border-white/8 px-5 py-4'
              }
              style={{ borderBottom: '1px solid rgba(255,255,255,0.07)' }}
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-bold tracking-tight text-ui-text">Controls</p>
                  <p className="mt-0.5 text-[10px] text-ui-muted">Settings &amp; layers</p>
                </div>
                <button
                  type="button"
                  onClick={() => setActivePanel('controls')}
                  className="flex h-7 w-7 items-center justify-center rounded-full bg-white/5 text-ui-muted transition hover:bg-white/10 hover:text-ui-text"
                  aria-label="Close controls panel"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>

            {/* ── Scrollable content ── */}
            <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 scrollbar-hide">
              <ControlsPanel />
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      {/* ── All other panels: anchored to dock icon ──────────── */}
      <AnimatePresence mode="wait" initial={false}>
        {Panel && activePanel !== 'controls' && (!insightsDockHidden || activePanel === 'compare') && (
          <motion.aside
            key={activePanel}
            initial={{ x: -18, opacity: 0, scale: 0.96 }}
            animate={{ x: 0,   opacity: 1, scale: 1    }}
            exit={{    x: -14, opacity: 0, scale: 0.97  }}
            transition={{
              type: 'spring',
              stiffness: 340,
              damping: 28,
              mass: 0.85,
            }}
            style={
              compareFullLayout
                ? undefined
                : {
                    top: panelTop,
                    transformOrigin: 'left center',
                  }
            }
            className={
              compareFullLayout
                ? [
                    'surface-panel fixed z-[38] flex flex-col overflow-hidden rounded-2xl border border-white/8 p-4 text-ui-text shadow-[0_12px_48px_rgba(0,0,0,0.45)] backdrop-blur-2xl',
                    sidePanelAsideClasses,
                    insightsDockHidden ? 'left-4' : 'left-20',
                  ].join(' ')
                : 'surface-panel fixed left-20 z-[38] w-[300px] max-h-[560px] overflow-y-auto rounded-2xl border p-4 text-ui-text scrollbar-hide shadow-[0_12px_48px_rgba(0,0,0,0.45)]'
            }
          >
            {/* Desktop header */}
            <div className={`flex shrink-0 items-center justify-between ${compareFullLayout ? 'mb-3' : 'mb-4'}`}>
              <p className="text-sm font-semibold text-ui-text">
                {activePanel ? PANEL_TITLES[activePanel] : ''}
              </p>
              <button
                type="button"
                onClick={() => setActivePanel(activePanel)}
                className="flex h-7 w-7 items-center justify-center rounded-full bg-ui-hover text-ui-muted transition hover:text-ui-text"
                aria-label="Close panel"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
            {compareFullLayout ? (
              <div className="min-h-0 flex-1 overflow-y-auto pr-0.5 scrollbar-hide">
                <Suspense fallback={<PanelSkeleton />}>
                  <Panel />
                </Suspense>
              </div>
            ) : (
              <Suspense fallback={<PanelSkeleton />}>
                <Panel />
              </Suspense>
            )}
          </motion.aside>
        )}
      </AnimatePresence>
    </>
  )
})
