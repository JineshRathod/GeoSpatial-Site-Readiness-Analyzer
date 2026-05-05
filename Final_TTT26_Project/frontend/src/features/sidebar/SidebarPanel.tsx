import { SidebarContainer } from './SidebarContainer'

export function SidebarPanel({ mobile = false }: { mobile?: boolean }) {
  return <SidebarContainer mobile={mobile} />
}
