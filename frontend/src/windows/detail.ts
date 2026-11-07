import { createStore } from '../store/store'
import type { ClientMsg, ServerMsg } from '../types'

// The `detail` reply per ship (statics, gap history, sanction, full RiskScore), for the ship card.
// Wiring at composition: bindDetailSender((m) => adapter.send(m)) and FeedHandlers.onDetail = receiveDetail.
export type DetailMsg = Extract<ServerMsg, { type: 'detail' }>
export const details = createStore<{ byMmsi: Record<number, DetailMsg> }>({ byMmsi: {} })

let send: ((msg: ClientMsg) => void) | null = null
const asked = new Set<number>()

export function bindDetailSender(fn: ((msg: ClientMsg) => void) | null): void {
  send = fn
  if (fn) for (const mmsi of asked) fn({ type: 'detail', mmsi })   // ask again for windows opened before the feed was up
}

export function requestDetail(mmsi: number): void {
  asked.add(mmsi)
  send?.({ type: 'detail', mmsi })
}

export function receiveDetail(msg: DetailMsg): void {
  details.set((s) => ({ byMmsi: { ...s.byMmsi, [msg.mmsi]: msg } }))
}
