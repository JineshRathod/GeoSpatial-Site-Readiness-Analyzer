import { AnimatePresence, motion } from 'framer-motion'
import { ChevronDown, Layers } from 'lucide-react'
import { memo, useEffect, useRef, useState } from 'react'
import { MAP_STYLE_LABELS, type MapStyleId } from '../../constants/mapStyles'
import { useDashboardStore } from '../../store/dashboardStore'
import { useToast } from '../../components/ui/Toast'

const ORDER: MapStyleId[] = ['street', 'normal', 'satellite']

export const MapStyleSwitcher = memo(function MapStyleSwitcher() {
  const [open, setOpen] = useState(false)
  const mapStyle = useDashboardStore((state) => state.mapStyle)
  const setMapStyle = useDashboardStore((state) => state.setMapStyle)
  const { toast } = useToast()
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [open])

  return (
    <div
      ref={containerRef}
      className="pointer-events-auto absolute bottom-4 left-4 z-30 md:bottom-6 md:left-6 lg:left-[5.25rem]"
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="header-map-pill flex h-12 items-center gap-2 rounded-full px-4 text-xs font-semibold text-ui-text transition hover:bg-ui-hover"
      >
        <Layers className="h-4 w-4 text-ui-accent" />
        <span className="hidden sm:inline">{MAP_STYLE_LABELS[mapStyle]}</span>
        <ChevronDown className={`h-3.5 w-3.5 transition ${open ? 'rotate-180' : ''}`} />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 6, scale: 0.98 }}
            transition={{ duration: 0.2 }}
            className="header-map-pill absolute bottom-full left-0 mb-2 min-w-[11rem] rounded-2xl p-1 shadow-lg"
          >
            <p className="px-3 py-2 text-[10px] font-medium uppercase tracking-wide text-ui-muted">Map view</p>
            {ORDER.map((id) => (
              <button
                key={id}
                type="button"
                onClick={() => {
                  setMapStyle(id)
                  setOpen(false)
                  toast(`Map style: ${MAP_STYLE_LABELS[id]}`)
                }}
                className={`flex w-full rounded-xl px-3 py-2.5 text-left text-xs transition hover:bg-ui-hover ${
                  mapStyle === id ? 'bg-ui-accent/20 font-medium text-ui-accent' : 'text-ui-text'
                }`}
              >
                {MAP_STYLE_LABELS[id]}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
})
