import type { MapStyleId } from '../constants/mapStyles'

/** UI theme drives CSS variables on `document.documentElement` via `data-theme`. */
export type UiTheme = 'light' | 'dark' | 'satellite'

export function mapStyleToUiTheme(mapStyle: MapStyleId): UiTheme {
  if (mapStyle === 'satellite') return 'satellite'
  if (mapStyle === 'normal') return 'light'
  return 'dark'
}

export function uiThemeToMapStyle(theme: UiTheme): MapStyleId {
  if (theme === 'satellite') return 'satellite'
  if (theme === 'light') return 'normal'
  return 'street'
}
