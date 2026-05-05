import type { StyleSpecification } from 'maplibre-gl'

/** MapLibre-compatible style URLs and inline specs. */
export type MapStyleId = 'street' | 'normal' | 'satellite'

export const MAP_STYLE_LABELS: Record<MapStyleId, string> = {
  street: 'Street',
  normal: 'Normal',
  satellite: 'Satellite',
}

/** OSM-style vector (Liberty). */
export const STREET_STYLE_URL = 'https://tiles.openfreemap.org/styles/liberty'

/** Light basemap. */
export const NORMAL_STYLE_URL = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'

/** Raster satellite (no API key; Esri world imagery). */
export const SATELLITE_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    satellite: {
      type: 'raster',
      tiles: [
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      ],
      tileSize: 256,
      attribution: '© Esri',
    },
  },
  layers: [
    {
      id: 'satellite',
      type: 'raster',
      source: 'satellite',
      minzoom: 0,
      maxzoom: 22,
    },
  ],
}

export function getStyleForMapStyleId(id: MapStyleId): string | StyleSpecification {
  switch (id) {
    case 'street':
      return STREET_STYLE_URL
    case 'normal':
      return NORMAL_STYLE_URL
    case 'satellite':
      return SATELLITE_STYLE
    default:
      return STREET_STYLE_URL
  }
}
