import { onFrame, type SpringStyle } from '../motion'

// Shared between the windows (which move) and the leader overlay (which follows them).
export const windowGeom = new Map<number, { spring: SpringStyle; w: number; h: number }>()

let draw: (() => void) | null = null
export function setLeaderDraw(fn: (() => void) | null): void {
  draw = fn
}
let scheduled = false
export function scheduleLeader(): void {
  if (scheduled || !draw) return
  scheduled = true
  onFrame(() => {
    scheduled = false
    draw?.()
    return false
  })
}
