import { useMemo } from 'react'

/**
 * Auth surfaces use global CSS variables (`data-theme` on `<html>`).
 * These class strings only add layout; color comes from tokens.
 */
export function useAuthTheme() {
  return useMemo(
    () => ({
      card: 'rounded-2xl border border-ui-border bg-ui-glass p-6 shadow-lg backdrop-blur-xl',
      input:
        'border-ui-border bg-ui-glass/90 text-ui-text placeholder:text-ui-muted focus-within:ring-2 focus-within:ring-ui-accent/30',
      muted: 'text-ui-muted',
      label: 'text-ui-text',
      link: 'text-ui-accent hover:underline',
      strengthTrack: 'bg-ui-border/60',
    }),
    [],
  )
}
