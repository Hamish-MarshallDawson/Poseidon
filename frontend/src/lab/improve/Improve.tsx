import { useMemo, useState } from 'react'
import { Band, Chart, Legend, Line, Markers, RefLine, Step as StepLine, extent, pad, timeFull, useChart, type Shape, type Tone } from '../charts'
import type { LabEvent, Metrics, Proposal, Run, Summary } from '../types'
import {
  BASELINE, MARKER_LABEL, championSteps, hoursLabel, liveSkill, markers, modelKey, offlineStatName, pct, recalLog,
  type EventLike, type LivePoint, type Marker, type MarkerKind, type MetricsLike, type ModelSummaryLike, type ProposalLike, type RecalEntry, type RunLike, type Step,
} from './shape'
import { liveComparison, offlineSkill } from '../skill'
import { signedPct } from '../format'
import './improve.css'

// "How it improved": per model, the champion's offline skill as a step line (one step per promotion or deployment,
// its interval as a band), the live skill on our feed over it, and markers for every promotion, rejection,
// recalibration, deployment and Gemini proposal. Below: the recalibration log.

export interface ImproveProps {
  summary: Summary
  runs: Run[]
  events: LabEvent[]
  metrics: Metrics | null
  proposals?: Proposal[]
}

const SHORT: Record<string, string> = { route: 'Route', godark: 'Go-dark', fishing: 'Fishing' }

export function Improve({ summary, runs, events, metrics, proposals = [] }: ImproveProps) {
  const models = summary.models.filter((m) => modelKey(m.target))
  const [sel, setSel] = useState(models[0]?.target ?? 'route')
  const model = models.find((m) => m.target === sel) ?? models[0]
  const recal = useMemo(() => recalLog(events), [events])
  if (!model) return <section className="lab-improve"><h2>How it improved</h2><p className="lab-improve__muted">No models yet.</p></section>

  return (
    <section className="lab-improve" aria-labelledby="lab-improve-title">
      <header className="lab-improve__head">
        <h3 id="lab-improve-title" className="lab-sr">Model</h3>
        <div role="tablist" aria-label="Model" className="lab-improve__tabs">
          {models.map((m) => (
            <button key={m.target} role="tab" type="button" aria-selected={m.target === model.target} onClick={() => setSel(m.target)}>
              {SHORT[m.target] ?? m.target}
            </button>
          ))}
        </div>
      </header>
      <ModelHistory key={model.target} model={model} runs={runs} events={events} metrics={metrics} proposals={proposals} now={summary.generated_at} />
      <RecalLog entries={recal} />
    </section>
  )
}

