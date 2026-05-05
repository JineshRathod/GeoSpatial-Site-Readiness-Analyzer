import { AnimatePresence, motion } from 'framer-motion'
import {
  Building2,
  ChevronDown,
  Factory,
  Flame,
  GraduationCap,
  Heart,
  LocateFixed,
  LogOut,
  MapPin,
  Radio,
  Search,
  Settings,
  Store,
  Sun,
  User as UserIcon,
  X,
  Zap,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import type { UiTheme } from '../../theme/uiTheme'

const CATEGORY_FADE = {
  dark: { left: 'rgba(18,24,32,0.92)', right: 'rgba(18,24,32,0.92)' },
  light: { left: 'rgba(255,255,255,0.96)', right: 'rgba(255,255,255,0.96)' },
} as const
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ThemeSwitcher } from '../ThemeSwitcher'
import { useDashboardStore } from '../../store/dashboardStore'
import { useToast } from './Toast'
import { autocompleteLocation } from '../../services/api'

// All available categories (preset pool the user can pick from)
const ALL_CATEGORIES: { label: string; icon: typeof Store }[] = [
  { label: 'restaurant',      icon: Store      },
  { label: 'supermarket',   icon: Building2  },
  { label: 'ev_stations', icon: Zap        },
  { label: 'telecom_towers',     icon: Radio      },
  { label: 'pharmacy',   icon: Sun        },
  { label: 'hardware',  icon: Factory    },
  { label: 'hotel',  icon: Heart      },
  { label: 'hospital',   icon: GraduationCap },
  { label: 'bank',     icon: Flame      },
]

const PILL_SURFACE_DARK: CSSProperties = {
  background: 'rgba(18, 24, 32, 0.92)',
  border: '1px solid rgba(255,255,255,0.10)',
  boxShadow: '0 8px 40px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.06)',
  backdropFilter: 'blur(24px)',
  WebkitBackdropFilter: 'blur(24px)',
}

const PILL_SURFACE_LIGHT: CSSProperties = {
  background: 'rgba(255, 255, 255, 0.94)',
  border: '1px solid rgba(0, 0, 0, 0.08)',
  boxShadow: '0 8px 32px rgba(15, 23, 42, 0.08), inset 0 1px 0 rgba(255,255,255,0.9)',
  backdropFilter: 'blur(24px)',
  WebkitBackdropFilter: 'blur(24px)',
}

function pillSurfaceForTheme(theme: UiTheme): CSSProperties {
  return theme === 'light' ? PILL_SURFACE_LIGHT : PILL_SURFACE_DARK
}

const CATEGORY_CONFIG: { label: string; icon: typeof Store }[] = [
  { label: 'restaurant',      icon: Store      },
  { label: 'supermarket',   icon: Building2  },
  { label: 'ev_stations', icon: Zap        },
  { label: 'telecom_towers',     icon: Radio      },
  { label: 'pharmacy',   icon: Sun        },
]

const MORE_CATEGORIES: { label: string; icon: typeof Store; custom?: boolean }[] = [
  { label: 'hardware',  icon: Factory        },
  { label: 'hotel',  icon: Heart          },
  { label: 'hospital',   icon: GraduationCap  },
  { label: 'bank',     icon: Flame, custom: true },
]

// Default active set (5 categories)
const DEFAULT_ACTIVE = ['restaurant', 'supermarket', 'ev_stations', 'telecom_towers', 'pharmacy']

// Icon pool for user-created categories
const ICON_POOL: { label: string; icon: typeof Store }[] = [
  { label: 'Store',    icon: Store      },
  { label: 'Zap',      icon: Zap        },
  { label: 'Building', icon: Building2  },
  { label: 'Radio',    icon: Radio      },
  { label: 'Sun',      icon: Sun        },
  { label: 'Factory',  icon: Factory    },
  { label: 'Heart',    icon: Heart      },
  { label: 'Flame',    icon: Flame      },
  { label: 'MapPin',   icon: MapPin     },
]

