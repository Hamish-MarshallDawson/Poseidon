import { useState } from 'react'
import { Button } from '../../ui'
import { collab } from '../store'
import type { Briefing } from '../../briefing/store'
import { saveBriefing } from './store'

// "Save to session" under a Brief me result (one ship or several, from the ship window, the Review list or the shared list).
// Shown only inside a session. It keeps the text of this briefing as a session document that lists the ships it covers.
export function SaveToSession({ briefing }: { briefing: Briefing }) {
  const inSession = collab.use((s) => s.session !== null)
  const [state, setState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  if (!inSession) return null
  const save = async () => {
    setState('saving')
    try { await saveBriefing(briefing); setState('saved') } catch { setState('error') }
  }
  return (
    <>
      <Button disabled={state === 'saving' || state === 'saved'} onClick={() => void save()}>
        {state === 'saving' ? 'Saving…' : state === 'saved' ? 'Saved to session' : 'Save to session'}
      </Button>
      {state === 'error' && <span className="br-note" role="alert">Could not save. Try again.</span>}
    </>
  )
}
