import type { PropsWithChildren } from 'react'
import { FloatingHeader } from '../ui/FloatingHeader'

export function SecondaryPageLayout({ children }: PropsWithChildren) {
  return (
    <div className="relative min-h-screen bg-ui-bg text-ui-text transition-colors duration-300">
      {/* Subtle radial gradient background */}
      <div
        className="pointer-events-none fixed inset-0 opacity-40"
        style={{
          background: 'radial-gradient(ellipse 80% 60% at 50% -10%, color-mix(in srgb, var(--accent) 18%, transparent), transparent)',
        }}
        aria-hidden
      />
      <FloatingHeader />
      <div className="relative mx-auto max-w-2xl px-4 pb-16 pt-24">
        {children}
      </div>
    </div>
  )
}