export function FloatingHeader() {
  const [userMenuOpen,     setUserMenuOpen]     = useState(false)
  const [searchFocused,    setSearchFocused]    = useState(false)
  const [locating,         setLocating]         = useState(false)
  const [customizeOpen,    setCustomizeOpen]    = useState(false)
  const [activeCategories, setActiveCategories] = useState<string[]>(DEFAULT_ACTIVE)
  // User-created categories (label only — shown as plain tag icon)
  const [userCategories,   setUserCategories]   = useState<{ label: string; iconKey: string }[]>([])
  // New category form
  const [newCatName,  setNewCatName]  = useState('')
  const newCatIcon = 'Store'  // Hardcoded for now if not used

  const category           = useDashboardStore((s) => s.activeCategory)
  const setCategory        = useDashboardStore((s) => s.setActiveCategory)
  const searchQuery        = useDashboardStore((s) => s.searchQuery)
  const setSearchQuery     = useDashboardStore((s) => s.setSearchQuery)
  const setSelectedLocation= useDashboardStore((s) => s.setSelectedLocation)
  const openControlsPanel  = useDashboardStore((s) => s.openControlsPanel)
  const insightsDockHidden = useDashboardStore((s) => s.insightsDockHidden)
  const uiTheme              = useDashboardStore((s) => s.uiTheme)
  const user                 = useDashboardStore((s) => s.user)
  const logout               = useDashboardStore((s) => s.logout)

  const pillSurface = useMemo(() => pillSurfaceForTheme(uiTheme), [uiTheme])
  const fadeKey = uiTheme === 'light' ? 'light' : 'dark'
  const isLightUi = uiTheme === 'light'

  const [suggestions, setSuggestions] = useState<any[]>([])
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
    autocompleteLocation(debouncedQuery).then(res => setSuggestions(res.slice(0, 5)))
  }, [debouncedQuery])

  const navigate    = useNavigate()
  const location    = useLocation()
  const isDashboard = location.pathname === '/'

  const userRef        = useRef<HTMLDivElement>(null)
  const searchRef      = useRef<HTMLDivElement>(null)
  const scrollTrackRef = useRef<HTMLDivElement>(null)
  const { toast } = useToast()

  // Scroll shadow state
  const [canScrollLeft,  setCanScrollLeft]  = useState(false)
  const [canScrollRight, setCanScrollRight] = useState(false)

  // Recompute scroll edges
  const updateScrollState = () => {
    const el = scrollTrackRef.current
    if (!el) return
    setCanScrollLeft(el.scrollLeft > 4)
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 4)
  }

  // Full pool = preset + user-created
  const allPool = [
    ...ALL_CATEGORIES,
    ...userCategories.map(({ label, iconKey }) => ({
      label,
      icon: ICON_POOL.find((p) => p.label === iconKey)?.icon ?? Store,
    })),
  ]

  // Displayed categories (user-selected active set), preserving order they were added
  const visibleCategories = allPool.filter((c) => activeCategories.includes(c.label))

  // Add user-created category
  const handleAddCustomCategory = () => {
    const name = newCatName.trim()
    if (!name || allPool.some((c) => c.label.toLowerCase() === name.toLowerCase())) return
    setUserCategories((prev) => [...prev, { label: name, iconKey: newCatIcon }])
    setActiveCategories((prev) => [...prev, name])
    setCategory(name)
    setNewCatName('')
  }

  const filteredSuggestions = suggestions

  useEffect(() => {
    const close = (e: MouseEvent) => {
      const t = e.target as Node
      if (userRef.current   && !userRef.current.contains(t))   setUserMenuOpen(false)
      if (searchRef.current && !searchRef.current.contains(t)) setSearchFocused(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  // Recompute scroll shadows whenever visible categories change
  useEffect(() => {
    // Slight delay so layout has settled
    const id = setTimeout(updateScrollState, 60)
    return () => clearTimeout(id)
  }, [visibleCategories])

  // Auto-scroll selected category button into view
  useEffect(() => {
    const track = scrollTrackRef.current
    if (!track) return
    const btn = track.querySelector<HTMLButtonElement>(`[data-cat="${CSS.escape(category)}"]`)
    if (btn) btn.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' })
  }, [category])


  const handleLocate = () => {
    if (!navigator.geolocation) { toast('Geolocation not supported'); return }
    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setSearchQuery(`${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`)
        setLocating(false)
        toast('Current location detected')
      },
      (err) => { toast(`Location error: ${err.message}`); setLocating(false) },
      { timeout: 8000, enableHighAccuracy: true },
    )
  }

  return (
    <header
      className={[
        'pointer-events-none absolute inset-x-0 top-0 z-40 px-3 pt-4 sm:px-4 sm:pt-5',
        isDashboard && !insightsDockHidden ? 'lg:pl-[5rem]' : '',
      ].filter(Boolean).join(' ')}
    >
      <motion.div
        className="pointer-events-auto mx-auto flex w-full min-w-0 max-w-[min(100%,1600px)] flex-col items-stretch gap-2 sm:gap-2.5"
        initial={{ y: -28, opacity: 0, scale: 0.97 }}
        animate={{ y: 0, opacity: 1, scale: 1 }}
        transition={{ type: 'spring', stiffness: 320, damping: 28, mass: 0.8, delay: 0.05 }}
      >
        {isDashboard ? (
          <>
            {/* ── Customize modal overlay ──────────────────────────── */}
            <AnimatePresence>
              {customizeOpen && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="fixed inset-0 z-[200] flex items-center justify-center"
                  style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(10px)' }}
                  onClick={() => setCustomizeOpen(false)}
                >
                  <motion.div
                    initial={{ scale: 0.92, opacity: 0, y: 20 }}
                    animate={{ scale: 1, opacity: 1, y: 0 }}
                    exit={{ scale: 0.92, opacity: 0, y: 16 }}
                    transition={{ type: 'spring', stiffness: 320, damping: 28 }}
                    onClick={(e) => e.stopPropagation()}
                    className="relative w-[400px] max-h-[85vh] overflow-y-auto overflow-x-hidden rounded-3xl p-6 scrollbar-hide"
                    style={{
                      background: 'rgba(12,18,26,0.99)',
                      border: '1px solid rgba(255,255,255,0.10)',
                      boxShadow: '0 24px 80px rgba(0,0,0,0.8)',
                    }}
                  >
                    {/* Modal header */}
                    <div className="mb-4 flex items-center justify-between">
                      <div>
                        <p className="text-[13px] font-bold text-[#D3D9D4]">Customize Categories</p>
                        <p className="mt-0.5 text-[11px]" style={{ color: '#748D92' }}>Toggle which categories appear in the bar</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => setCustomizeOpen(false)}
                        className="flex h-7 w-7 items-center justify-center rounded-full transition-colors hover:bg-white/10"
                        style={{ color: '#748D92' }}
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>

                    {/* ── Category grid ──────────────────────────────── */}
                    <p className="mb-2 text-[10px] font-bold uppercase tracking-widest" style={{ color: '#748D92' }}>Categories</p>
                    <div className="grid grid-cols-3 gap-2">
                      {allPool.map(({ label, icon: Icon }) => {
                        const on = activeCategories.includes(label)
                        const isUser = userCategories.some((u) => u.label === label)
                        return (
                          <motion.button
                            key={label}
                            type="button"
                            whileHover={{ scale: 1.04 }}
                            whileTap={{ scale: 0.95 }}
                            onClick={() => {
                              setActiveCategories((prev) =>
                                on ? prev.filter((c) => c !== label) : [...prev, label]
                              )
                              if (on && category === label) {
                                const remaining = activeCategories.filter((c) => c !== label)
                                if (remaining.length > 0) setCategory(remaining[0])
                              }
                            }}
                            className="relative flex flex-col items-center gap-2 rounded-xl p-3 text-center text-[11px] font-semibold transition-all"
                            style={{
                              background: on ? 'rgba(18,78,102,0.28)' : 'rgba(255,255,255,0.04)',
                              border: on ? '1px solid rgba(18,78,102,0.65)' : '1px solid rgba(255,255,255,0.07)',
                              color: on ? '#D3D9D4' : '#748D92',
                            }}
                          >
                            <div
                              className="flex h-8 w-8 items-center justify-center rounded-full"
                              style={{ background: on ? 'rgba(18,78,102,0.5)' : 'rgba(255,255,255,0.07)' }}
                            >
                              <Icon className="h-3.5 w-3.5" style={{ color: on ? '#22d3ee' : '#748D92' }} />
                            </div>
                            <span className="leading-tight">{label}</span>
                            {on && (
                              <motion.span
                                initial={{ scale: 0 }}
                                animate={{ scale: 1 }}
                                className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full"
                                style={{ background: '#22d3ee' }}
                              />
                            )}
                            {isUser && (
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  setUserCategories((p) => p.filter((u) => u.label !== label))
                                  setActiveCategories((p) => p.filter((c) => c !== label))
                                  if (category === label) setCategory(activeCategories.filter((c) => c !== label)[0] ?? 'Retail')
                                }}
                                className="absolute left-1.5 top-1.5 flex h-4 w-4 items-center justify-center rounded-full hover:bg-red-500/20"
                                style={{ color: '#748D92' }}
                              >
                                <X className="h-2.5 w-2.5" />
                              </button>
                            )}
                          </motion.button>
                        )
                      })}
                    </div>

                    {/* Modal footer */}
                    <div className="mt-5 flex items-center justify-between">
                      <button
                        type="button"
                        onClick={() => { setActiveCategories(DEFAULT_ACTIVE); setUserCategories([]) }}
                        className="text-[11px] font-medium transition-colors hover:text-[#D3D9D4]"
                        style={{ color: '#748D92' }}
                      >
                        Reset to default
                      </button>
                      <motion.button
                        type="button"
                        whileHover={{ scale: 1.04 }}
                        whileTap={{ scale: 0.96 }}
                        onClick={() => setCustomizeOpen(false)}
                        className="rounded-xl px-5 py-2 text-[12px] font-bold text-white"
                        style={{ background: '#124E66', boxShadow: '0 2px 12px rgba(18,78,102,0.5)' }}
                      >
                        Done
                      </motion.button>
                    </div>
                  </motion.div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Single top bar: search | categories | theme & profile */}
            <div
              className={`pointer-events-auto flex min-h-[3rem] w-full min-w-0 flex-col divide-y overflow-hidden rounded-2xl sm:flex-row sm:items-stretch sm:divide-x sm:divide-y-0 ${
                uiTheme === 'light' ? 'divide-black/10' : 'divide-white/10'
              }`}
              style={pillSurface}
            >
            {/* ── Search ──────────── */}
            <div className="relative min-w-0 flex-1 px-1.5 py-1.5 sm:px-2 sm:py-1.5" ref={searchRef}>
              <motion.div
                animate={{
                  width: searchFocused ? 360 : (searchQuery.length > 0 ? 340 : 220),
                  boxShadow: searchFocused
                    ? isLightUi
                      ? '0 0 0 3px rgba(18,78,102,0.25), 0 0 24px rgba(18,78,102,0.15)'
                      : '0 0 0 3px rgba(34,211,238,0.22), 0 0 24px rgba(0,0,0,0.35)'
                    : '0 0 0 0px transparent',
                }}
                transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
                className="flex h-12 w-full max-w-full items-center gap-2.5 rounded-full px-3.5 sm:w-auto"
                style={{
                  maxWidth: 'min(360px, calc(100vw - 2rem))',
                  background: isLightUi
                    ? (searchFocused ? 'rgba(255,255,255,0.98)' : 'rgba(255,255,255,0.85)')
                    : (searchFocused ? 'rgba(30,38,44,0.96)' : 'rgba(24,30,36,0.92)'),
                  border: isLightUi
                    ? (searchFocused ? '1px solid rgba(18,78,102,0.6)' : '1px solid rgba(0,0,0,0.1)')
                    : (searchFocused ? '1px solid rgba(34,211,238,0.45)' : '1px solid rgba(255,255,255,0.12)'),
                  backdropFilter: 'blur(20px)',
                  WebkitBackdropFilter: 'blur(20px)',
                }}
              >
                <Search className={`h-4 w-4 shrink-0 ${isLightUi ? 'text-gray-500' : 'text-slate-400'}`} />
                <input
                  value={searchQuery}
                  onFocus={() => setSearchFocused(true)}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className={`min-w-0 flex-1 bg-transparent text-[13px] font-medium outline-none ${
                    isLightUi
                      ? 'text-black placeholder:text-gray-500'
                      : 'text-slate-100 placeholder:text-slate-500'
                  }`}
                  placeholder="Search location…"
                />
                <AnimatePresence>
                  {searchQuery.length > 0 && (
                    <motion.button
                      initial={{ opacity: 0, scale: 0.5 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.5 }}
                      transition={{ duration: 0.1 }}
                      type="button"
                      onClick={() => setSearchQuery('')}
                      className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full"
                      style={{ background: isLightUi ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.08)' }}
                    >
                      <X className={`h-2.5 w-2.5 ${isLightUi ? 'text-black' : 'text-slate-200'}`} />
                    </motion.button>
                  )}
                </AnimatePresence>
                <motion.button
                  type="button"
                  onClick={handleLocate}
                  whileHover={{ scale: 1.15 }}
                  whileTap={{ scale: 0.9 }}
                  title="Use my current location"
                  className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full"
                  style={{ background: isLightUi ? 'rgba(0,0,0,0.04)' : 'rgba(255,255,255,0.07)' }}
                >
                  <motion.div
                    animate={locating ? { rotate: 360 } : { rotate: 0 }}
                    transition={locating ? { repeat: Infinity, duration: 1, ease: 'linear' } : {}}
                  >
                    <LocateFixed className={`h-3 w-3 ${locating ? 'text-[#22d3ee]' : isLightUi ? 'text-[#748D92]' : 'text-slate-500'}`} />
                  </motion.div>
                </motion.button>
              </motion.div>

              {/* Suggestions dropdown */}
              <AnimatePresence>
                {searchFocused && searchQuery.length > 0 && filteredSuggestions.length > 0 && (
                  <motion.div
                    initial={{ opacity: 0, y: -8, scale: 0.97 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -6, scale: 0.97 }}
                    transition={{ duration: 0.15, ease: [0.22, 1, 0.36, 1] }}
                    className="absolute left-0 top-full z-50 mt-2 w-80 overflow-hidden rounded-2xl p-1.5"
                    style={{
                      background: isLightUi ? 'rgba(255,255,255,0.98)' : 'rgba(22,28,34,0.98)',
                      border: isLightUi ? '1px solid rgba(0,0,0,0.10)' : '1px solid rgba(255,255,255,0.10)',
                      boxShadow: isLightUi ? '0 16px 48px rgba(0,0,0,0.2)' : '0 16px 48px rgba(0,0,0,0.55)',
                      backdropFilter: 'blur(24px)',
                    }}
                  >
                    {filteredSuggestions.map((item, i) => (
                      <motion.button
                        key={item.place_id || i}
                        initial={{ opacity: 0, x: -4 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.04 }}
                        type="button"
                        onMouseDown={() => {
                          setSearchQuery(item.display_name)
                          if (item.lat && item.lon) {
                            setSelectedLocation({lat: item.lat, lng: item.lon}, item.display_name)
                            openControlsPanel()
                          }
                          setSearchFocused(false)
                        }}
                        className={`flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left text-[11px] font-medium transition-colors ${
                          isLightUi ? 'text-black hover:bg-black/5' : 'text-slate-100 hover:bg-white/10'
                        }`}
                      >
                        <Search className={`h-3 w-3 shrink-0 ${isLightUi ? 'text-gray-500' : 'text-slate-400'}`} />
                        {item.display_name}
                      </motion.button>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* ── Categories ── */}
            <AnimatePresence mode="popLayout">
              {!insightsDockHidden && (
                <motion.div
                  key="categories-pill"
                  initial={{ opacity: 0, scale: 0.96 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.96 }}
                  transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
                  className="flex min-h-12 min-w-0 flex-1 items-center justify-center px-1 py-1 sm:px-2"
                  style={{ maxWidth: 'min(92vw, 52rem)' }}
                >
                  <div className="flex h-full min-h-12 w-full min-w-0 items-center">
                    {/* Scroll track with edge fade masks */}
                    <div
                      className="relative flex shrink-0 items-center"
                      style={{ maxWidth: 'min(54vw, 40rem)' }}
                    >
                      {/* Left fade mask — appears when scrolled right */}
                      <div
                        className="pointer-events-none absolute left-0 top-0 z-20 h-full w-10 transition-opacity duration-300"
                        style={{
                          background: `linear-gradient(to right, ${CATEGORY_FADE[fadeKey].left} 0%, transparent 100%)`,
                          opacity: canScrollLeft ? 1 : 0,
                          borderRadius: '999px 0 0 999px',
                        }}
                      />
                      {/* Right fade mask — appears when more content ahead */}
                      <div
                        className="pointer-events-none absolute right-0 top-0 z-20 h-full w-10 transition-opacity duration-300"
                        style={{
                          background: `linear-gradient(to left, ${CATEGORY_FADE[fadeKey].right} 0%, transparent 100%)`,
                          opacity: canScrollRight ? 1 : 0,
                          borderRadius: '0 999px 999px 0',
                        }}
                      />
                      {/* Actual scrollable row */}
                      <div
                        ref={scrollTrackRef}
                        onScroll={updateScrollState}
                        className="flex items-center gap-0.5 overflow-x-auto scrollbar-hide"
                        style={{ scrollBehavior: 'smooth' }}
                      >
                        {visibleCategories.map(({ label, icon: Icon }) => {
                          const isActive = category === label
                          const inactive = uiTheme === 'light' ? '#64748b' : '#748D92'
                          const activeFg = '#f8fafc'
                          return (
                            <motion.button
                              key={label}
                              layout
                              data-cat={label}
                              type="button"
                              onClick={() => setCategory(label)}
                              className="relative flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-3 py-1.5 text-[12px] font-semibold"
                              style={{ color: isActive ? activeFg : inactive }}
                              animate={{ color: isActive ? activeFg : inactive }}
                              transition={{ duration: 0.15 }}
                              whileHover={!isActive ? { color: uiTheme === 'light' ? '#0f172a' : '#D3D9D4' } as never : {}}
                            >
                              {/* Fluid active background — lives inside button */}
                              {isActive && (
                                <motion.span
                                  layoutId="cat-active-bg"
                                  className="absolute inset-0 rounded-full"
                                  style={{
                                    background: isLightUi ? '#0284c7' : '#124E66',
                                    boxShadow: isLightUi
                                      ? '0 2px 12px rgba(2,132,199,0.35)'
                                      : '0 2px 14px rgba(18,78,102,0.6)',
                                  }}
                                  transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                                />
                              )}
                              <span className="relative z-10 flex items-center gap-1.5">
                                <Icon className="h-3.5 w-3.5 shrink-0" />
                                <span className="hidden sm:inline">{label}</span>
                              </span>
                            </motion.button>
                          )
                        })}
                      </div>
                    </div>

                    {/* Separator */}
                    <div
                      className="mx-1.5 h-4 w-px shrink-0"
                      style={{ background: uiTheme === 'light' ? 'rgba(0,0,0,0.10)' : 'rgba(255,255,255,0.10)' }}
                    />

                    {/* ✦ Customize button — always visible, highlighted */}
                    <motion.button
                      type="button"
                      onClick={() => setCustomizeOpen(true)}
                      whileHover={{ scale: 1.06 }}
                      whileTap={{ scale: 0.94 }}
                      className="relative flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] font-bold"
                      style={{
                        background: 'linear-gradient(135deg, rgba(34,211,238,0.18), rgba(18,78,102,0.25))',
                        border: '1px solid rgba(34,211,238,0.40)',
                        color: '#22d3ee',
                        boxShadow: '0 0 14px rgba(34,211,238,0.14)',
                      }}
                    >
                      <Zap className="h-3 w-3" />
                      <span className="hidden sm:inline">Customize</span>
                    </motion.button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* ── Theme + user ─────────────────────────────── */}
            <div className="flex h-12 shrink-0 items-center gap-1 px-2 pr-2.5 sm:px-2.5">
              <ThemeSwitcher variant="compact" />
              <div className="relative" ref={userRef}>
                {user.isAuthenticated ? (
                  <button
                    type="button"
                    onClick={() => setUserMenuOpen((v) => !v)}
                    className="flex items-center gap-2 rounded-full px-2 py-1 transition-all"
                    style={{
                      background: userMenuOpen
                        ? (uiTheme === 'light' ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.08)')
                        : 'transparent',
                    }}
                  >
                    <div
                      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-bold uppercase"
                      style={{
                        background: 'linear-gradient(135deg, #124E66, #1a6b8a)',
                        color: '#f8fafc',
                        boxShadow: uiTheme === 'light'
                          ? '0 0 0 2px rgba(18,78,102,0.25)'
                          : '0 0 0 2px rgba(18,78,102,0.4)',
                      }}
                    >
                      {user.name.charAt(0)}
                    </div>
                    <span
                      className={`hidden max-w-[7rem] truncate text-[12px] font-semibold sm:block ${
                        uiTheme === 'light' ? 'text-slate-800' : 'text-[#D3D9D4]'
                      }`}
                    >
                      {user.name}
                    </span>
                    <ChevronDown
                      className={`hidden h-3.5 w-3.5 shrink-0 sm:block transition-transform duration-150 ${
                        uiTheme === 'light' ? 'text-slate-500' : 'text-[#748D92]'
                      } ${userMenuOpen ? 'rotate-180' : ''}`}
                    />
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => navigate('/login')}
                    className="rounded-full px-4 py-2 text-xs font-bold text-[#D3D9D4] transition-all"
                    style={{ background: '#124E66', boxShadow: '0 2px 10px rgba(18,78,102,0.4)' }}
                  >
                    Sign In
                  </button>
                )}

                <AnimatePresence>
                  {userMenuOpen && user.isAuthenticated && (
                    <motion.div
                      initial={{ opacity: 0, scale: 0.95, y: -8 }}
                      animate={{ opacity: 1, scale: 1, y: 0 }}
                      exit={{ opacity: 0, scale: 0.95, y: -6 }}
                      transition={{ type: 'spring', stiffness: 340, damping: 28 }}
                      className="absolute right-0 top-full z-50 mt-3 w-52 overflow-hidden rounded-2xl"
                      style={{
                        background: 'rgba(15,21,28,0.97)',
                        border: '1px solid rgba(255,255,255,0.10)',
                        boxShadow: '0 20px 60px rgba(0,0,0,0.7)',
                        backdropFilter: 'blur(24px)',
                      }}
                    >
                      <div className="px-4 pb-3 pt-3.5">
                        <div className="flex items-center gap-3">
                          <div
                            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-bold uppercase"
                            style={{
                              background: 'linear-gradient(135deg, #124E66, #1a6b8a)',
                              color: '#D3D9D4',
                            }}
                          >
                            {user.name.charAt(0)}
                          </div>
                          <div className="min-w-0">
                            <p className="truncate text-[12px] font-bold text-[#D3D9D4]">{user.name}</p>
                            <p className="truncate text-[10px] text-[#748D92]">{user.email}</p>
                          </div>
                        </div>
                      </div>

                      <div className="mx-3 h-px" style={{ background: 'rgba(255,255,255,0.07)' }} />

                      <div className="space-y-0.5 p-1.5">
                        {[
                          { icon: UserIcon, label: 'Profile',     path: '/profile'  },
                          { icon: Settings, label: 'Settings',    path: '/settings' },
                          { icon: MapPin,   label: 'Back to map', path: '/'         },
                        ].filter(({ label }) => !(isDashboard && label === 'Back to map'))
                         .map(({ icon: Icon, label, path }) => (
                          <button
                            key={label}
                            type="button"
                            onClick={() => { setUserMenuOpen(false); navigate(path) }}
                            className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-[11px] font-semibold text-[#D3D9D4] transition-colors hover:bg-white/6"
                            style={{ color: '#D3D9D4' }}
                            onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.06)' }}
                            onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'transparent' }}
                          >
                            <Icon className="h-3.5 w-3.5 shrink-0" style={{ color: '#748D92' }} />
                            {label}
                          </button>
                        ))}
                      </div>

                      <div className="mx-3 h-px" style={{ background: 'rgba(255,255,255,0.07)' }} />

                      <div className="p-1.5">
                        <button
                          type="button"
                          onClick={() => { setUserMenuOpen(false); logout(); navigate('/login') }}
                          className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-[11px] font-semibold text-red-400 transition-colors"
                          onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(239,68,68,0.08)' }}
                          onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'transparent' }}
                        >
                          <LogOut className="h-3.5 w-3.5 shrink-0" />
                          Sign out
                        </button>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>
            </div>
          </>
        ) : (
          <>
            <div
              className="pointer-events-auto flex h-14 min-w-0 flex-1 items-center rounded-full px-3 sm:max-w-xs"
              style={pillSurface}
            >
              <Link
                to="/"
                className={`flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-[#124E66] transition-colors ${
                  uiTheme === 'light' ? 'hover:text-slate-900' : 'hover:text-[#D3D9D4]'
                }`}
              >
                <MapPin className="h-3.5 w-3.5 shrink-0" /> Back to map
              </Link>
            </div>
            <div
              className="pointer-events-auto flex h-14 shrink-0 items-center gap-1 rounded-full px-2 pr-2.5"
              style={pillSurface}
            >
              <ThemeSwitcher variant="compact" />
              <div className="relative" ref={userRef}>
                {user.isAuthenticated ? (
                  <button
                    type="button"
                    onClick={() => setUserMenuOpen((v) => !v)}
                    className="flex items-center gap-2 rounded-full px-2 py-1 transition-all"
                    style={{
                      background: userMenuOpen
                        ? (uiTheme === 'light' ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.08)')
                        : 'transparent',
                    }}
                  >
                    <div
                      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-bold uppercase"
                      style={{
                        background: 'linear-gradient(135deg, #124E66, #1a6b8a)',
                        color: '#f8fafc',
                        boxShadow: uiTheme === 'light'
                          ? '0 0 0 2px rgba(18,78,102,0.25)'
                          : '0 0 0 2px rgba(18,78,102,0.4)',
                      }}
                    >
                      {user.name.charAt(0)}
                    </div>
                    <span
                      className={`hidden max-w-[7rem] truncate text-[12px] font-semibold sm:block ${
                        uiTheme === 'light' ? 'text-slate-800' : 'text-[#D3D9D4]'
                      }`}
                    >
                      {user.name}
                    </span>
                    <ChevronDown
                      className={`hidden h-3.5 w-3.5 shrink-0 sm:block transition-transform duration-150 ${
                        uiTheme === 'light' ? 'text-slate-500' : 'text-[#748D92]'
                      } ${userMenuOpen ? 'rotate-180' : ''}`}
                    />
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => navigate('/login')}
                    className="rounded-full px-4 py-2 text-xs font-bold text-[#D3D9D4] transition-all"
                    style={{ background: '#124E66', boxShadow: '0 2px 10px rgba(18,78,102,0.4)' }}
                  >
                    Sign In
                  </button>
                )}

                <AnimatePresence>
                  {userMenuOpen && user.isAuthenticated && (
                    <motion.div
                      initial={{ opacity: 0, scale: 0.95, y: -8 }}
                      animate={{ opacity: 1, scale: 1, y: 0 }}
                      exit={{ opacity: 0, scale: 0.95, y: -6 }}
                      transition={{ type: 'spring', stiffness: 340, damping: 28 }}
                      className="absolute right-0 top-full z-50 mt-3 w-52 overflow-hidden rounded-2xl"
                      style={{
                        background: 'rgba(15,21,28,0.97)',
                        border: '1px solid rgba(255,255,255,0.10)',
                        boxShadow: '0 20px 60px rgba(0,0,0,0.7)',
                        backdropFilter: 'blur(24px)',
                      }}
                    >
                      <div className="px-4 pb-3 pt-3.5">
                        <div className="flex items-center gap-3">
                          <div
                            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-bold uppercase"
                            style={{
                              background: 'linear-gradient(135deg, #124E66, #1a6b8a)',
                              color: '#D3D9D4',
                            }}
                          >
                            {user.name.charAt(0)}
                          </div>
                          <div className="min-w-0">
                            <p className="truncate text-[12px] font-bold text-[#D3D9D4]">{user.name}</p>
                            <p className="truncate text-[10px] text-[#748D92]">{user.email}</p>
                          </div>
                        </div>
                      </div>

                      <div className="mx-3 h-px" style={{ background: 'rgba(255,255,255,0.07)' }} />

                      <div className="space-y-0.5 p-1.5">
                        {[
                          { icon: UserIcon, label: 'Profile',     path: '/profile'  },
                          { icon: Settings, label: 'Settings',    path: '/settings' },
                          { icon: MapPin,   label: 'Back to map', path: '/'         },
                        ].filter(({ label }) => !(isDashboard && label === 'Back to map'))
                         .map(({ icon: Icon, label, path }) => (
                          <button
                            key={label}
                            type="button"
                            onClick={() => { setUserMenuOpen(false); navigate(path) }}
                            className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-[11px] font-semibold text-[#D3D9D4] transition-colors hover:bg-white/6"
                            style={{ color: '#D3D9D4' }}
                            onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.06)' }}
                            onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'transparent' }}
                          >
                            <Icon className="h-3.5 w-3.5 shrink-0" style={{ color: '#748D92' }} />
                            {label}
                          </button>
                        ))}
                      </div>

                      <div className="mx-3 h-px" style={{ background: 'rgba(255,255,255,0.07)' }} />

                      <div className="p-1.5">
                        <button
                          type="button"
                          onClick={() => { setUserMenuOpen(false); logout(); navigate('/login') }}
                          className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-[11px] font-semibold text-red-400 transition-colors"
                          onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(239,68,68,0.08)' }}
                          onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'transparent' }}
                        >
                          <LogOut className="h-3.5 w-3.5 shrink-0" />
                          Sign out
                        </button>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>
          </>
        )}
      </motion.div>
    </header>
  )
}
