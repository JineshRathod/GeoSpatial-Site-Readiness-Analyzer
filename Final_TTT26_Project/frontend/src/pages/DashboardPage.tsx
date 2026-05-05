import { Suspense, lazy, useEffect } from 'react'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { useDashboardStore } from '../store/dashboardStore'
import { InsightsPanel } from '../features/insights/InsightsPanel'
import { SidebarPanel } from '../features/sidebar/SidebarPanel'
import { FloatingHeader } from '../components/ui/FloatingHeader'
const MapCanvas = lazy(() => import('../features/map/MapCanvas'))

export function DashboardPage() {
  const searchQuery = useDashboardStore((state) => state.searchQuery)
  const debouncedSearch = useDebouncedValue(searchQuery, 240)

  useEffect(() => {
    document.title = debouncedSearch ? `${debouncedSearch} | Geo Dashboard` : 'Geo Dashboard'
  }, [debouncedSearch])

  return (
    <main className="relative h-screen w-full overflow-hidden bg-ui-bg transition-colors duration-300">
      <Suspense
        fallback={
          <div className="flex h-full flex-col items-center justify-center gap-3 bg-ui-bg">
            <div className="h-10 w-10 animate-pulse rounded-full bg-ui-border/40" />
            <p className="typo-muted">Loading map…</p>
          </div>
        }
      >
        <MapCanvas />
      </Suspense>

      <FloatingHeader />

      <div className="hidden lg:block">
        <SidebarPanel />
        <InsightsPanel />
      </div>

      <div className="lg:hidden">
        <SidebarPanel mobile />
        <InsightsPanel mobile />
      </div>
    </main>
  )
}
