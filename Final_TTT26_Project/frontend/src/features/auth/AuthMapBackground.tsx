import { memo } from 'react'

/** Lightweight satellite-style background (CSS zoom/pan — no MapLibre). */
export const AuthMapBackground = memo(function AuthMapBackground() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      <div
        className="auth-map-bg-layer absolute inset-[-8%] bg-cover bg-center"
        style={{
          backgroundImage:
            'url(https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=2400&q=80)',
        }}
        aria-hidden
      />
    </div>
  )
})
