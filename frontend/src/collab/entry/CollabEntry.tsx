import { useEffect } from 'react'
import { acceptInviteToken, collab, openSession } from '../store'
import { entry, forgetSession, rememberedSession, showJoined, takeInvite } from './state'
import './entry.css'

// Mounted once in the logged-in app: the ?invite=<token> link flow, putting a reloaded tab back in its session, the one
// entry pop-up, and the joined toast. The session bar and the Invite / Join panel live in the toolbar (SessionBar.tsx).

/** Once logged in: accept an invite link (dropped from the address bar either way), else return to this tab's session, silently. */
function useEntry(me: string | undefined) {
  useEffect(() => {
    if (!me) return
    const token = takeInvite(), back = rememberedSession(me)
    if (!token && !back) return
    entry.set({ popupDone: true })                    // both replace the pop-up
    void (async () => {
      const joined = token ? await acceptInviteToken(token) : null
      if (joined) showJoined(joined)
      else if (back && !(await openSession(back))) forgetSession(me)
    })()
  }, [me])
}

export function CollabEntry() {
  useEntry(collab.use((s) => s.me?.id))
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
  const row = collab.use((s) => s.sessions.find((x) => x.online.length) ?? s.sessions[0] ?? null)   // a session with people in it first
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
  const n = entry.use((s) => s.notice)
  if (n) return <div className={`panel entry-toast ${n.bad ? 'bad' : ''}`} role={n.bad ? 'alert' : 'status'}>{n.text}</div>
  if (!t) return null
  return (
    <div className="panel entry-toast" role="status">
      You have joined <em>{t[0]}</em>{t[1] ? ` with ${t[1]}` : ''}
    </div>
  )
}
