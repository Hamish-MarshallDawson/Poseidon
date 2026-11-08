// Pure presence logic, import-free so node can run logic.check.ts on it.

export type Status = 'open' | 'reviewed' | 'no_action'
export type Bbox = [number, number, number, number]

export interface PresenceUser {
  id: string; name: string | null; picture: string | null
  viewing: number | null; following: number[]; bbox: Bbox | null; ts: number
}

export interface PresenceOut { viewing: number | null; following: number[]; bbox: Bbox | null; private: boolean }

export const STATUS_LABEL: Record<Status | 'report', string> = {
  open: 'Open', reviewed: 'Reviewed', no_action: 'No action', report: 'Report generated',
}
export const STATUS_ORDER: Status[] = ['open', 'reviewed', 'no_action']

export const SEND_EVERY_MS = 2000     // while something changes
export const HEARTBEAT_MS = 8000      // the server drops a user silent for 30 s; it asks for at least every 10 s

const sameBbox = (a: Bbox | null, b: Bbox | null) =>
  a === b || (!!a && !!b && a.every((v, i) => Math.abs(v - b[i]) < 1e-3))
export const samePresence = (a: PresenceOut, b: PresenceOut) =>
  a.viewing === b.viewing && a.private === b.private && sameBbox(a.bbox, b.bbox) &&
  a.following.length === b.following.length && a.following.every((m, i) => m === b.following[i])

/** True when `next` should go out now: a change after the 2 s throttle, or the heartbeat is due. */
export function shouldSend(last: PresenceOut | null, lastAt: number, next: PresenceOut, now: number): boolean {
  if (!last) return true
  if (now - lastAt >= HEARTBEAT_MS) return true
  return now - lastAt >= SEND_EVERY_MS && !samePresence(last, next)
}

/** Teammates (not me) grouped by the ship they are viewing. */
export function viewersByShip(users: PresenceUser[], meId: string | null): Map<number, PresenceUser[]> {
  const out = new Map<number, PresenceUser[]>()
  for (const u of users) {
    if (u.id === meId || u.viewing == null) continue
    const a = out.get(u.viewing)
    if (a) a.push(u); else out.set(u.viewing, [u])
  }
  return out
}

const first = (n: string | null | undefined) => (n?.trim().split(/\s+/)[0]) || 'Someone'

/** "Aiden and Jake are viewing", "Aiden, Jake and Mano are viewing", "Aiden, Jake and 2 others are viewing". */
export function viewerText(users: { name: string | null }[], verb = 'viewing'): string {
  const n = users.map((u) => first(u.name))
  if (n.length === 0) return ''
  const be = n.length === 1 ? 'is' : 'are'
  const list = n.length === 1 ? n[0] : n.length === 2 ? `${n[0]} and ${n[1]}` : n.length === 3 ? `${n[0]}, ${n[1]} and ${n[2]}`
    : `${n[0]}, ${n[1]} and ${n.length - 2} others`
  return `${list} ${be} ${verb}`
}

export function trackedText(names: (string | null)[]): string {
  const n = names.map(first)
  return n.length === 0 ? '' : `Tracked by ${n.length <= 3 ? n.join(', ') : `${n.slice(0, 2).join(', ')} and ${n.length - 2} others`}`
}

export function initials(name: string | null | undefined): string {
  const p = (name ?? '').trim().split(/\s+/).filter(Boolean)
  return p.length === 0 ? '?' : (p[0][0] + (p.length > 1 ? p[p.length - 1][0] : '')).toUpperCase()
}

export const RING_COLOURS = 6
/** A stable ring colour index (0..5) per user id. */
export function ringIndex(id: string): number {
  let h = 0
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0
  return h % RING_COLOURS
}

/** Only https avatars are drawn; anything else falls back to initials (the server also checks, but never trust it). */
export const safePicture = (p: string | null | undefined) => (p && /^https:\/\//i.test(p) ? p : null)

/** Screen offsets so several avatars on one ship fan out instead of stacking: a small arc above the ship. */
export function fanOffsets(n: number, r = 16): { x: number; y: number }[] {
  if (n <= 1) return [{ x: 0, y: -r - 6 }]
  const out: { x: number; y: number }[] = []
  const span = Math.min(Math.PI * 0.9, 0.55 * n)
  for (let i = 0; i < n; i++) {
    const a = -Math.PI / 2 - span / 2 + (span * i) / (n - 1)
    out.push({ x: Math.round(Math.cos(a) * (r + 8)), y: Math.round(Math.sin(a) * (r + 8)) })
  }
  return out
}

export function activityText(kind: string, who: string): string {
  switch (kind) {
    case 'created': return `${who} started the session`
    case 'joined': return `${who} joined`
    case 'added': return `${who} added a ship`
    case 'removed': return `${who} removed a ship`
    case 'status_open': return `${who} marked a ship open`
    case 'status_reviewed': return `${who} marked a ship reviewed`
    case 'status_no_action': return `${who} marked a ship no action`
    case 'noted': return `${who} added a note`
    default: return `${who} did something`
  }
}

export function ago(ms: number, now: number): string {
  const s = Math.max(0, Math.round((now - ms) / 1000))
  return s < 60 ? 'just now' : s < 3600 ? `${Math.round(s / 60)} min ago` : s < 86400 ? `${Math.round(s / 3600)} h ago` : `${Math.round(s / 86400)} d ago`
}
