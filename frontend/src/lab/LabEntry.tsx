import { Component, lazy, Suspense, useEffect, type ErrorInfo, type ReactNode } from 'react'
import { bindLabAuth } from './api'
import { closeLab, openLab, useLabOpen } from './hash'

// The Lab's two entry points: <LabChip> in the map toolbar, and <LabRoot> (mounted once in App's Monitor) that
// opens the full-screen Lab while the URL hash is #lab. No router: the hash is the state, so Back and links work.

const Lab = lazy(() => import('./Lab').then((m) => ({ default: m.Lab })))

export function LabRoot({ getToken }: { getToken: () => Promise<string | undefined> }) {
  useEffect(() => { bindLabAuth(getToken); return () => bindLabAuth(null) }, [getToken])
  const open = useLabOpen()
  if (!open) return null
  return <LabBoundary onClose={closeLab}><Suspense fallback={null}><Lab onClose={closeLab} /></Suspense></LabBoundary>
}

/** Keeps a Lab error (a bad record, a failed chunk load) inside the Lab: the map under it stays mounted. Closing and
 *  reopening the Lab mounts a fresh boundary, so it retries. */
export class LabBoundary extends Component<{ onClose: () => void; children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null }
  static getDerivedStateFromError(error: Error) { return { error } }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error('Model Lab error', error, info.componentStack) }
  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="lab" role="dialog" aria-modal="true" aria-labelledby="lab-error-title">
        <header className="lab-head">
          <div className="lab-head__title">
            <h1 id="lab-error-title">Model Lab</h1>
            <p role="alert">The Model Lab hit an error and could not be shown. The map is unaffected; close the Lab and open it again to retry.</p>
          </div>
          <div className="lab-head__meta">
            <button type="button" className="lab-close" onClick={this.props.onClose} aria-label="Close the Model Lab and return to the map">
              <span aria-hidden>×</span> Map
            </button>
          </div>
        </header>
      </div>
    )
  }
}

export function LabChip() {
  const open = useLabOpen()
  return (
    <button type="button" className={`chip ${open ? 'on' : ''}`} aria-haspopup="dialog" onClick={openLab}>
      <span className="chip-square" aria-hidden />Model Lab
    </button>
  )
}
