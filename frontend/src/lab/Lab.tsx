import { useCallback, useEffect, useRef } from 'react'
import { lab, offline } from './api'
import { useLab } from './useLab'
import { Home } from './home/Home'
import { ModelPage } from './ModelPage'
import { MODEL_INFO } from './model'
import { openLab, useLabRoute } from './hash'
import { when } from './format'
import './lab.css'

// The Model Lab: a full-screen view over the map. #lab is the home (totals and three model cards); #lab/<model>[/<tab>]
// a model page. Escape on a model page returns home; on home it closes the Lab. Reloads every minute while open.

export function Lab({ onClose }: { onClose: () => void }) {
  const state = useLab()
  const route = useLabRoute()
  const closeRef = useRef<HTMLButtonElement>(null)
  const modelRef = useRef(route.model)
  useEffect(() => { modelRef.current = route.model }, [route.model])
  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || e.defaultPrevented) return
      if (modelRef.current) openLab()
      else onClose()
    }
    window.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { window.removeEventListener('keydown', onKey); document.body.style.overflow = prev }
  }, [onClose])
  const bodyRef = useRef<HTMLDivElement>(null)
  useEffect(() => { bodyRef.current?.scrollTo?.({ top: 0 }) }, [route.model])
  const loadDetail = useCallback(async (id: string) => (await lab.run(id)).value, [])
  return (
    <div ref={bodyRef} className="lab" role="dialog" aria-modal="true" aria-labelledby="lab-title">
      <header className="lab-head">
        <nav className="lab-head__title" aria-label="Model Lab">
          <h1 id="lab-title">
            {route.model
              ? <><a href="#lab" className="lab-crumb">Model Lab</a> <span aria-hidden>/</span> {MODEL_INFO[route.model].name}</>
              : 'Model Lab'}
          </h1>
          {!route.model && <p>Three models that learn from our own feed. Each new version must beat the current one on a frozen test before it goes live.</p>}
        </nav>
        <div className="lab-head__meta">
          {state.sample && <span className="lab-tag" role="status" title={state.errors.join('\n') || undefined}>{offline() ? 'Sample data' : 'Server unreachable: sample data'}</span>}
          {state.summary && <span className="lab-muted">Updated {when(state.sample ? state.summary.generated_at : state.now)}</span>}
          <button ref={closeRef} type="button" className="lab-close" onClick={onClose} aria-label="Close the Model Lab and return to the map">
            <span aria-hidden>×</span> Map
          </button>
        </div>
      </header>
      <main className="lab-body">
        {route.model
          ? <ModelPage target={route.model} tab={route.tab} summary={state.summary} runs={state.runs} proposals={state.proposals}
              events={state.events} metrics={state.metrics} data={state.data} loadDetail={loadDetail} />
          : <Home summary={state.summary} runs={state.runs} proposals={state.proposals} metrics={state.metrics} />}
      </main>
    </div>
  )
}
