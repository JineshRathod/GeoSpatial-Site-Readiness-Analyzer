import { Eye, EyeOff } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AuthShell } from '../features/auth/AuthShell'
import { useDashboardStore } from '../store/dashboardStore'

const GoogleIcon = () => (
  <svg width="18" height="18" viewBox="0 0 48 48">
    <path fill="#FFC107" d="M43.6 20.1H42V20H24v8h11.3C33.7 32.7 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.7-.4-3.9z" />
    <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
    <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z" />
    <path fill="#1976D2" d="M43.6 20.1H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C42 35 44 30 44 24c0-1.3-.1-2.7-.4-3.9z" />
  </svg>
)

type LocState = { status: 'idle' } | { status: 'asking' } | { status: 'granted'; lat: number; lng: number; label: string } | { status: 'denied' }

export function SignInPage() {
  const login = useDashboardStore((s) => s.login)
  const setSelectedLocation = useDashboardStore((s) => s.setSelectedLocation)
  const navigate = useNavigate()
  const [showPw, setShowPw] = useState(false)
  const [busy, setBusy] = useState(false)
  const [loc, setLoc] = useState<LocState>({ status: 'idle' })

  const askLocation = () => {
    if (!navigator.geolocation) { setLoc({ status: 'denied' }); return }
    setLoc({ status: 'asking' })
    navigator.geolocation.getCurrentPosition(
      ({ coords: { latitude: lat, longitude: lng } }) => {
        fetch(`https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json`)
          .then(r => r.json())
          .then(d => {
            const label = d?.address?.city || d?.address?.town || d?.address?.county || `${lat.toFixed(3)}, ${lng.toFixed(3)}`
            setLoc({ status: 'granted', lat, lng, label })
          })
          .catch(() => setLoc({ status: 'granted', lat, lng, label: `${lat.toFixed(3)}, ${lng.toFixed(3)}` }))
      },
      () => setLoc({ status: 'denied' }),
      { timeout: 8000 },
    )
  }

  const onSignIn = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setBusy(true)
    const fd = new FormData(e.currentTarget)
    const email = String(fd.get('email') ?? '')
    const local = email.split('@')[0] || 'User'
    login({ name: local.charAt(0).toUpperCase() + local.slice(1), email: email || 'user@example.com', role: 'Analyst' })
    if (loc.status === 'granted') setSelectedLocation({ lat: loc.lat, lng: loc.lng }, loc.label)
    setTimeout(() => navigate('/'), 600)
  }

  return (
    <AuthShell>
      <div style={{ width: '100%', maxWidth: 380 }}>

        {/* ── Heading ─────────────────────────────────────────── */}
        <h1 style={{ fontSize: 42, fontWeight: 800, color: '#fff', letterSpacing: '-0.04em', lineHeight: 1.1, margin: '0 0 10px' }}>
          Welcome
        </h1>
        <p style={{ fontSize: 14, color: 'rgba(255,255,255,0.45)', margin: '0 0 32px', lineHeight: 1.6 }}>
          Access your account and continue your journey with us
        </p>

        {/* ── Location chip ───────────────────────────────────── */}
        {loc.status === 'idle' && (
          <button type="button" onClick={askLocation} style={{
            display: 'flex', alignItems: 'center', gap: 8, width: '100%',
            background: 'rgba(34,211,238,0.08)', border: '1px solid rgba(34,211,238,0.22)',
            borderRadius: 12, padding: '10px 14px', cursor: 'pointer', marginBottom: 20,
            transition: 'background .2s',
          }}
            onMouseEnter={e => (e.currentTarget.style.background = 'rgba(34,211,238,0.14)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'rgba(34,211,238,0.08)')}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#22d3ee" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="10" r="3" /><path d="M12 2C8.1 2 5 5.1 5 9c0 5.3 7 13 7 13s7-7.7 7-13c0-3.9-3.1-7-7-7z" />
            </svg>
            <span style={{ flex: 1, textAlign: 'left', fontSize: 12, color: 'rgba(255,255,255,0.6)', fontWeight: 500 }}>
              Allow location to jump map to your area
            </span>
            <span style={{ fontSize: 11, color: '#22d3ee', fontWeight: 600 }}>Allow →</span>
          </button>
        )}
        {loc.status === 'asking' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '10px 14px', borderRadius: 12, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)', marginBottom: 20 }}>
            <div style={{ width: 13, height: 13, borderRadius: '50%', border: '2px solid rgba(34,211,238,0.3)', borderTopColor: '#22d3ee', animation: 'siSpin .7s linear infinite', flexShrink: 0 }} />
            <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)' }}>Locating…</span>
          </div>
        )}
        {loc.status === 'granted' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', borderRadius: 12, background: 'rgba(52,211,153,0.08)', border: '1px solid rgba(52,211,153,0.22)', marginBottom: 20 }}>
            <span style={{ fontSize: 13 }}>📍</span>
            <span style={{ fontSize: 12, color: '#34d399', fontWeight: 600 }}>{loc.label}</span>
            <span style={{ marginLeft: 'auto', fontSize: 11, color: 'rgba(52,211,153,0.65)' }}>Map will fly here ✓</span>
          </div>
        )}
        {loc.status === 'denied' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', borderRadius: 12, background: 'rgba(239,68,68,0.07)', border: '1px solid rgba(239,68,68,0.18)', marginBottom: 20 }}>
            <span style={{ fontSize: 12, color: '#f87171' }}>Location denied — default view will be used.</span>
          </div>
        )}

        {/* ── Form ────────────────────────────────────────────── */}
        <form onSubmit={onSignIn}>

          {/* Email */}
          <p style={LBL}>Email Address</p>
          <div className="si-field" style={{ marginBottom: 16 }}>
            <input name="email" type="email" required placeholder="Enter your email address"
              style={INPUT} onFocus={focusField} onBlur={blurField} />
          </div>

          {/* Password */}
          <p style={LBL}>Password</p>
          <div className="si-field" style={{ marginBottom: 12, position: 'relative' }}>
            <input name="password" type={showPw ? 'text' : 'password'} required placeholder="Enter your password"
              style={{ ...INPUT, paddingRight: 44 }} onFocus={focusField} onBlur={blurField} />
            <button type="button" onClick={() => setShowPw(v => !v)}
              style={{ position: 'absolute', right: 14, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(255,255,255,0.35)', display: 'flex', padding: 0 }}>
              {showPw
                ? <EyeOff style={{ width: 16, height: 16 }} />
                : <Eye style={{ width: 16, height: 16 }} />}
            </button>
          </div>

          {/* Remember + Reset */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 9, fontSize: 13, color: 'rgba(255,255,255,0.5)', cursor: 'pointer' }}>
              <input type="checkbox" style={{ width: 15, height: 15, accentColor: '#22d3ee', cursor: 'pointer' }} />
              Keep me signed in
            </label>
            <button type="button" onClick={() => window.alert('Password reset.')}
              style={{ fontSize: 13, color: '#22d3ee', background: 'none', border: 'none', cursor: 'pointer', padding: 0, fontWeight: 500 }}>
              Reset password
            </button>
          </div>

          {/* Sign In */}
          <button type="submit" disabled={busy} style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            width: '100%', border: 'none', borderRadius: 12,
            background: busy ? 'rgba(255,255,255,0.55)' : '#ffffff',
            color: '#09090b', fontSize: 14, fontWeight: 700, padding: '14px',
            cursor: busy ? 'not-allowed' : 'pointer',
            boxShadow: '0 0 0 0 rgba(255,255,255,0)',
            transition: 'background .2s, box-shadow .2s',
            marginBottom: 20,
          }}
            onMouseEnter={e => { if (!busy) e.currentTarget.style.background = 'rgba(255,255,255,0.88)' }}
            onMouseLeave={e => { if (!busy) e.currentTarget.style.background = '#ffffff' }}
          >
            {busy
              ? <div style={{ width: 16, height: 16, borderRadius: '50%', border: '2px solid rgba(0,0,0,0.2)', borderTopColor: '#09090b', animation: 'siSpin .7s linear infinite' }} />
              : 'Sign In'
            }
          </button>
        </form>

        {/* Divider */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
          <div style={{ flex: 1, height: 1, background: 'rgba(255,255,255,0.09)' }} />
          <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.3)' }}>Or continue with</span>
          <div style={{ flex: 1, height: 1, background: 'rgba(255,255,255,0.09)' }} />
        </div>

        {/* Google */}
        <button type="button" onClick={() => window.alert('Connect OAuth in production.')} style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
          width: '100%', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 12,
          background: 'rgba(255,255,255,0.04)', color: 'rgba(255,255,255,0.72)',
          fontSize: 13, fontWeight: 600, padding: '13px', cursor: 'pointer',
          transition: 'background .2s, border-color .2s, color .2s', marginBottom: 28,
        }}
          onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.08)'; e.currentTarget.style.color = '#fff' }}
          onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.04)'; e.currentTarget.style.color = 'rgba(255,255,255,0.72)' }}
        >
          <GoogleIcon />
          Continue with Google
        </button>

        {/* Create account */}
        <p style={{ textAlign: 'center', fontSize: 13, color: 'rgba(255,255,255,0.38)', margin: 0 }}>
          New to our platform?{' '}
          <Link to="/signup" style={{ color: '#22d3ee', fontWeight: 600, textDecoration: 'none' }}>
            Create Account
          </Link>
        </p>

        <style>{`
          .si-field {
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.1);
            background: rgba(255,255,255,0.04);
            transition: border-color .2s, box-shadow .2s;
          }
          .si-field:focus-within {
            border-color: rgba(34,211,238,0.7);
            box-shadow: 0 0 0 3px rgba(34,211,238,0.15);
          }
          @keyframes siSpin { to { transform: rotate(360deg); } }
        `}</style>
      </div>
    </AuthShell>
  )
}

/* ── tiny helpers ────────────────────────────────────────────── */
const LBL: React.CSSProperties = {
  fontSize: 13, fontWeight: 500, color: 'rgba(255,255,255,0.55)', margin: '0 0 7px',
}

const INPUT: React.CSSProperties = {
  width: '100%', background: 'transparent', border: 'none', outline: 'none',
  fontSize: 14, color: '#fff', padding: '13px 14px', boxSizing: 'border-box',
  fontFamily: 'inherit',
}

function focusField(e: React.FocusEvent<HTMLInputElement>) {
  const wrap = e.currentTarget.closest('.si-field') as HTMLElement | null
  if (wrap) { wrap.style.borderColor = 'rgba(34,211,238,0.7)'; wrap.style.boxShadow = '0 0 0 3px rgba(34,211,238,0.15)' }
}
function blurField(e: React.FocusEvent<HTMLInputElement>) {
  const wrap = e.currentTarget.closest('.si-field') as HTMLElement | null
  if (wrap) { wrap.style.borderColor = 'rgba(255,255,255,0.1)'; wrap.style.boxShadow = 'none' }
}
