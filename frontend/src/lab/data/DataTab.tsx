// Data tab of a model page: 3 counters, the growth of graded predictions (live and backtest), the sources list.
import { fmtDay, fmtHM } from '../../timeline/format'
import { Chart, Legend, Line, extent, type Tone } from '../charts'
import { count, countedFrom, outcomeSeries, sourceSpans } from '../live/shape'
import { targetOf, type ModelRef } from '../live/plain'
import type { TabModel } from '../tabs'
import type { LabData } from '../types'
import { dataCounters } from './shape'
import '../live/live.css'

/** The tab contract (tabs.ts), also taking a bare target or a /lab/summary entry and null while loading. */
export interface DataTabProps { model: TabModel | ModelRef; data: LabData | null }

const MODE_TONE: Record<string, Tone> = { live: 'accent', backtest: 'warn', all: 'accent' }
const MODE_NAME: Record<string, string> = { live: 'Live feed', backtest: 'Replayed past hours', all: 'Live and replayed' }
const date = (t: number) => new Date(t).toISOString().slice(0, 10)

export function DataTab({ model, data }: DataTabProps) {
  if (!data) return <p className="ll-muted" role="status">Loading…</p>
  const c = dataCounters(data, targetOf(model))
  const outs = outcomeSeries(data.outcomes)
  const pts = outs.flatMap((s) => s.points)
  const from = countedFrom(data, pts[0]?.t)
  const spans = sourceSpans(data.sources)
  return (
    <section className="ll-sec" aria-label="Data">
      <div className="ll-tiles">
        <div className="ll-tile ll-tile--none">
          <div className="ll-tile__title">Graded predictions</div>
          <div className="ll-count">{c.graded == null ? '–' : `${data.truncated ? '≥ ' : ''}${count(c.graded)}`}</div>
          <div className="ll-tile__caption">{from == null ? 'None graded yet' : `All three models, checked against what happened, since ${fmtDay(from)}`}</div>
        </div>
        <div className="ll-tile ll-tile--none">
          <div className="ll-tile__title">Training examples</div>
          <div className="ll-count">{c.training == null ? '–' : count(c.training)}</div>
          <div className="ll-tile__caption">{c.training == null ? 'No run with a recorded size yet' : 'In the latest training run'}</div>
        </div>
        <div className="ll-tile ll-tile--none">
          <div className="ll-tile__title">History depth</div>
          <div className="ll-count">{c.depth ?? '–'}</div>
          <div className="ll-tile__caption">{c.oldest == null ? 'No source history recorded' : `Oldest data from ${date(c.oldest)}`}</div>
        </div>
      </div>
      <div className="ll-grid2">
        <div className="ll-card">
          <h4>Graded predictions, growing</h4>
          {!pts.length ? <p className="ll-muted">No graded predictions yet.</p> : (
            <>
              <Chart label="Graded predictions over time" x={{ type: 'time', domain: extent(pts.map((p) => p.t)) }}
                y={{ domain: [0, Math.max(1, ...pts.map((p) => p.cumulative)) * 1.05], format: count, ticks: 4 }} height={180}>
                {outs.map((s) => (
                  <Line key={s.mode} label={MODE_NAME[s.mode] ?? s.mode} tone={MODE_TONE[s.mode] ?? 'ink'} dots data={s.points.map((p) => ({ ...p, x: p.t, y: p.cumulative }))}
                    tip={(p) => <>{fmtDay(p.t)} {fmtHM(p.t)}<br />+{p.n.toLocaleString('en-GB')} graded, <b>{p.cumulative.toLocaleString('en-GB')}</b> in total</>} />
                ))}
              </Chart>
              <Legend items={outs.map((s) => ({ label: MODE_NAME[s.mode] ?? s.mode, tone: MODE_TONE[s.mode] ?? 'ink' }))} />
            </>
          )}
        </div>
        <div className="ll-card">
          <h4>Sources</h4>
          {!spans.length ? <p className="ll-muted">No source history recorded.</p> : (
            <ul className="ll-list">
              {spans.map((s) => (
                <li key={`${s.src}|${s.stream}`}><span>{s.label}</span><span>{count(s.rows)} rows · {date(s.oldest)} to {date(s.newest)}</span></li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  )
}
