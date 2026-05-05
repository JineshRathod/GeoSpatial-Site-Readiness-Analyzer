import { Eye, EyeOff } from 'lucide-react'
import { type FormEvent, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AuthShell } from '../features/auth/AuthShell'
import { getPasswordStrength } from '../utils/passwordStrength'

const STRENGTH: Record<string, { label: string; color: string; w: string }> = {
  weak:   { label: 'Weak',   color: '#ef4444', w: '33%'  },
  medium: { label: 'Medium', color: '#f59e0b', w: '66%'  },
  strong: { label: 'Strong', color: '#34d399', w: '100%' },
}

type LocState = { status: 'idle' } | { status: 'asking' } | { status: 'granted'; lat: number; lng: number; label: string } | { status: 'denied' }

export default function Signup() {
  const navigate = useNavigate()
  const [name,     setName]     = useState('')
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [confirm,  setConfirm]  = useState('')
  const [showPw,   setShowPw]   = useState(false)
  const [showCf,   setShowCf]   = useState(false)
  const [busy,     setBusy]     = useState(false)
  const [loc,      setLoc]      = useState<LocState>({ status: 'idle' })

  const strength = useMemo(() => getPasswordStrength(password), [password])
  const mismatch = confirm.length > 0 && password !== confirm
  const meta = STRENGTH[strength]

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

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (mismatch) return
    setBusy(true)
    setTimeout(() => navigate('/login'), 650)
  }

  return (
    <AuthShell>
      <div style={{ width: '100%', maxWidth: 380 }}>

        {/* ── Heading ───────────────────────────────────────── */}
        <h1 style={{ fontSize: 42, fontWeight: 800, color: '#fff', letterSpacing: '-0.04em', lineHeight: 1.1, margin: '0 0 10px' }}>
          Create account
        </h1>
        <p style={{ fontSize: 14, color: 'rgba(255,255,255,0.45)', margin: '0 0 28px', lineHeight: 1.6 }}>
          Join the GeoSpatial intelligence platform today
        </p>

        {/* ── Location chip ─────────────────────────────────── */}
        {loc.status === 'idle' && (
          <button type="button" onClick={askLocation} style={{
            display: 'flex', alignItems: 'center', gap: 8, width: '100%',
            background: 'rgba(34,211,238,0.08)', border: '1px solid rgba(34,211,238,0.22)',
            borderRadius: 12, padding: '10px 14px', cursor: 'pointer', marginBottom: 20,
          }}
            onMouseEnter={e => (e.currentTarget.style.background = 'rgba(34,211,238,0.14)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'rgba(34,211,238,0.08)')}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#22d3ee" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="10" r="3" /><path d="M12 2C8.1 2 5 5.1 5 9c0 5.3 7 13 7 13s7-7.7 7-13c0-3.9-3.1-7-7-7z" />
            </svg>
            <span style={{ flex: 1, textAlign: 'left', fontSize: 12, color: 'rgba(255,255,255,0.6)', fontWeight: 500 }}>
              Allow location to personalise your map view
            </span>
            <span style={{ fontSize: 11, color: '#22d3ee', fontWeight: 600 }}>Allow →</span>
          </button>
        )}
        {loc.status === 'asking' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '10px 14px', borderRadius: 12, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)', marginBottom: 20 }}>
            <div style={{ width: 13, height: 13, borderRadius: '50%', border: '2px solid rgba(34,211,238,0.3)', borderTopColor: '#22d3ee', animation: 'spSpin .7s linear infinite', flexShrink: 0 }} />
            <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)' }}>Locating…</span>
          </div>
        )}
        {loc.status === 'granted' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', borderRadius: 12, background: 'rgba(52,211,153,0.08)', border: '1px solid rgba(52,211,153,0.22)', marginBottom: 20 }}>
            <span style={{ fontSize: 13 }}>📍</span>
            <span style={{ fontSize: 12, color: '#34d399', fontWeight: 600 }}>{loc.label}</span>
            <span style={{ marginLeft: 'auto', fontSize: 11, color: 'rgba(52,211,153,0.65)' }}>Saved ✓</span>
          </div>
        )}
        {loc.status === 'denied' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', borderRadius: 12, background: 'rgba(239,68,68,0.07)', border: '1px solid rgba(239,68,68,0.18)', marginBottom: 20 }}>
            <span style={{ fontSize: 12, color: '#f87171' }}>Location denied — default view will be used.</span>
          </div>
        )}

        {/* ── Form ──────────────────────────────────────────── */}
        <form onSubmit={onSubmit}>

          {/* Name */}
          <p style={LBL}>Full Name</p>
          <div className="su-field" style={{ marginBottom: 14 }}>
            <input type="text" autoComplete="name" required value={name} onChange={e => setName(e.target.value)}
              placeholder="Your full name" style={INPUT} onFocus={focusField} onBlur={blurField} />
          </div>

          {/* Email */}
          <p style={LBL}>Email Address</p>
          <div className="su-field" style={{ marginBottom: 14 }}>
            <input type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)}
              placeholder="you@company.com" style={INPUT} onFocus={focusField} onBlur={blurField} />
          </div>

          {/* Password */}
          <p style={LBL}>Password</p>
          <div className="su-field" style={{ marginBottom: 8, position: 'relative' }}>
            <input type={showPw ? 'text' : 'password'} autoComplete="new-password" required
              value={password} onChange={e => setPassword(e.target.value)}
              placeholder="Min. 8 characters" style={{ ...INPUT, paddingRight: 44 }} onFocus={focusField} onBlur={blurField} />
            <button type="button" onClick={() => setShowPw(v => !v)}
              style={{ position: 'absolute', right: 14, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(255,255,255,0.33)', display: 'flex', padding: 0 }}>
              {showPw ? <EyeOff style={{ width: 16, height: 16 }} /> : <Eye style={{ width: 16, height: 16 }} />}
            </button>
          </div>

          {/* Strength bar */}
          {password.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
              <div style={{ flex: 1, height: 3, borderRadius: 999, background: 'rgba(255,255,255,0.08)', overflow: 'hidden' }}>
                <div style={{ height: '100%', borderRadius: 999, background: meta.color, width: meta.w, transition: 'width .4s ease, background .3s ease' }} />
              </div>
              <span style={{ fontSize: 10, fontWeight: 700, color: meta.color, textTransform: 'uppercase', letterSpacing: '0.06em', minWidth: 38 }}>
                {meta.label}
              </span>
            </div>
          )}
          {!password.length && <div style={{ marginBottom: 14 }} />}

          {/* Confirm */}
          <p style={LBL}>Confirm Password</p>
          <div className={`su-field ${mismatch ? 'su-field-err' : ''}`} style={{ marginBottom: mismatch ? 6 : 22, position: 'relative' }}>
            <input type={showCf ? 'text' : 'password'} autoComplete="new-password" required
              value={confirm} onChange={e => setConfirm(e.target.value)}
              placeholder="Re-enter password" style={{ ...INPUT, paddingRight: 44 }} onFocus={focusField} onBlur={blurField} />
            <button type="button" onClick={() => setShowCf(v => !v)}
              style={{ position: 'absolute', right: 14, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(255,255,255,0.33)', display: 'flex', padding: 0 }}>
              {showCf ? <EyeOff style={{ width: 16, height: 16 }} /> : <Eye style={{ width: 16, height: 16 }} />}
            </button>
          </div>
          {mismatch && <p style={{ fontSize: 12, color: '#f87171', margin: '0 0 16px' }}>⚠ Passwords do not match</p>}

          {/* Submit */}
          <button type="submit" disabled={mismatch || busy} style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            width: '100%', border: 'none', borderRadius: 12,
            background: (mismatch || busy) ? 'rgba(255,255,255,0.55)' : '#ffffff',
            color: '#09090b', fontSize: 14, fontWeight: 700, padding: '14px',
            cursor: (mismatch || busy) ? 'not-allowed' : 'pointer',
            transition: 'background .2s', marginBottom: 28,
          }}
            onMouseEnter={e => { if (!mismatch && !busy) e.currentTarget.style.background = 'rgba(255,255,255,0.88)' }}
            onMouseLeave={e => { if (!mismatch && !busy) e.currentTarget.style.background = '#ffffff' }}
          >
            {busy
              ? <div style={{ width: 16, height: 16, borderRadius: '50%', border: '2px solid rgba(0,0,0,0.2)', borderTopColor: '#09090b', animation: 'spSpin .7s linear infinite' }} />
              : 'Create Account'
            }
          </button>
        </form>

        {/* Footer */}
        <p style={{ textAlign: 'center', fontSize: 13, color: 'rgba(255,255,255,0.38)', margin: '0 0 10px' }}>
          Already have an account?{' '}
          <Link to="/login" style={{ color: '#22d3ee', fontWeight: 600, textDecoration: 'none' }}>Sign In</Link>
        </p>
        <p style={{ textAlign: 'center', fontSize: 11, color: 'rgba(255,255,255,0.2)', margin: 0 }}>
          By signing up you agree to our <a href="#" style={{ color: 'rgba(255,255,255,0.36)', textDecoration: 'underline' }}>Terms</a> &amp; <a href="#" style={{ color: 'rgba(255,255,255,0.36)', textDecoration: 'underline' }}>Privacy Policy</a>.
        </p>

        <style>{`
          .su-field {
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.1);
            background: rgba(255,255,255,0.04);
            transition: border-color .2s, box-shadow .2s;
          }
          .su-field:focus-within {
            border-color: rgba(34,211,238,0.7);
            box-shadow: 0 0 0 3px rgba(34,211,238,0.15);
          }
          .su-field-err {
            border-color: rgba(239,68,68,0.55) !important;
            box-shadow: 0 0 0 3px rgba(239,68,68,0.1) !important;
          }
          @keyframes spSpin { to { transform: rotate(360deg); } }
        `}</style>
      </div>
    </AuthShell>
  )
}

/* ── helpers ─────────────────────────────────────────────────── */
const LBL: React.CSSProperties = {
  fontSize: 13, fontWeight: 500, color: 'rgba(255,255,255,0.55)', margin: '0 0 7px',
}
const INPUT: React.CSSProperties = {
  width: '100%', background: 'transparent', border: 'none', outline: 'none',
  fontSize: 14, color: '#fff', padding: '13px 14px', boxSizing: 'border-box', fontFamily: 'inherit',
}
function focusField(e: React.FocusEvent<HTMLInputElement>) {
  const w = e.currentTarget.closest('.su-field') as HTMLElement | null
  if (w && !w.classList.contains('su-field-err')) { w.style.borderColor = 'rgba(34,211,238,0.7)'; w.style.boxShadow = '0 0 0 3px rgba(34,211,238,0.15)' }
}
function blurField(e: React.FocusEvent<HTMLInputElement>) {
  const w = e.currentTarget.closest('.su-field') as HTMLElement | null
  if (w && !w.classList.contains('su-field-err')) { w.style.borderColor = 'rgba(255,255,255,0.1)'; w.style.boxShadow = 'none' }
}
