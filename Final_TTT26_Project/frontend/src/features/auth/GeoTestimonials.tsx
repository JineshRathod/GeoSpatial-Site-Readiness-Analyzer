import type { CSSProperties } from 'react'

const ITEMS = [
  {
    name: 'Amit Shah',
    quote: 'Reduced site selection time by 60%',
    rotate: '-2deg',
    offset: 'ml-0 mr-auto',
  },
  {
    name: 'Priya Mehta',
    quote: 'Accurate geospatial insights boosted expansion',
    rotate: '0deg',
    offset: 'mx-auto',
  },
  {
    name: 'Rahul Verma',
    quote: 'AI scoring simplified decision making',
    rotate: '2deg',
    offset: 'ml-auto mr-0',
  },
]

export function GeoTestimonials() {
  return (
    <div className="flex flex-col gap-6 py-2">
      <p className="animate-element text-sm font-semibold tracking-tight text-ui-text" style={{ animationDelay: '0.1s' }}>
        Trusted by location teams
      </p>
      <ul className="flex flex-col gap-5">
        {ITEMS.map((item, i) => (
          <li
            key={item.name}
            className={`animate-element max-w-sm ${item.offset}`}
            style={{ animationDelay: `${0.15 + i * 0.08}s` }}
          >
            <div
              className="auth-testimonial-card surface-panel rounded-2xl border p-4 shadow-lg backdrop-blur-md"
              style={
                {
                  '--auth-rotate': item.rotate,
                  '--float-delay': `${i * 0.4}s`,
                } as CSSProperties
              }
            >
              <p className="text-sm leading-relaxed text-ui-muted">{item.quote}</p>
              <p className="mt-3 text-xs font-semibold text-ui-text">{item.name}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
