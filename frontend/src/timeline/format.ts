// UTC with Z everywhere (timeline report). Behind-live rounds down to whole minutes.
const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const p2 = (n: number) => String(n).padStart(2, '0')

export const fmtTime = (t: number) => new Date(t).toISOString().slice(11, 19) + 'Z'
export const fmtHM = (t: number) => new Date(t).toISOString().slice(11, 16) + 'Z'
export function fmtDay(t: number): string {
  const d = new Date(t)
  return `${DAYS[d.getUTCDay()]} ${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`
}
export function fmtBehind(ms: number): string {
  const m = Math.floor(Math.max(0, ms) / 60_000)
  if (m < 60) return `−${m} min`
  const h = Math.floor(m / 60)
  return h < 48 ? `−${h} h ${p2(m % 60)} min` : `−${Math.floor(h / 24)} d ${h % 24} h`
}
export function fmtDuration(ms: number): string {
  const m = Math.floor(Math.max(0, ms) / 60_000)
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${p2(m % 60)} min`
}
export function fmtSpan(ms: number): string {
  const m = Math.round(ms / 60_000)
  if (m < 60) return `${m} min`
  const h = Math.round(m / 60)
  return h < 48 ? `${h} h` : `${Math.round(h / 24)} d`
}
