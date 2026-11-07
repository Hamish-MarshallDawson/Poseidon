import { nextWindowLetter, ui } from '../store/ui'

// Map-side actions on the shared ui store. The windows agent owns window placement and the focus UI; these are
// the minimal versions the map needs so a click does something sensible on its own.

const WIN_W = 320, WIN_H = 240, GAP = 24

/** Open (or bring to front) the ship window for `mmsi`. `at` is the ship's screen position in CSS px. */
export function openShipWindow(mmsi: number, at?: { x: number; y: number }): void {
  ui.set((s) => {
    const z = s.windows.reduce((m, w) => Math.max(m, w.z), 0) + 1
    if (s.windows.some((w) => w.mmsi === mmsi)) {
      return { frontMmsi: mmsi, windows: s.windows.map((w) => (w.mmsi === mmsi ? { ...w, z, minimised: false } : w)) }
    }
    const vw = window.innerWidth, vh = window.innerHeight
    // Default: to the right of the ship, flipped left near the right edge, clamped into the viewport.
    let x = at ? at.x + GAP : vw - WIN_W - GAP, y = at ? at.y - WIN_H / 2 : GAP + s.windows.length * 28
    if (x + WIN_W > vw - 8) x = (at?.x ?? vw) - GAP - WIN_W
    x = Math.max(8, Math.min(vw - WIN_W - 8, x)); y = Math.max(8, Math.min(vh - WIN_H - 8, y))
    return { frontMmsi: mmsi, windows: [...s.windows, { mmsi, letter: nextWindowLetter(s.windows), minimised: false, x, y, z }] }
  })
}

export function setFocus(mmsi: number | null): void {
  ui.set({ focusMmsi: mmsi, ...(mmsi == null ? { focusRelated: [] } : {}) })
}