function ModelHistory({ model, runs, events, metrics, proposals, now }: { model: ModelSummaryLike; runs: RunLike[]; events: EventLike[]; metrics: MetricsLike | null; proposals: ProposalLike[]; now: number }) {
  const key = modelKey(model.target)!
  const steps = useMemo(() => championSteps(model, runs, events), [model, runs, events])
  const live = useMemo(() => liveSkill(model, metrics), [model, metrics])
  const marks = useMemo(() => markers(model, runs, events, proposals), [model, runs, events, proposals])
  const h = hoursLabel(model.offline.primary_h)
  const vs = BASELINE[key]
  // One statistic at one horizon on this chart: go-dark's held-out Brier skill (not its log-loss skill) under its live Brier skill.
  const stat = offlineStatName(model, runs)
  const offline = useMemo(() => offlineSkill(model, runs), [model, runs])

  const ts = [...steps.map((s) => s.t), ...marks.map((m) => m.t), ...live.live.map((p) => p.t), ...live.backtest.map((p) => p.t), now]
  const t0 = Math.min(...ts)
  const xDomain = pad([t0, Math.max(...ts)], 0.03) as [number, number]
  const ys = [0, ...steps.flatMap((s) => [s.value, s.lo, s.hi]), ...live.live.map((p) => p.value), ...live.backtest.map((p) => p.value)]
  const yDomain = pad(extent(ys, [0, 1]), 0.12) as [number, number]
  const hasValues = steps.some((s) => s.value != null) || live.live.length > 0 || live.backtest.length > 0
  const lastLive = live.live[live.live.length - 1]
  const stepPts = steps.map((st) => ({ x: st.t, y: st.value, s: st }))
  const band = steps.map((st) => ({ x: st.t, lo: st.lo, hi: st.hi }))
  const livePrimary = model.live?.primary
  // Live against held-out only on one statistic at one horizon: the backend's live.offline (go-dark: Brier skill at 1 h).
  const cmp = liveComparison(model, runs)
  const below = cmp?.live && cmp.offline && cmp.live.skill < cmp.offline.skill ? cmp : null

  return (
    <div className="lab-improve__model">
      <p className="lab-improve__lede">
        Champion <b>{model.champion.version}</b>:{' '}
        {offline != null
          ? <>{offline.name} <b>{pct(offline.skill)}</b>{offline.lo != null && offline.hi != null && <> ({pct(offline.lo)} to {pct(offline.hi)})</>} over {vs} at {h} on the held-out set{model.offline.holdout ? ` (${model.offline.holdout})` : ''}.</>
          : <>no offline {stat} on a held-out set yet.</>}
        {' '}{livePrimary?.value != null
          ? <>Live on our feed, last {model.live?.hours ?? 24} h: <b>{pct(livePrimary.value)}</b> {livePrimary.name}{model.live?.n ? ` (${model.live.n.toLocaleString('en-GB')} graded)` : ''}.</>
          : !model.live && model.deployed ? 'No live grades for this version yet.'
            : lastLive ? <>Live on our feed, last hour: <b>{pct(lastLive.value)}</b> ({lastLive.n.toLocaleString('en-GB')} graded).</>
              : key === 'fishing' || !model.live ? 'Not graded on our live feed yet.' : 'No live grades at this horizon yet.'}
      </p>
      {hasValues || marks.length ? (
        <Chart label={`${SHORT[key]} champion ${stat} over ${vs} at ${h}, offline and live, with model events`} x={{ type: 'time', domain: xDomain }} y={{ domain: yDomain, percent: true, label: `${stat} over ${vs} at ${h}` }} height={240} margin={{ top: 18 }}>
          <RefLine y={0} label={`no better than ${vs}`} />
          <Band data={band} step until={xDomain[1]} tone="ink" />
          <StepLine data={stepPts} until={xDomain[1]} tone="ink" label="champion skill on the held-out set" tip={(d) => stepTip(d.s, stat, vs, h)} />
          <Line data={live.backtest.map(xy)} tone="muted" dashed dots label="backtest replay" tip={(d) => pointTip(d, `backtest replay, ${live.name}`)} />
          <Line data={live.live.map(xy)} tone="accent" dots label="live on our feed" tip={(d) => pointTip(d, `live, ${live.name}`)} />
          <EventRail marks={marks} />
        </Chart>
      ) : <p className="lab-improve__muted">Nothing recorded for this model yet.</p>}
      <Legend items={[
        ...(stepPts.some((p) => p.y != null) ? [{ label: 'champion, held-out set', tone: 'ink' as const }] : []),
        ...(band.some((b) => b.lo != null) ? [{ label: '95% interval', tone: 'ink' as const, kind: 'band' as const }] : []),
        ...(live.live.length ? [{ label: 'live, our feed', tone: 'accent' as const }] : []),
        ...(live.backtest.length ? [{ label: 'backtest replay', tone: 'muted' as const, kind: 'dashed' as const }] : []),
        ...[...new Set(marks.map((m) => m.kind))].map((k) => ({ label: MARKER_LABEL[k].toLowerCase(), tone: KIND[k].tone, kind: KIND[k].shape })),
      ]} />
      {below && (
        <p className="lab-improve__note">Live {below.live!.name} at {hoursLabel(below.live!.h)} ({signedPct(below.live!.skill)}) is below the held-out {below.offline!.name} at the same horizon ({signedPct(below.offline!.skill)}): our feed is not the held-out set, so we show both.</p>
      )}
    </div>
  )
}

