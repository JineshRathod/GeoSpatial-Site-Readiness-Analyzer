/**
 * Shared desktop geometry for Controls (left) and Insights (right) columns.
 * `top-*` clears the floating header (search + pills) so panels never sit under the navbar.
 */
export const SIDE_PANEL_TOP = 'top-28'
/** Reserved top ≈7rem header + small gap — keeps panels just under the unified navbar. */
export const SIDE_PANEL_HEIGHT = 'h-[calc(100vh-8rem)]'
export const SIDE_PANEL_WIDTH = 'w-[min(92vw,360px)]'

export const sidePanelAsideClasses = `${SIDE_PANEL_TOP} ${SIDE_PANEL_HEIGHT} ${SIDE_PANEL_WIDTH}`
