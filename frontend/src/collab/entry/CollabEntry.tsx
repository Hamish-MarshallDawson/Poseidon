import { useEffect } from 'react'
import { acceptInviteToken, collab, openSession } from '../store'
import { entry, showJoined } from './state'
import './entry.css'

// Mounted once in the logged-in app: the ?invite=<token> link flow, the one entry pop-up, and the joined toast.
// The session bar and the Invite / Join panel live in the toolbar (SessionBar.tsx).

/** The invite link: accept once logged in, drop the token from the address bar either way. */
function useInviteLink(ready: boolean) {
  useEffect(() => {
    if (!ready) return
    const token = new URLSearchParams(location.search).get('invite')
    if (!token) return
    const u = new URL(location.href); u.searchParams.delete('invite'); history.replaceState(null, '', u)
    entry.set({ popupDone: true })                    // an invite link replaces the pop-up
    void acceptInviteToken(token).then((s) => { if (s) showJoined(s) })
  }, [ready])
}

export function CollabEntry() {
  const me = collab.use((s) => s.me)
  useInviteLink(!!me)
  return <><EntryPopup /><JoinedToast /></>
}

function names(list: { name: string | null }[]): string {
  const n = list.map((u) => u.name ?? 'Someone')
  return n.length > 1 ? `${n.slice(0, -1).join(', ')} and ${n[n.length - 1]}` : n[0]
}

/** Once per login, only when there is something to join or resume; nothing otherwise. */
function EntryPopup() {
  const me = collab.use((s) => s.me)
  const inSession = collab.use((s) => s.session !== null)
  const row = collab.use((s) => s.sessions[0] ?? null)
  const done = entry.use((s) => s.popupDone)
  const shown = !!me && !inSession && !!row && !done
  useEffect(() => {
    if (!shown) return
    const close = () => entry.set({ popupDone: true })
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') close() }
    const click = (e: PointerEvent) => { if (!(e.target as Element).closest('.entry-popup')) close() }   // a click on the map
    window.addEventListener('keydown', key); window.addEventListener('pointerdown', click, true)
    return () => { window.removeEventListener('keydown', key); window.removeEventListener('pointerdown', click, true) }
  }, [shown])
  if (!shown || !row) return null
  const join = async () => { entry.set({ popupDone: true }); const s = await openSession(row.id); if (s) showJoined(s) }
  return (
    <div className="panel entry-popup" role="dialog" aria-label="Session" data-zone>
      <p>{row.online.length
        ? <>{names(row.online)} {row.online.length > 1 ? 'are' : 'is'} in <em>{row.title}</em></>
        : <>Resume <em>{row.title}</em>?</>}</p>
      <div className="entry-popup__actions">
        <button type="button" className="chip on" onClick={join} autoFocus>{row.online.length ? 'Join' : 'Resume'}</button>
        <button type="button" className="chip" onClick={() => entry.set({ popupDone: true })}>Just the map</button>
      </div>
    </div>
  )
}

function JoinedToast() {
  const t = entry.use((s) => s.toast)
  if (!t) return null
  return (
    <div className="panel entry-toast" role="status">
      You have joined <em>{t[0]}</em>{t[1] ? ` with ${t[1]}` : ''}
    </div>
  )
}
