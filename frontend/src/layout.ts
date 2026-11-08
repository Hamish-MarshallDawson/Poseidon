// The one layout rule for everything floating over the map. Import-free so node can run place.check.ts on it.
//
//   top-left      status line (y 16), the focus bar under it (y 50)
//   top-right     toolbar (y 16): Review, Layers, Log out
//                 map controls row (y 54): Display and the zoom +/-, always visible
//                 right column (y 92): the one open panel (Review, Layers), 360 wide, never over the controls
//   bottom        the scrub bar, centred, 48 px high
//   bottom-left   Legend toggle on the scrub bar's row; Legend or the AI briefing above it. They share the column:
//                 opening the briefing closes the legend and disables its toggle.
//   bottom-right  scale and map attribution
//   phone (<=720) status line alone on the first row, toolbar under it, controls and panels below; the scrub bar goes
//                 full width and the legend toggle moves above it
//
// Ship windows live in the free area: the viewport between TOP and BOTTOM, minus the boxes of every element tagged
// `data-zone` (toolbar, controls, right panel, focus bar, legend, briefing). The CSS custom properties that
// panels.css reads (--lay-*) must equal the numbers below; place.check.ts verifies it.

export const INSET = 16        // from every screen edge
export const GAP = 8
export const TOP = 56          // windows never go above this (the status line and toolbar band)
export const BOTTOM = 72       // nor below viewport height minus this (scrub bar 48 + 16 inset + 8 gap)
export const CONTROLS_TOP = 54 // Display and zoom row
export const PANEL_TOP = 92    // top of the right-column panels
export const PANEL_W = 360
