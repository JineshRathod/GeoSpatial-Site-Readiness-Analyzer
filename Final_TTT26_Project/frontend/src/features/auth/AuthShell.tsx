import { lazy, Suspense, type PropsWithChildren } from 'react'

const AuthMapPanel = lazy(() =>
  import('./AuthMapPanel').then((m) => ({ default: m.AuthMapPanel })),
)

type AuthShellProps = PropsWithChildren

export function AuthShell({ children }: AuthShellProps) {
  return (
    <div className="auth-shell-root">
      {/* ── LEFT: form panel ─────────────────────────────────────── */}
      <section className="auth-left">
        {/* Logo */}
        <div className="auth-logo">
          <div className="auth-logo-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#22d3ee" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="10" r="4" />
              <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z" />
            </svg>
          </div>
          <span className="auth-logo-text">GeoAnalytics</span>
        </div>

        {/* Vertically centred form content */}
        <div className="auth-form-wrapper">
          {children}
        </div>

        {/* Footer */}
        <p className="auth-footer">© 2026 GeoAnalytics · All rights reserved</p>
      </section>

      {/* ── RIGHT: live map ──────────────────────────────────────── */}
      <section className="auth-right">
        <Suspense fallback={<div className="auth-map-fallback"><div className="auth-map-spinner" /></div>}>
          <AuthMapPanel />
        </Suspense>
      </section>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

        .auth-shell-root {
          display: flex;
          min-height: 100vh;
          width: 100%;
          background: #09090b;
          font-family: 'Inter', system-ui, sans-serif;
          overflow: hidden;
        }

        /* ─ LEFT ─ */
        .auth-left {
          position: relative;
          display: flex;
          flex-direction: column;
          width: 48%;
          max-width: 560px;
          min-width: 380px;
          flex-shrink: 0;
          background: #09090b;
          overflow-y: auto;
        }

        .auth-logo {
          display: flex;
          align-items: center;
          gap: 9px;
          padding: 32px 48px 0;
        }
        .auth-logo-icon {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 32px;
          height: 32px;
          border-radius: 9px;
          background: rgba(34,211,238,0.12);
          box-shadow: 0 0 0 1px rgba(34,211,238,0.28);
        }
        .auth-logo-text {
          font-size: 14px;
          font-weight: 700;
          color: rgba(255,255,255,0.9);
          letter-spacing: -0.02em;
        }

        .auth-form-wrapper {
          flex: 1;
          display: flex;
          align-items: center;
          justify-content: flex-start;
          padding: 40px 48px;
        }

        .auth-footer {
          text-align: center;
          font-size: 11px;
          color: rgba(255,255,255,0.18);
          padding: 0 48px 24px;
          margin: 0;
        }

        /* ─ RIGHT ─ */
        .auth-right {
          position: relative;
          flex: 1;
        }

        .auth-map-fallback {
          position: absolute;
          inset: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          background: #111118;
        }
        .auth-map-spinner {
          width: 34px;
          height: 34px;
          border-radius: 50%;
          border: 2px solid rgba(34,211,238,0.2);
          border-top-color: #22d3ee;
          animation: authShellSpin 0.75s linear infinite;
        }
        @keyframes authShellSpin { to { transform: rotate(360deg); } }

        /* ─ MOBILE ─ */
        @media (max-width: 768px) {
          .auth-right  { display: none; }
          .auth-left   { width: 100%; max-width: 100%; min-width: 0; }
          .auth-form-wrapper { padding: 32px 28px; }
          .auth-logo   { padding: 24px 28px 0; }
        }
      `}</style>
    </div>
  )
}
