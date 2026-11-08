import { useMemo, useState } from 'react'
import { Chart, useChart } from '../charts/Chart'
import { extent, pad, timeFull } from '../charts/scale'
import {
  BASELINE, MARKER_LABEL, championSteps, hoursLabel, liveSkill, markers, modelKey, pct, recalLog,
  type EventLike, type LivePoint, type Marker, type MarkerKind, type MetricsLike, type ModelSummaryLike, type ProposalLike, type RecalEntry, type RunLike, type Step,
} from './shape'
import './improve.css'

// "How it improved": per model, the champion's offline skill as a step line (one step per promotion or deployment,
// its interval as a band), the live skill on our feed over it, and markers for every promotion, rejection,
// recalibration, deployment and Gemini proposal. Below: the recalibration log.

export interface ImproveProps {
  summary: { generated_at: number; models: ModelSummaryLike[] }
  runs: RunLike[]
  events: EventLike[]
  metrics: MetricsLike | null
  proposals?: ProposalLike[]
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
        <h2 id="lab-improve-title">How it improved</h2>
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

  const ts = [...steps.map((s) => s.t), ...marks.map((m) => m.t), ...live.live.map((p) => p.t), ...live.backtest.map((p) => p.t), now]
  const t0 = Math.min(...ts)
  const xDomain = pad([t0, Math.max(...ts)], 0.03) as [number, number]
  const ys = [0, ...steps.flatMap((s) => [s.value, s.lo, s.hi]), ...live.live.map((p) => p.value), ...live.backtest.map((p) => p.value)]
  const yDomain = pad(extent(ys, [0, 1]), 0.12) as [number, number]
  const hasValues = steps.some((s) => s.value != null) || live.live.length > 0 || live.backtest.length > 0
  const lastLive = live.live[live.live.length - 1]
  const livePrimary = model.live?.primary
  const liveNow = livePrimary?.value ?? lastLive?.value

  return (
    <div className="lab-improve__model">
      <p className="lab-improve__lede">
        Champion <b>{model.champion.version}</b>:{' '}
        {model.offline.skill != null
          ? <>skill <b>{pct(model.offline.skill)}</b>{model.offline.skill_lo != null && model.offline.skill_hi != null && <> ({pct(model.offline.skill_lo)} to {pct(model.offline.skill_hi)})</>} over {vs} at {h} on the held-out set{model.offline.holdout ? ` (${model.offline.holdout})` : ''}.</>
          : <>no offline skill on a held-out set yet.</>}
        {' '}{livePrimary?.value != null
          ? <>Live on our feed, last {model.live?.hours ?? 24} h: <b>{pct(livePrimary.value)}</b> {livePrimary.name}{model.live?.n ? ` (${model.live.n.toLocaleString('en-GB')} graded)` : ''}.</>
          : lastLive ? <>Live on our feed, last hour: <b>{pct(lastLive.value)}</b> ({lastLive.n.toLocaleString('en-GB')} graded).</>
            : key === 'fishing' || !model.live ? 'Not graded on our live feed yet.' : 'No live grades at this horizon yet.'}
      </p>
      {hasValues || marks.length ? (
        <Chart label={`${SHORT[key]} champion skill over ${vs} at ${h}, offline and live, with model events`} x={{ type: 'time', domain: xDomain }} y={{ domain: yDomain, percent: true, label: `skill over ${vs}` }} height={240} margin={{ top: 26 }}>
          <ZeroLine />
          <ChampionSteps steps={steps} end={xDomain[1]} vs={vs} h={h} />
          <SkillLine points={live.backtest} cls="backtest" name={`backtest replay, ${live.name}`} />
          <SkillLine points={live.live} cls="live" name={`live, ${live.name}`} />
          <EventMarks marks={marks} />
        </Chart>
      ) : <p className="lab-improve__muted">Nothing recorded for this model yet.</p>}
      <Legend hasStep={steps.some((s) => s.value != null)} hasBand={steps.some((s) => s.lo != null)} hasLive={live.live.length > 0} hasBacktest={live.backtest.length > 0} kinds={[...new Set(marks.map((m) => m.kind))]} />
      {liveNow != null && model.offline.skill != null && liveNow < model.offline.skill && (
        <p className="lab-improve__note">Live skill is below the offline result: our feed is not the held-out set, so we show both.</p>
      )}
    </div>
  )
}

const ZeroLine = () => {
  const { X, Y, xNum } = useChart()
  if (!xNum) return null
  const [a, b] = xNum.domain
  return <line className="lab-improve__zero" x1={X(a)} x2={X(b)} y1={Y(0)} y2={Y(0)} />
}

