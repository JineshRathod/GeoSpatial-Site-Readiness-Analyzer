import { motion, AnimatePresence } from 'framer-motion'
import { useState } from 'react'
import {
  User, Lock, Palette, Bell, ShieldCheck,
  Eye, EyeOff, Check, Save, Zap,
} from 'lucide-react'
import { ThemeSwitcher } from '../components/ThemeSwitcher'
import { useToast } from '../components/ui/Toast'
import { MAP_STYLE_LABELS } from '../constants/mapStyles'
import { useDashboardStore } from '../store/dashboardStore'
import type { DistanceUnit } from '../store/dashboardStore'

/* ── Animation presets ──────────────────────────────────────────── */
const fadeUp = {
  hidden:  { opacity: 0, y: 20 },
  visible: (i = 0) => ({
    opacity: 1, y: 0,
    transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1], delay: i * 0.08 },
  }),
}

/* ── Toggle switch ──────────────────────────────────────────────── */
function Toggle({ checked, onChange, accent = 'ui-accent' }: {
  checked: boolean
  onChange: (v: boolean) => void
  accent?: string
}) {
  return (
    <motion.button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      whileTap={{ scale: 0.9 }}
      className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none ${checked ? 'bg-ui-accent' : 'bg-ui-border/60'}`}
    >
      <motion.span
        layout
        transition={{ type: 'spring', stiffness: 700, damping: 30 }}
        className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-lg ${checked ? 'translate-x-5' : 'translate-x-0'}`}
      />
    </motion.button>
  )
}

/* ── Section card ───────────────────────────────────────────────── */
function Section({
  icon: Icon, title, delay = 0, children,
}: {
  icon: typeof User; title: string; delay?: number; children: React.ReactNode
}) {
  return (
    <motion.div
      variants={fadeUp}
      custom={delay}
      initial="hidden"
      animate="visible"
      className="surface-panel overflow-hidden rounded-2xl transition-all duration-300 hover:border-ui-accent/35 hover:shadow-[0_8px_32px_var(--shadow)]"
    >
      <div className="flex items-center gap-3 border-b border-ui-border px-5 py-4">
        <motion.div
          whileHover={{ scale: 1.1, rotate: 6 }}
          transition={{ type: 'spring', stiffness: 400, damping: 15 }}
          className="flex h-8 w-8 items-center justify-center rounded-xl bg-ui-accent/18 ring-1 ring-ui-accent/35 shadow-[0_0_14px_rgba(18,78,102,0.35)]"
        >
          <Icon className="h-4 w-4 text-ui-accent" />
        </motion.div>
        <h2 className="text-sm font-semibold text-ui-text">{title}</h2>
      </div>
      <div className="space-y-0 divide-y divide-ui-border">{children}</div>
    </motion.div>
  )
}

