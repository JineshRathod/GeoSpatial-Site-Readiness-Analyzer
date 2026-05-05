import { motion } from 'framer-motion'
import {
  User, Mail, Lock, Eye, EyeOff,
  MapPin, Camera, Check, Trash2, Activity, Shield, Star,
} from 'lucide-react'
import { useState } from 'react'
import { useToast } from '../components/ui/Toast'
import { useDashboardStore } from '../store/dashboardStore'

/* ── Animation presets ──────────────────────────────────────────── */
const fadeUp = {
  hidden:  { opacity: 0, y: 20 },
  visible: (i = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1], delay: i * 0.07 },
  }),
}

/* ── Mock data ─────────────────────────────────────────────────── */
const MOCK_ACTIVITY = [
  { id: 'a1', label: 'Exported PDF report — Bopal Hub',   when: '2h ago',    icon: '📄', color: 'from-blue-500/20 to-blue-500/0'    },
  { id: 'a2', label: 'Compared two retail zones',         when: 'Yesterday', icon: '⚖️', color: 'from-orange-500/20 to-orange-500/0' },
  { id: 'a3', label: 'Updated scoring weights',           when: 'Mon',       icon: '⚙️', color: 'from-purple-500/20 to-purple-500/0' },
  { id: 'a4', label: 'Ran analysis on Prahlad Nagar',     when: 'Last week', icon: '📍', color: 'from-emerald-500/20 to-emerald-500/0'},
]

const STATS = [
  { label: 'Analyses',     value: 24, icon: Star     },
  { label: 'Locations',    value: 8,  icon: MapPin   },
  { label: 'Reports',      value: 6,  icon: Activity },
]

/* ── Tiny shared primitives ─────────────────────────────────────── */
function SectionCard({
  icon: Icon, title, subtitle, delay = 0, children,
}: {
  icon: typeof User; title: string; subtitle?: string; delay?: number; children: React.ReactNode
}) {
  return (
    <motion.div
      variants={fadeUp}
      custom={delay}
      initial="hidden"
      animate="visible"
      className="surface-panel overflow-hidden rounded-2xl transition-all duration-300 hover:border-ui-accent/35 hover:shadow-[0_8px_32px_var(--shadow)]"
    >
      {/* Card header */}
      <div className="flex items-center gap-3 border-b border-ui-border px-5 py-4">
        <motion.div
          whileHover={{ scale: 1.1, rotate: 5 }}
          transition={{ type: 'spring', stiffness: 400, damping: 15 }}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-ui-accent/15 ring-1 ring-ui-accent/30 shadow-[0_0_12px_rgba(18,78,102,0.3)]"
        >
          <Icon className="h-4 w-4 text-ui-accent" />
        </motion.div>
        <div>
          <h2 className="text-sm font-semibold text-ui-text">{title}</h2>
          {subtitle && <p className="text-[11px] text-ui-muted">{subtitle}</p>}
        </div>
      </div>
      <div className="p-5">{children}</div>
    </motion.div>
  )
}