function ChampionSteps({ steps, end, vs, h }: { steps: Step[]; end: number; vs: string; h: string }) {
  const { X, Y, tip } = useChart()
  return (
    <g className="lab-improve__steps">
      {steps.map((s, i) => {
        if (s.value == null) return null
        const x1 = X(s.t)
        const x2 = X(steps[i + 1]?.t ?? end)
        const next = steps[i + 1]
        const show = () => tip({
          x: (x1 + x2) / 2, y: Y(s.hi ?? s.value!) - 8,
          content: <><b>{s.version}</b><br />{s.how === 'recalibrated' ? 'recalibrated' : s.how === 'current' ? 'current champion' : s.how} {timeFull(s.t)}<br />skill {pct(s.value)} over {vs} at {h}{s.lo != null && s.hi != null ? ` (${pct(s.lo)} to ${pct(s.hi)})` : ''}</>,
        })
        return (
          <g key={`${s.version}-${s.t}`} tabIndex={0} onPointerEnter={show} onFocus={show} onBlur={() => tip(null)}>
            {s.lo != null && s.hi != null && <rect className="lab-improve__band" x={x1} width={Math.max(1, x2 - x1)} y={Y(s.hi)} height={Math.max(1, Y(s.lo) - Y(s.hi))} />}
            <line className="lab-improve__step" x1={x1} x2={x2} y1={Y(s.value)} y2={Y(s.value)} />
            {next?.value != null && <line className="lab-improve__step" x1={x2} x2={x2} y1={Y(s.value)} y2={Y(next.value)} />}
            <rect className="lab-improve__hit" x={x1} width={Math.max(6, x2 - x1)} y={Y(s.value) - 6} height={12} />
          </g>
        )
      })}
    </g>
  )
}

function SkillLine({ points, cls, name }: { points: LivePoint[]; cls: string; name: string }) {
  const { X, Y, tip } = useChart()
  if (!points.length) return null
  const d = points.map((p, i) => `${i ? 'L' : 'M'}${X(p.t).toFixed(1)},${Y(p.value).toFixed(1)}`).join('')
  return (
    <g className={`lab-improve__line lab-improve__line--${cls}`}>
      <path d={d} />
      {points.map((p) => {
        const show = () => tip({ x: X(p.t), y: Y(p.value) - 8, content: <><b>{pct(p.value)}</b> {name}<br />{timeFull(p.t)} · {p.n.toLocaleString('en-GB')} graded</> })
        return <circle key={p.t} cx={X(p.t)} cy={Y(p.value)} r={points.length > 40 ? 1.5 : 2.5} tabIndex={0} onPointerEnter={show} onFocus={show} onBlur={() => tip(null)} />
      })}
    </g>
  )
}

const GLYPH: Record<MarkerKind, string> = {
  promoted: 'M0,-5L5,4L-5,4Z',                      // up triangle
  rejected: 'M-4,-4L4,4M4,-4L-4,4',                  // cross
  recalibrated: 'M0,-5L5,0L0,5L-5,0Z',               // diamond
  deployed: 'M-4,-4H4V4H-4Z',                         // square
  proposal: 'M0,-5L1.5,-1.5L5,-1.5L2.2,1L3.2,5L0,2.6L-3.2,5L-2.2,1L-5,-1.5L-1.5,-1.5Z', // star
}

function EventMarks({ marks }: { marks: Marker[] }) {
  const { X, box, tip } = useChart()
  // markers sit in a strip above the plot; ones closer than 9 px stack downward so none hides another
  const placed: { m: Marker; x: number; row: number }[] = []
  for (const m of marks) {
    const x = X(m.t)
    let row = 0
    while (placed.some((p) => p.row === row && Math.abs(p.x - x) < 9)) row++
    placed.push({ m, x, row })
  }
  return (
    <g className="lab-improve__marks">
      {placed.map(({ m, x, row }, i) => {
        const y = box.top - 14 + row * 11
        const show = () => tip({
          x, y: y + 10,
          content: <><b>{m.title}</b><br />{timeFull(m.t)}{m.target !== modelKey(m.target) ? ` · ${m.target}` : ''}{m.changed && <><br />Changed: {m.changed}</>}{m.why && <><br />Why: {m.why}</>}</>,
        })
        return (
          <g key={i} transform={`translate(${x} ${y})`} className={`lab-improve__mark lab-improve__mark--${m.kind}`} tabIndex={0} role="img" aria-label={`${m.title}, ${timeFull(m.t)}`} onPointerEnter={show} onFocus={show} onBlur={() => tip(null)}>
            <line className="lab-improve__tick" y1={4} y2={box.bottom - y} />
            <circle className="lab-improve__hit" r={7} />
            <path d={GLYPH[m.kind]} />
          </g>
        )
      })}
    </g>
  )
}

function Legend({ hasStep, hasBand, hasLive, hasBacktest, kinds }: { hasStep: boolean; hasBand: boolean; hasLive: boolean; hasBacktest: boolean; kinds: MarkerKind[] }) {
  return (
    <ul className="lab-improve__legend" aria-label="Legend">
      {hasStep && <li><svg width="18" height="10" aria-hidden><line className="lab-improve__step" x1="0" x2="18" y1="5" y2="5" /></svg>champion, held-out set</li>}
      {hasBand && <li><svg width="18" height="10" aria-hidden><rect className="lab-improve__band" width="18" height="10" /></svg>95% interval</li>}
      {hasLive && <li className="lab-improve__line--live"><svg width="18" height="10" aria-hidden><path d="M0,5H18" /></svg>live, our feed</li>}
      {hasBacktest && <li className="lab-improve__line--backtest"><svg width="18" height="10" aria-hidden><path d="M0,5H18" /></svg>backtest replay</li>}
      {kinds.map((k) => (
        <li key={k} className={`lab-improve__mark--${k}`}><svg width="12" height="12" viewBox="-6 -6 12 12" aria-hidden><path d={GLYPH[k]} /></svg>{MARKER_LABEL[k].toLowerCase()}</li>
      ))}
    </ul>
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
