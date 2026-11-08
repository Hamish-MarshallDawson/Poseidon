import { useEffect, useRef } from 'react'
import { lab } from './api'
import { HOURS, useLab } from './useLab'
import { Overview } from './Overview'
import { Improve } from './improve'
import { Live } from './live'
import { Runs } from './runs'
import type { LabSectionProps } from './sections'
import { when } from './format'
import './lab.css'

// The Model Lab: a full-screen view over the map (#lab). Overview cards on top, then three sections that other agents
// fill (improve/, live/, runs/), each given LabSectionProps. Reloads every minute while open.



export function Lab({ onClose }: { onClose: () => void }) {
  const state = useLab()
  const closeRef = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape' && !e.defaultPrevented) onClose() }
    window.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { window.removeEventListener('keydown', onKey); document.body.style.overflow = prev }
  }, [onClose])
  const props: LabSectionProps = { ...state, hours: HOURS, api: lab }
  return (
    <div className="lab" role="dialog" aria-modal="true" aria-labelledby="lab-title">
      <header className="lab-head">
        <div className="lab-head__title">
          <h1 id="lab-title">Model Lab</h1>
          <p>How our three models are trained, tested against a frozen held-out set, promoted only when they beat the champion, and how they do live on our own feed.</p>
        </div>
        <div className="lab-head__meta">
          {state.sample && <span className="lab-tag" title={state.errors.join('\n') || undefined}>Sample data</span>}
          {state.summary && <span className="lab-muted">Updated {when(state.sample ? state.summary.generated_at : state.now)}</span>}
          <button ref={closeRef} type="button" className="lab-close" onClick={onClose} aria-label="Close the Model Lab and return to the map">
            <span aria-hidden>×</span> Map
          </button>
        </div>
      </header>
      <main className="lab-body">
        <Overview summary={state.summary} />
        <Section id="improve" title="How it improved" lede="Each step is a promotion: a run that beat the champion on the frozen held-out set. Live results on our feed are drawn over it.">
          <Improve {...props} />
        </Section>
        <Section id="live" title="Live track record" lede="Every prediction we serve is graded when its horizon passes. These are those grades, against the baselines.">
          <Live {...props} />
        </Section>
        <Section id="runs" title="Runs and proposals" lede="Every training run with its config, data and evaluation, and why the promotion rule kept or rejected it.">
          <Runs {...props} />
        </Section>
      </main>
    </div>
  )
}

function Section({ id, title, lede, children }: { id: string; title: string; lede: string; children: React.ReactNode }) {
  return (
    <section className="lab-section" aria-labelledby={`lab-${id}`}>
      <h2 id={`lab-${id}`}>{title}</h2>
      <p className="lab-lede">{lede}</p>
      {children}
    </section>
  )
}
