import { useMemo, useState } from 'react'
import { Chart, Legend, Line, Markers, extent, pad } from '../charts'
import type { ChampionsTabProps as BaseProps } from '../tabs'
import { fmtWhen, proposerLabel, STATUS_LABEL, type RunRecord } from '../runs/shape'
import { championLine, decisionSentence, latestDecided, measureFor, proposalRows, targetOf, timelinePoints, type Point } from './shape'
import { RunPanel } from './RunPanel'
import './champions.css'

/** The nav contract's props (tabs.ts), plus an optional "now" for the champion line's right end. */
export type ChampionsTabProps = BaseProps & { now?: number }

/** Every run of one model on a timeline (champions joined by a line), the latest decision in one sentence, the
 *  proposals Gemini made, and a side panel with any run's full story. */
export function ChampionsTab({ model, runs, proposals, loadDetail, now }: ChampionsTabProps) {
  const target = targetOf(model)
  const all = useMemo(() => (runs ?? []) as unknown as RunRecord[], [runs])
  const byId = useMemo(() => new Map(all.map((r) => [r.run_id, r])), [all])
  const points = useMemo(() => timelinePoints(all, target), [all, target])
  const latest = useMemo(() => latestDecided(all, target), [all, target])
  const rows = useMemo(() => proposalRows(proposals ?? [], target), [proposals, target])
  const [open, setOpen] = useState<string | null>(null)
  const openRun = open ? byId.get(open) : undefined

  if (runs == null) return <p className="lc-muted" role="status">Loading runs…</p>
  if (!points.length) return <p className="lc-muted">No training runs for this model yet.</p>

  const champ = points.filter((p) => p.run.status === 'champion').pop()
  const gemini = points.filter((p) => p.gemini).length
  const rejected = points.filter((p) => p.kind === 'rejected').length

  return (
    <div className="lc">
      <div className="lc-top">
        {latest && (
          <section className="lc-card lc-latest" aria-label="Latest decision">
            <span className="lc-kicker">Latest decision · {fmtWhen(latest.created_at)}</span>
            <p className="lc-sentence">{latest.proposer === 'gemini' && <GeminiBadge />}{decisionSentence(latest, byId)}</p>
            <button type="button" className="lc-link" onClick={() => setOpen(latest.run_id)}>See why →</button>
          </section>
        )}
        <section className="lc-card lc-stats" aria-label="Runs in numbers">
          <div><b>{points.length}</b><span>runs</span></div>
          <div><b>{points.filter((p) => p.run.status === 'champion' || p.run.status === 'retired').length}</b><span>became champion</span></div>
          <div><b>{rejected}</b><span>rejected</span></div>
          <div><b>{gemini}</b><span>by Gemini</span></div>
        </section>
      </div>

      <section className="lc-card" aria-label="Timeline of runs">
        <h3 className="lc-h">Every run, and the champion over time</h3>
        <Timeline points={points} target={target} now={now ?? Date.now()} onOpen={setOpen} />
        <p className="lc-caption">
          {champ ? <>Champion now: <button type="button" className="lc-link lc-mono" onClick={() => setOpen(champ.run.run_id)}>{champ.run.run_id}</button>. </> : 'No champion yet. '}
          Click a dot for the run's story.
        </p>
        <RunList points={points} onOpen={setOpen} openId={open} />
      </section>

      <section className="lc-card" aria-labelledby="lc-props-h">
        <h3 className="lc-h" id="lc-props-h">Proposals <span className="lc-muted">{rows.length ? `${rows.length} · ${rows.filter((r) => r.kind === 'valid').length} trained` : ''}</span></h3>
        {!rows.length ? (
          <p className="lc-muted">No proposals yet: Gemini proposes after the next training cycle.</p>
        ) : (
          <ul className="lc-props">
            {rows.map(({ p, kind, change, reason, outcome }) => (
              <li key={p.id} data-kind={kind}>
                <span className={`lc-pill lc-pill--${kind}`}>{kind}</span>
                <div className="lc-prop-main">
                  <span>{p.proposer === 'gemini' && <GeminiBadge />}<span className="lc-mono">{change}</span></span>
                  {reason && <span className="lc-muted">{reason}</span>}
                </div>
                <span className="lc-prop-side">
                  <span className="lc-muted">{fmtWhen(p.created_at)} · {outcome}</span>
                  {p.run_id && byId.has(p.run_id) && <button type="button" className="lc-link" onClick={() => setOpen(p.run_id)}>open run</button>}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {openRun && <RunPanel key={openRun.run_id} run={openRun} byId={byId} proposals={proposals ?? []} loadDetail={loadDetail} onClose={() => setOpen(null)} />}
    </div>
  )
}

export function GeminiBadge() {
  return <span className="lc-gemini" title="Proposed by Gemini">Gemini</span>
}

const TONE = { champion: 'accent', retired: 'accent', candidate: 'ink', rejected: 'muted' } as const

function Timeline({ points, target, now, onOpen }: { points: Point[]; target: string; now: number; onOpen: (id: string) => void }) {
  const m = measureFor(target)
  const ys = points.flatMap((p) => (p.y == null ? [] : [p.y]))
  if (!ys.length) return <p className="lc-muted">No run has a held-out score yet, so there is nothing to plot.</p>
  const xs = points.map((p) => p.x)
  const span = Math.max(3_600_000, Math.max(...xs, now) - Math.min(...xs))
  const xDomain: [number, number] = [Math.min(...xs) - span * 0.04, Math.max(...xs, now) + span * 0.02]
  const yDomain = pad(extent(m.lowerBetter ? ys : [0, ...ys]), 0.15)
  const line = championLine(points, now)
  const tip = (p: Point) => (
    <>
      <b>{p.run.run_id}</b><br />
      {STATUS_LABEL[p.run.status] ?? p.run.status} · {proposerLabel(p.run.proposer)} · {fmtWhen(p.x)}<br />
      {p.y == null ? 'no held-out score' : `${m.label.toLowerCase()}: ${m.fmt(p.y)}`}
    </>
  )
  const marks = points.map((p) => ({
    ...p,
    tone: TONE[p.kind],
    shape: p.gemini ? ('diamond' as const) : p.kind === 'rejected' ? ('cross' as const) : ('circle' as const),
    size: p.run.status === 'champion' ? 6 : 4.5,
  }))
  // The chart kit draws one hit circle per marker, in data order (Markers never skips one): its index is the run.
  const hit = (t: EventTarget) => {
    const el = (t as Element).closest?.('.lab-chart__hits > circle')
    const i = el?.parentElement ? Array.from(el.parentElement.children).indexOf(el) : -1
    if (i >= 0 && marks[i]) onOpen(marks[i].run.run_id)
  }
  return (
    <div className="lc-timeline" onClick={(e) => hit(e.target)} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') hit(e.target) }}>
      <Chart
        label={`${m.label} for every run of the ${target} model over time; champions joined by a line`}
        x={{ type: 'time', domain: xDomain, ticks: 5 }}
        y={{ domain: yDomain, format: m.fmt, ticks: 4, label: m.label }}
        height={220}
        className="lc-chart"
      >
        <Line data={line} tone="accent" label="champion" />
        <Markers data={marks} tip={tip} label="run" />
      </Chart>
      <Legend items={[
        { label: 'champion', tone: 'accent', kind: 'circle' },
        { label: 'rejected challenger', tone: 'muted', kind: 'cross' },
        { label: 'Gemini proposed', tone: 'ink', kind: 'diamond' },
      ]} />
      <p className="lc-caption">{m.lowerBetter ? 'Lower is better.' : 'Higher is better; 0% is no better than a simple guess.'}</p>
    </div>
  )
}

/** The same runs as buttons, newest first: the keyboard and small-screen way in, and a fallback for the chart. */
function RunList({ points, onOpen, openId }: { points: Point[]; onOpen: (id: string) => void; openId: string | null }) {
  const m = measureFor(points[0]?.run.target ?? '')
  return (
    <ul className="lc-runs" aria-label="Runs, newest first">
      {[...points].reverse().map((p) => (
        <li key={p.run.run_id}>
          <button type="button" className="lc-run" data-kind={p.kind} aria-pressed={openId === p.run.run_id} onClick={() => onOpen(p.run.run_id)}>
            <i aria-hidden />
            <span className="lc-mono">{p.run.run_id}</span>
            {p.gemini && <GeminiBadge />}
            <span className="lc-muted">{STATUS_LABEL[p.run.status] ?? p.run.status}</span>
            <b className="lc-mono">{p.y == null ? '—' : m.fmt(p.y)}</b>
          </button>
        </li>
      ))}
    </ul>
  )
}