function FieldInput({
  label, value, onChange, type = 'text', placeholder, autoComplete, icon: Icon,
}: {
  label: string; value: string; onChange: (v: string) => void
  type?: string; placeholder?: string; autoComplete?: string; icon?: typeof User
}) {
  const [showPw, setShowPw] = useState(false)
  const [focused, setFocused] = useState(false)
  const isPassword = type === 'password'

  return (
    <div>
      <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-ui-muted">
        {label}
      </label>
      <motion.div
        animate={{
          boxShadow: focused ? '0 0 0 3px rgba(18,78,102,0.25), 0 0 20px rgba(18,78,102,0.1)' : '0 0 0 0px transparent',
        }}
        className="flex items-center gap-2.5 rounded-xl border border-ui-border bg-white/5 px-3 py-2.5 transition-colors duration-150 focus-within:border-ui-accent hover:border-ui-border/80"
      >
        {Icon && <Icon className="h-4 w-4 shrink-0 text-ui-muted" />}
        <input
          type={isPassword && showPw ? 'text' : type}
          value={value}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          autoComplete={autoComplete}
          className="min-w-0 flex-1 bg-transparent text-sm text-ui-text outline-none placeholder:text-ui-muted/60"
        />
        {isPassword && (
          <button type="button" onClick={() => setShowPw((v) => !v)} className="shrink-0 text-ui-muted transition hover:text-ui-text">
            {showPw ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
          </button>
        )}
      </motion.div>
    </div>
  )
}

/* ── Main component ─────────────────────────────────────────────── */
export function ProfilePage() {
  const user    = useDashboardStore((s) => s.user)
  const history = useDashboardStore((s) => s.history)
  const { toast } = useToast()

  const [name,    setName]    = useState(user.name)
  const [email,   setEmail]   = useState(user.email)
  const [curPw,   setCurPw]   = useState('')
  const [newPw,   setNewPw]   = useState('')
  const [cfPw,    setCfPw]    = useState('')
  const [saved,   setSaved]   = useState(false)
  const [pwSaved, setPwSaved] = useState(false)

  if (!user.isAuthenticated) {
    return (
      <div className="flex h-48 items-center justify-center rounded-2xl border border-ui-border bg-ui-glass p-6 text-ui-muted backdrop-blur-xl">
        Sign in to view your profile.
      </div>
    )
  }

  const initials = name.split(' ').map((w) => w[0]).join('').toUpperCase().slice(0, 2) || 'U'

  const handleSaveProfile = () => {
    setSaved(true)
    toast('✓ Profile saved!')
    setTimeout(() => setSaved(false), 2200)
  }

  const handleUpdatePw = () => {
    if (!curPw || !newPw || newPw !== cfPw) { toast('Check passwords and try again.'); return }
    setCurPw(''); setNewPw(''); setCfPw('')
    setPwSaved(true)
    toast('✓ Password updated')
    setTimeout(() => setPwSaved(false), 2200)
  }

  return (
    <div className="space-y-5">
      {/* ── Page hero ──────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: -16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        className="relative overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br from-ui-accent/20 via-ui-glass/80 to-transparent p-6 shadow-[0_8px_32px_rgba(18,78,102,0.2)] backdrop-blur-xl"
      >
        {/* Background glow */}
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,rgba(18,78,102,0.25),transparent_60%)]" />
        <div className="pointer-events-none absolute right-0 top-0 h-40 w-40 rounded-full bg-[radial-gradient(circle,rgba(18,78,102,0.3),transparent_70%)] blur-2xl" />

        <div className="relative flex flex-col items-center gap-5 sm:flex-row sm:items-start">
          {/* Animated avatar */}
          <div className="relative shrink-0">
            <motion.div
              initial={{ scale: 0.7, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: 'spring', stiffness: 260, damping: 20, delay: 0.1 }}
              className="relative"
            >
              {/* Pulse ring */}
              <motion.div
                animate={{ scale: [1, 1.12, 1], opacity: [0.5, 0, 0.5] }}
                transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut' }}
                className="absolute inset-0 rounded-full bg-ui-accent/30"
              />
              <div
                className="flex items-center justify-center rounded-full bg-gradient-to-br from-ui-accent to-indigo-500 text-2xl font-bold text-white shadow-[0_0_0_4px_rgba(18,78,102,0.4),0_8px_24px_rgba(18,78,102,0.4)]"
                style={{ width: 80, height: 80 }}
              >
                {initials}
              </div>
            </motion.div>
            <motion.button
              type="button"
              whileHover={{ scale: 1.15 }}
              whileTap={{ scale: 0.9 }}
              onClick={() => toast('Avatar upload coming soon')}
              className="absolute -bottom-1 -right-1 flex h-7 w-7 items-center justify-center rounded-full border border-white/20 bg-black/50 shadow-md backdrop-blur-md transition hover:bg-white/10"
            >
              <Camera className="h-3.5 w-3.5 text-ui-muted" />
            </motion.button>
          </div>

          {/* Info */}
          <div className="flex-1 text-center sm:text-left">
            <motion.p
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.2, duration: 0.4 }}
              className="text-xl font-bold tracking-tight text-ui-text"
            >
              {user.name}
            </motion.p>
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.28 }}
              className="mt-0.5 text-sm text-ui-muted"
            >
              {user.email}
            </motion.p>
            <motion.span
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.35, type: 'spring' }}
              className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-ui-accent/20 px-3 py-1 text-[11px] font-bold uppercase tracking-wide text-ui-accent ring-1 ring-ui-accent/30"
            >
              <Shield className="h-3 w-3" /> {user.role}
            </motion.span>
          </div>

          {/* Stats */}
          <div className="flex gap-3 sm:gap-4">
            {STATS.map(({ label, value, icon: Icon }, i) => (
              <motion.div
                key={label}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 + i * 0.08, duration: 0.4 }}
                className="flex flex-col items-center gap-1 rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 text-center"
              >
                <Icon className="h-3.5 w-3.5 text-ui-accent" />
                <span className="text-lg font-bold tabular-nums text-ui-text">{value}</span>
                <span className="text-[10px] text-ui-muted">{label}</span>
              </motion.div>
            ))}
          </div>
        </div>
      </motion.div>

      {/* ── SECTION 1: Profile ─────────────────────────── */}
      <SectionCard icon={User} title="Profile" subtitle="Your public identity on the platform" delay={1}>
        <div className="space-y-3">
          <FieldInput label="Display Name" value={name} onChange={setName} placeholder="Your name" autoComplete="name" icon={User} />
          <FieldInput label="Email Address" value={email} onChange={setEmail} type="email" placeholder="you@example.com" autoComplete="email" icon={Mail} />
          <motion.button
            type="button"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.97 }}
            onClick={handleSaveProfile}
            className={`flex items-center gap-1.5 rounded-xl px-4 py-2.5 text-xs font-semibold transition-all duration-200 ${
              saved ? 'bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30' : 'btn-primary'
            }`}
          >
            {saved ? <><Check className="h-3.5 w-3.5" /> Saved!</> : 'Save changes'}
          </motion.button>
        </div>
      </SectionCard>

      {/* ── SECTION 2: Security ────────────────────────── */}
      <SectionCard icon={Lock} title="Account Security" subtitle="Keep your account protected" delay={2}>
        <div className="space-y-3">
          <FieldInput label="Current Password" value={curPw} onChange={setCurPw} type="password" placeholder="Enter current password" autoComplete="current-password" icon={Lock} />
          <FieldInput label="New Password"     value={newPw} onChange={setNewPw} type="password" placeholder="Min. 8 characters"     autoComplete="new-password"     icon={Lock} />
          <FieldInput label="Confirm Password" value={cfPw}  onChange={setCfPw}  type="password" placeholder="Re-enter new password" autoComplete="new-password"     icon={Lock} />
          {newPw && cfPw && newPw !== cfPw && (
            <motion.p
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-[11px] font-medium text-red-400"
            >
              ⚠ Passwords don't match
            </motion.p>
          )}
          <motion.button
            type="button"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.97 }}
            onClick={handleUpdatePw}
            className={`flex items-center gap-1.5 rounded-xl px-4 py-2.5 text-xs font-semibold transition-all duration-200 ${
              pwSaved ? 'bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30' : 'btn-secondary'
            }`}
          >
            {pwSaved ? <><Check className="h-3.5 w-3.5" /> Updated!</> : 'Update Password'}
          </motion.button>
        </div>
      </SectionCard>

      {/* ── SECTION 3: Activity ────────────────────────── */}
      <SectionCard icon={Activity} title="Recent Activity" subtitle="Your last actions on the platform" delay={3}>
        <ul className="space-y-2">
          {MOCK_ACTIVITY.map((row, i) => (
            <motion.li
              key={row.id}
              initial={{ opacity: 0, x: -16 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.35 + i * 0.07, duration: 0.35, ease: 'easeOut' }}
              whileHover={{ x: 4 }}
              className={`flex items-center gap-3 rounded-xl border border-white/8 bg-gradient-to-r ${row.color} px-3 py-2.5 text-sm transition-colors hover:border-ui-accent/20`}
            >
              <span className="text-base leading-none">{row.icon}</span>
              <span className="flex-1 truncate text-xs font-medium text-ui-text">{row.label}</span>
              <span className="shrink-0 text-[11px] text-ui-muted">{row.when}</span>
            </motion.li>
          ))}
        </ul>
      </SectionCard>

      {/* ── SECTION 4: Saved Locations ─────────────────── */}
      <SectionCard icon={MapPin} title="Saved Locations" subtitle="Locations from your analysis history" delay={4}>
        {history.length === 0 ? (
          <p className="py-4 text-center text-xs text-ui-muted">No saved locations yet. Run an analysis to get started.</p>
        ) : (
          <ul className="space-y-2">
            {history.map((item, i) => (
              <motion.li
                key={item.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5 + i * 0.07 }}
                whileHover={{ scale: 1.01 }}
                className="group flex items-center gap-3 rounded-xl border border-white/8 bg-white/4 px-3 py-2.5 text-sm transition-all hover:border-ui-accent/25 hover:bg-ui-accent/8"
              >
                <MapPin className="h-3.5 w-3.5 shrink-0 text-ui-accent" />
                <span className="flex-1 font-medium text-ui-text">{item.name}</span>
                <span className="text-[10px] tabular-nums text-ui-muted">
                  {item.coordinates.lat.toFixed(3)}, {item.coordinates.lng.toFixed(3)}
                </span>
                <motion.button
                  type="button"
                  whileHover={{ scale: 1.1 }}
                  whileTap={{ scale: 0.9 }}
                  onClick={() => toast(`Removed "${item.name}" (demo)`)}
                  className="ml-1 shrink-0 rounded-lg p-1 text-ui-muted opacity-0 transition hover:bg-red-500/15 hover:text-red-400 group-hover:opacity-100"
                >
                  <Trash2 className="h-3 w-3" />
                </motion.button>
              </motion.li>
            ))}
          </ul>
        )}
        {history.length > 0 && (
          <button
            type="button"
            onClick={() => toast('All locations cleared (demo)')}
            className="mt-3 flex items-center gap-1.5 text-[11px] font-medium text-ui-muted transition hover:text-red-400"
          >
            <Trash2 className="h-3 w-3" /> Clear all
          </button>
        )}
      </SectionCard>
    </div>
  )
}