/* ── Row ────────────────────────────────────────────────────────── */
function Row({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 px-5 py-4 transition-colors hover:bg-ui-surface-hover/50">
      <div className="min-w-0">
        <p className="text-sm font-medium text-ui-text">{label}</p>
        {hint && <p className="mt-0.5 text-xs text-ui-muted">{hint}</p>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  )
}

/* ── Styled input ────────────────────────────────────────────────── */
function SettingsInput({
  value, onChange, type = 'text', placeholder, autoComplete,
}: {
  value: string; onChange: (v: string) => void; type?: string; placeholder?: string; autoComplete?: string
}) {
  const [showPw, setShowPw] = useState(false)
  const [focused, setFocused] = useState(false)
  const isPassword = type === 'password'
  return (
    <motion.div
      animate={{
        boxShadow: focused
          ? '0 0 0 3px rgba(18,78,102,0.25), 0 0 20px rgba(18,78,102,0.1)'
          : '0 0 0 0px transparent',
      }}
      className="relative flex w-full items-center rounded-xl border border-ui-border bg-white/5 px-3 py-2.5 transition-colors focus-within:border-ui-accent"
    >
      <input
        type={isPassword && showPw ? 'text' : type}
        value={value}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        className="min-w-0 flex-1 bg-transparent text-sm text-ui-text outline-none placeholder:text-ui-muted"
      />
      {isPassword && (
        <button type="button" onClick={() => setShowPw((v) => !v)} className="ml-2 shrink-0 text-ui-muted hover:text-ui-text">
          {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      )}
    </motion.div>
  )
}

/* ── Main ────────────────────────────────────────────────────────── */
export function SettingsPage() {
  const preferences    = useDashboardStore((s) => s.preferences)
  const setPreferences = useDashboardStore((s) => s.setPreferences)
  const setMapStyle    = useDashboardStore((s) => s.setMapStyle)
  const user           = useDashboardStore((s) => s.user)
  const { toast }      = useToast()

  const [name,    setName]    = useState(user.name)
  const [email,   setEmail]   = useState(user.email)
  const [curPw,   setCurPw]   = useState('')
  const [newPw,   setNewPw]   = useState('')
  const [cfPw,    setCfPw]    = useState('')
  const [twoFA,   setTwoFA]   = useState(false)
  const [saved,   setSaved]   = useState(false)

  const mapOptions = (['street', 'normal', 'satellite'] as const).map((id) => ({ id, label: MAP_STYLE_LABELS[id] }))

  const handleSave = () => {
    setSaved(true)
    toast('✓ Settings saved!')
    setTimeout(() => setSaved(false), 2200)
  }

  const initials = name.split(' ').map((w) => w[0]).join('').toUpperCase().slice(0, 2) || 'U'

  return (
    <div className="space-y-5">
      {/* ── Page heading ─────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: -14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
        className="flex items-end justify-between"
      >
        <div>
          <h1 className="text-xl font-bold tracking-tight text-ui-text">Settings</h1>
          <p className="mt-1 text-sm text-ui-muted">Manage your account, preferences, and notifications.</p>
        </div>
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.2 }}
          className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-ui-accent to-indigo-500 text-sm font-bold text-white shadow-[0_0_0_3px_rgba(18,78,102,0.3),0_4px_12px_rgba(18,78,102,0.4)]"
        >
          {initials}
        </motion.div>
      </motion.div>

      {/* ── PROFILE ─────────────────────────────────────── */}
      <Section icon={User} title="Profile" delay={1}>
        {/* Avatar row */}
        <div className="flex items-center gap-4 px-5 py-4">
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: 'spring', stiffness: 260, damping: 20, delay: 0.15 }}
            className="relative"
          >
            <motion.div
              animate={{ boxShadow: ['0 0 0 0px rgba(18,78,102,0.4)', '0 0 0 6px rgba(18,78,102,0)', '0 0 0 0px rgba(18,78,102,0.4)'] }}
              transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
              className="flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-ui-accent to-indigo-500 text-lg font-bold text-white"
            >
              {initials}
            </motion.div>
          </motion.div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-ui-text">{name || 'Your Name'}</p>
            <p className="text-xs text-ui-muted">{email || 'your@email.com'}</p>
            <span className="mt-1 inline-block rounded-full bg-ui-accent/15 px-2 py-0.5 text-[10px] font-semibold text-ui-accent">
              {user.role}
            </span>
          </div>
        </div>
        <div className="space-y-3 px-5 py-4">
          <div>
            <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-ui-muted">Display Name</p>
            <SettingsInput value={name} onChange={setName} placeholder="Your name" autoComplete="name" />
          </div>
          <div>
            <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-ui-muted">Email Address</p>
            <SettingsInput value={email} onChange={setEmail} type="email" placeholder="you@example.com" autoComplete="email" />
          </div>
        </div>
      </Section>

      {/* ── SECURITY ─────────────────────────────────────── */}
      <Section icon={Lock} title="Security" delay={2}>
        <div className="space-y-3 px-5 py-4">
          <p className="text-xs font-medium uppercase tracking-wide text-ui-muted">Change Password</p>
          <SettingsInput value={curPw} onChange={setCurPw} type="password" placeholder="Current password" autoComplete="current-password" />
          <SettingsInput value={newPw} onChange={setNewPw} type="password" placeholder="New password" autoComplete="new-password" />
          <SettingsInput value={cfPw}  onChange={setCfPw}  type="password" placeholder="Confirm new password" autoComplete="new-password" />
          <AnimatePresence>
            {newPw && cfPw && newPw !== cfPw && (
              <motion.p
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="text-[11px] font-medium text-red-400"
              >
                ⚠ Passwords don't match
              </motion.p>
            )}
          </AnimatePresence>
          <motion.button
            type="button"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => { setCurPw(''); setNewPw(''); setCfPw(''); toast('✓ Password updated (demo)') }}
            className="btn-secondary w-full py-2 text-xs font-medium"
          >
            Update password
          </motion.button>
        </div>
        <Row label="Two-Factor Authentication" hint="Add an extra layer of security to your account">
          <div className="flex items-center gap-2">
            <AnimatePresence>
              {twoFA && (
                <motion.div
                  initial={{ scale: 0, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  exit={{ scale: 0, opacity: 0 }}
                >
                  <ShieldCheck className="h-4 w-4 text-emerald-400" />
                </motion.div>
              )}
            </AnimatePresence>
            <Toggle checked={twoFA} onChange={(v) => { setTwoFA(v); toast(v ? '🛡 2FA enabled (demo)' : '2FA disabled (demo)') }} />
          </div>
        </Row>
      </Section>

      {/* ── PREFERENCES ────────────────────────────────── */}
      <Section icon={Palette} title="Preferences" delay={3}>
        <div className="space-y-2 px-5 py-4">
          <p className="text-sm font-medium text-ui-text">Theme</p>
          <p className="text-xs text-ui-muted">Syncs with your default map view.</p>
          <ThemeSwitcher variant="full" />
        </div>

        <div className="px-5 py-4">
          <p className="mb-3 text-sm font-medium text-ui-text">Map Default View</p>
          <div className="flex gap-2">
            {mapOptions.map((o, i) => (
              <motion.button
                key={o.id}
                type="button"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 + i * 0.06 }}
                whileHover={{ scale: 1.04 }}
                whileTap={{ scale: 0.96 }}
                onClick={() => { setPreferences({ mapDefaultView: o.id }); setMapStyle(o.id); toast(`Default map: ${o.label}`) }}
                className={`flex-1 rounded-xl border px-3 py-2 text-xs font-medium transition-all ${
                  preferences.mapDefaultView === o.id
                    ? 'border-ui-accent/60 bg-ui-accent/20 text-ui-accent shadow-[0_0_12px_rgba(18,78,102,0.2)]'
                    : 'border-ui-border bg-white/5 text-ui-muted hover:bg-ui-hover hover:text-ui-text'
                }`}
              >
                {o.label}
              </motion.button>
            ))}
          </div>
        </div>

        <Row label="Distance Units">
          <div className="flex gap-1.5 rounded-xl border border-ui-border bg-white/5 p-1">
            {(['km', 'mi'] as DistanceUnit[]).map((u) => (
              <motion.button
                key={u}
                type="button"
                whileHover={{ scale: 1.04 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => setPreferences({ units: u })}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
                  preferences.units === u
                    ? 'bg-ui-accent/25 text-ui-accent shadow-[0_0_10px_rgba(18,78,102,0.2)]'
                    : 'text-ui-muted hover:text-ui-text'
                }`}
              >
                {u === 'km' ? 'Kilometers' : 'Miles'}
              </motion.button>
            ))}
          </div>
        </Row>
      </Section>

      {/* ── NOTIFICATIONS ──────────────────────────────── */}
      <Section icon={Bell} title="Notifications" delay={4}>
        {([
          { key: 'notificationsEmail', label: 'Email Updates',       hint: 'Reports, alerts, and weekly summaries'    },
          { key: 'notificationsPush',  label: 'Push Notifications',  hint: 'Real-time alerts in your browser'         },
        ] as const).map(({ key, label, hint }) => (
          <Row key={key} label={label} hint={hint}>
            <Toggle checked={preferences[key]} onChange={(v) => setPreferences({ [key]: v })} />
          </Row>
        ))}
        <Row label="Analysis Completed" hint="Notify when site analysis finishes">
          <Toggle checked={true} onChange={() => toast('Notification setting updated (demo)')} />
        </Row>
      </Section>

      {/* ── Save button ─────────────────────────────────── */}
      <motion.button
        type="button"
        onClick={handleSave}
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        whileHover={{ scale: 1.02, boxShadow: '0 8px 32px rgba(18,78,102,0.3)' }}
        whileTap={{ scale: 0.97 }}
        className={`flex w-full items-center justify-center gap-2 rounded-2xl py-3.5 text-sm font-bold transition-all duration-300 sm:w-auto sm:px-10 ${
          saved
            ? 'bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/40'
            : 'btn-primary shadow-[0_4px_16px_rgba(18,78,102,0.3)]'
        }`}
      >
        <AnimatePresence mode="wait">
          {saved ? (
            <motion.span
              key="saved"
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              className="flex items-center gap-2"
            >
              <Check className="h-4 w-4" /> Saved!
            </motion.span>
          ) : (
            <motion.span
              key="save"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center gap-2"
            >
              <Save className="h-4 w-4" /> Save Settings
            </motion.span>
          )}
        </AnimatePresence>
      </motion.button>
    </div>
  )
}
