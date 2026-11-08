import { lazy, Suspense, useEffect } from 'react'
import { bindLabAuth } from './api'
import { closeLab, openLab, useLabOpen } from './hash'

// The Lab's two entry points: <LabChip> in the map toolbar, and <LabRoot> (mounted once in App's Monitor) that
// opens the full-screen Lab while the URL hash is #lab. No router: the hash is the state, so Back and links work.

const Lab = lazy(() => import('./Lab').then((m) => ({ default: m.Lab })))

export function LabRoot({ getToken }: { getToken: () => Promise<string | undefined> }) {
  useEffect(() => { bindLabAuth(getToken); return () => bindLabAuth(null) }, [getToken])
  const open = useLabOpen()
  if (!open) return null
  return <Suspense fallback={null}><Lab onClose={closeLab} /></Suspense>
}

export function LabChip() {
  const open = useLabOpen()
  return (
    <button type="button" className={`chip ${open ? 'on' : ''}`} aria-haspopup="dialog" onClick={openLab}>
      <span className="chip-square" aria-hidden />Model Lab
    </button>
  )
}