const xy = (p: LivePoint) => ({ x: p.t, y: p.value, p })

const pointTip = (d: { p: LivePoint }, name: string) => <><b>{pct(d.p.value)}</b> {name}<br />{timeFull(d.p.t)} · {d.p.n.toLocaleString('en-GB')} graded</>
const stepTip = (s: Step, stat: string, vs: string, h: string) => (
  <><b>{s.version}</b><br />{s.how === 'current' ? 'current champion' : s.how} {timeFull(s.t)}<br />{stat} {pct(s.value)} over {vs} at {h}{s.lo != null && s.hi != null ? ` (${pct(s.lo)} to ${pct(s.hi)})` : ''}</>
)

const KIND: Record<MarkerKind, { shape: Shape; tone: Tone }> = {
  promoted: { shape: 'triangle', tone: 'good' },
  rejected: { shape: 'cross', tone: 'bad' },
  recalibrated: { shape: 'diamond', tone: 'muted' },
  deployed: { shape: 'square', tone: 'ink' },
  proposal: { shape: 'circle', tone: 'warn' },
}

/** Markers on the event rail. Markers closer than 10 px merge into one whose tooltip lists them all, so none hides another. */
function EventRail({ marks }: { marks: Marker[] }) {
  const { X } = useChart()
  const groups: { x: number; ms: Marker[] }[] = []
  for (const m of marks) {
    const g = groups[groups.length - 1]
    if (g && X(m.t) - X(g.ms[g.ms.length - 1].t) < 10) g.ms.push(m)
    else groups.push({ x: m.t, ms: [m] })
  }
  const data = groups.map((g) => ({ x: g.x, ms: g.ms, shape: KIND[g.ms[0].kind].shape, tone: KIND[g.ms[0].kind].tone, size: g.ms.length > 1 ? 5 : 4 }))
  return <Markers data={data} label="model event" tip={(d) => d.ms.map((m, i) => <MarkTip key={i} m={m} first={i === 0} />)} />
}

function MarkTip({ m, first }: { m: Marker; first: boolean }) {
  return (
    <div className={first ? undefined : 'lab-improve__tip-more'}>
      <b>{m.title}</b><br />{timeFull(m.t)}{m.target !== modelKey(m.target) ? ` · ${m.target}` : ''}
      {m.changed && <><br />Changed: {m.changed}</>}
      {m.why && <><br />Why: {m.why}</>}
    </div>
  )
}

function RecalLog({ entries }: { entries: RecalEntry[] }) {
  return (
    <div className="lab-improve__recal">
      <h3>Recalibration log</h3>
      <p className="lab-improve__muted">Each recalibration refits the champion's probabilities or circles on graded live outcomes; a change is kept only if it helps on the newer half of the data.</p>
      {!entries.length ? <p className="lab-improve__muted">No recalibrations yet.</p> : (
        <ol>
          {entries.map((e) => (
            <li key={`${e.target}-${e.t}`}>
              <div className="lab-improve__recal-head">
                <span className="lab-improve__chip" data-kept={e.kept === false ? 'no' : 'yes'}>{e.kept === false ? 'rejected' : 'kept'}</span>
                <b>{e.version || e.target}</b>
                <span className="lab-improve__muted">{timeFull(e.t)}</span>
              </div>
              {e.label && <p>{e.label}</p>}
              {e.factors.length > 0 && (
                <ul className="lab-improve__factors">
                  {e.factors.map((f) => (
                    <li key={f.name} data-kept={f.kept ? 'yes' : 'no'}>
                      <span>{f.name}</span><span>{f.value}</span><span>{f.kept ? 'kept' : `rejected${f.why ? `: ${f.why}` : ''}`}</span>
                    </li>
                  ))}
                </ul>
              )}
              {(e.before || e.after) && <p className="lab-improve__cov">Before: {e.before ?? '–'}<br />After: {e.after ?? '–'}</p>}
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
