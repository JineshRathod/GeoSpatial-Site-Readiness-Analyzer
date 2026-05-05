import { useEffect } from 'react'
import { useDashboardStore } from '../store/dashboardStore'

/** Applies `data-theme` on `<html>` for global CSS variables (light / dark / satellite). */
export function ThemeSync() {
  const uiTheme = useDashboardStore((s) => s.uiTheme)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', uiTheme)
  }, [uiTheme])

  return null
}
