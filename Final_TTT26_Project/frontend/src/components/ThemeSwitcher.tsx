import { AnimatePresence, motion } from 'framer-motion'
import { Moon, Satellite, Sun } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { UiTheme } from '../theme/uiTheme'
import { useDashboardStore } from '../store/dashboardStore'

const OPTIONS: { id: UiTheme; label: string; hint: string; Icon: typeof Sun }[] = [
  { id: 'light',     label: 'Light',     hint: 'Light basemap',      Icon: Sun       },
  { id: 'dark',      label: 'Dark',      hint: 'Street / dark UI',   Icon: Moon      },
  { id: 'satellite', label: 'Satellite', hint: 'Imagery + glass',    Icon: Satellite },
]

type ThemeSwitcherProps = {
  variant?: 'compact' | 'full'
}

export function ThemeSwitcher({ variant = 'compact' }: ThemeSwitcherProps) {
  const [open, setOpen] = useState(false)
  const uiTheme    = useDashboardStore((s) => s.uiTheme)
  const setUiTheme = useDashboardStore((s) => s.setUiTheme)
  const ref = useRef<HTMLDivElement>(null)

  const active = OPTIONS.find((o) => o.id === uiTheme) ?? OPTIONS[1]
  const isLight = uiTheme === 'light'

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  return (
    <div className="relative" ref={ref}>
      {/* ── Trigger — matches other pill-internal elements ── */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="listbox"
        title={`Theme: ${active.label}`}
        className="flex h-7 items-center gap-1.5 rounded-full px-2.5 transition-all duration-150"
        style={{
          background: isLight
            ? (open ? 'rgba(0,0,0,0.06)' : 'rgba(0,0,0,0.03)')
            : (open ? 'rgba(255,255,255,0.10)' : 'rgba(255,255,255,0.05)'),
          border: isLight ? '1px solid rgba(0,0,0,0.10)' : '1px solid rgba(255,255,255,0.10)',
          color: isLight ? '#0f172a' : '#D3D9D4',
        }}
        onMouseEnter={(e) => {
          if (!open) {
            (e.currentTarget as HTMLButtonElement).style.background = isLight
              ? 'rgba(0,0,0,0.07)'
              : 'rgba(255,255,255,0.09)'
          }
        }}
        onMouseLeave={(e) => {
          if (!open) {
            (e.currentTarget as HTMLButtonElement).style.background = isLight
              ? 'rgba(0,0,0,0.03)'
              : 'rgba(255,255,255,0.05)'
          }
        }}
      >
        <active.Icon className="h-3.5 w-3.5 shrink-0" style={{ color: isLight ? '#1d4ed8' : '#124E66' }} aria-hidden />
        {variant === 'full' && (
          <span
            className="hidden text-[11px] font-semibold md:inline"
            style={{ color: isLight ? '#0f172a' : '#D3D9D4' }}
          >
            {active.label}
          </span>
        )}
        <motion.svg
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: 0.2 }}
          width="10" height="10" viewBox="0 0 10 10" fill="none"
          style={{ color: isLight ? '#64748b' : '#748D92' }}
        >
          <path d="M2 3.5L5 6.5L8 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </motion.svg>
      </button>

      {/* ── Dropdown ─────────────────────────────────────────────── */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.97 }}
            transition={{ type: 'spring', stiffness: 340, damping: 28 }}
            role="listbox"
            className="absolute right-0 top-full z-50 mt-3 w-44 overflow-hidden rounded-2xl p-1.5"
            style={{
              background: isLight ? 'rgba(255,255,255,0.98)' : 'rgba(15,21,28,0.97)',
              border: isLight ? '1px solid rgba(0,0,0,0.08)' : '1px solid rgba(255,255,255,0.10)',
              boxShadow: isLight ? '0 16px 48px rgba(15,23,42,0.12)' : '0 16px 48px rgba(0,0,0,0.65)',
              backdropFilter: 'blur(24px)',
            }}
          >
            {/* Label */}
            <p
              className="px-3 pb-1.5 pt-1 text-[10px] font-bold uppercase tracking-widest"
              style={{ color: isLight ? '#64748b' : '#748D92' }}
            >
              Map Theme
            </p>

            {OPTIONS.map((opt) => {
              const isActive = uiTheme === opt.id
              return (
                <button
                  key={opt.id}
                  type="button"
                  role="option"
                  aria-selected={isActive}
                  onClick={() => { setUiTheme(opt.id); setOpen(false) }}
                  className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-all duration-100"
                  style={{
                    background: isActive ? 'rgba(18,78,102,0.20)' : 'transparent',
                    border: isActive ? '1px solid rgba(18,78,102,0.35)' : '1px solid transparent',
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive) {
                      (e.currentTarget as HTMLButtonElement).style.background = isLight
                        ? 'rgba(0,0,0,0.04)'
                        : 'rgba(255,255,255,0.05)'
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive) (e.currentTarget as HTMLButtonElement).style.background = 'transparent'
                  }}
                >
                  {/* Icon badge */}
                  <div
                    className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full"
                    style={{
                      background: isActive
                        ? 'rgba(18,78,102,0.35)'
                        : (isLight ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.07)'),
                    }}
                  >
                    <opt.Icon
                      className="h-3.5 w-3.5"
                      style={{ color: isActive ? (isLight ? '#0e7490' : '#22d3ee') : (isLight ? '#64748b' : '#748D92') }}
                    />
                  </div>

                  {/* Labels */}
                  <span className="flex flex-col gap-0">
                    <span
                      className="text-[12px] font-semibold"
                      style={{ color: isLight ? '#0f172a' : '#D3D9D4' }}
                    >
                      {opt.label}
                    </span>
                    <span className="text-[10px]" style={{ color: isLight ? '#64748b' : '#748D92' }}>
                      {opt.hint}
                    </span>
                  </span>

                  {/* Active dot */}
                  {isActive && (
                    <motion.div
                      layoutId="theme-active-dot"
                      className="ml-auto h-1.5 w-1.5 rounded-full"
                      style={{ background: '#22d3ee' }}
                    />
                  )}
                </button>
              )
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
