import { AnimatePresence, motion } from 'framer-motion'
import { LocateFixed, Search, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useDashboardStore } from '../../store/dashboardStore'
import { useToast } from '../ui/Toast'
import { autocompleteLocation, geocodeLocation } from '../../services/api'

export function FloatingSearch() {
  const searchQuery    = useDashboardStore((s) => s.searchQuery)
  const setSearchQuery = useDashboardStore((s) => s.setSearchQuery)
  const setSelectedLocation = useDashboardStore((s) => s.setSelectedLocation)
  const activeSidebarPanel = useDashboardStore((s) => s.activePanel)
  const { toast } = useToast()

  const [focused, setFocused] = useState(false)
  const [locating, setLocating] = useState(false)
  const [suggestions, setSuggestions] = useState<any[]>([])
  const containerRef = useRef<HTMLDivElement>(null)

  const [debouncedQuery, setDebouncedQuery] = useState(searchQuery)
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(searchQuery), 300)
    return () => clearTimeout(t)
  }, [searchQuery])

  useEffect(() => {
    if (!debouncedQuery.trim()) {
      setSuggestions([])
      return
    }
    autocompleteLocation(debouncedQuery).then(res => {
      setSuggestions(res.slice(0, 5))
    })
  }, [debouncedQuery])

  const handleLocate = () => {
    if (!navigator.geolocation) {
      toast('Geolocation is not supported by your browser')
      return
    }
    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords
        setSearchQuery(`${latitude.toFixed(4)}, ${longitude.toFixed(4)}`)
        setLocating(false)
        toast('Current location detected')
      },
      (err) => {
        toast(`Location error: ${err.message}`)
        setLocating(false)
      },
      { timeout: 8000, enableHighAccuracy: true },
    )
  }

  // Determine left offset: shifts right when a sidebar panel is open (same as header)
  const PANEL_W = activeSidebarPanel ? 'calc(4.5rem + 300px + 1rem)' : '6rem'

  return (
    <div
      ref={containerRef}
      className="pointer-events-none absolute top-5 z-40 flex justify-center"
      style={{
        left: PANEL_W,
        right: '16rem', // leave space for header controls on the right
        transition: 'left 0.3s cubic-bezier(0.22,1,0.36,1)',
      }}
    >
      <motion.div
        className="pointer-events-auto relative w-full max-w-md"
        layout
      >
        {/* ── Main pill ─────────────────────────────────────────── */}
        <motion.div
          animate={{
            boxShadow: focused
              ? '0 0 0 2px rgba(18,78,102,0.45), 0 8px 32px rgba(0,0,0,0.35)'
              : '0 4px 20px rgba(0,0,0,0.28)',
          }}
          transition={{ duration: 0.2 }}
          className={[
            'glass flex h-10 items-center gap-2 rounded-full px-3.5 transition-colors duration-200',
            focused
              ? 'border-ui-accent/50 bg-[#212A31]/90'
              : 'border-ui-border/50 bg-ui-glass/80',
          ].join(' ')}
        >
          {/* Search icon */}
          <Search className="h-3.5 w-3.5 shrink-0 text-gray-500" />

          {/* Input */}
          <input
            value={searchQuery}
            onFocus={() => setFocused(true)}
            onBlur={() => setTimeout(() => setFocused(false), 150)}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="min-w-0 flex-1 bg-transparent text-xs font-medium text-black outline-none placeholder:text-gray-500"
            placeholder="Search location, coordinates, or area…"
          />

          {/* Clear */}
          <AnimatePresence>
            {searchQuery.length > 0 && (
              <motion.button
                initial={{ opacity: 0, scale: 0.7 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.7 }}
                transition={{ duration: 0.12 }}
                type="button"
                onClick={() => setSearchQuery('')}
                className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-ui-surface-hover text-gray-500 hover:text-black transition-colors"
              >
                <X className="h-3 w-3" />
              </motion.button>
            )}
          </AnimatePresence>

          {/* Divider */}
          <div className="h-4 w-px shrink-0 bg-ui-border/60" />

          {/* Current location */}
          <motion.button
            type="button"
            onClick={handleLocate}
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            title="Use my current location"
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full transition-colors hover:bg-ui-surface-hover"
          >
            <motion.div
              animate={locating ? { rotate: 360 } : { rotate: 0 }}
              transition={locating ? { repeat: Infinity, duration: 1, ease: 'linear' } : {}}
            >
              <LocateFixed
                className={`h-4 w-4 transition-colors ${locating ? 'text-ui-accent' : 'text-gray-500 hover:text-black'}`}
              />
            </motion.div>
          </motion.button>
        </motion.div>

        {/* ── Suggestions dropdown ───────────────────────────────── */}
        <AnimatePresence>
          {focused && searchQuery.length > 0 && suggestions.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: -6, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -4, scale: 0.98 }}
              transition={{ duration: 0.15, ease: [0.22, 1, 0.36, 1] }}
              className="glass absolute left-0 right-0 top-full z-50 mt-2 overflow-hidden rounded-2xl p-1.5 shadow-[0_8px_32px_rgba(0,0,0,0.45)]"
            >
              {suggestions.map((item, i) => (
                <motion.button
                  key={item.place_id || i}
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.04, duration: 0.15 }}
                  type="button"
                  onMouseDown={() => {
                    setSearchQuery(item.display_name)
                    if (item.lat && item.lon) {
                      setSelectedLocation({ lat: item.lat, lng: item.lon }, item.display_name)
                    }
                    setFocused(false)
                  }}
                  className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left text-xs font-medium text-black hover:bg-ui-surface-hover transition-colors shadow-sm"
                >
                  <Search className="h-3 w-3 shrink-0 text-gray-400" />
                  {item.display_name}
                </motion.button>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  )
}
