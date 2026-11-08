// "Data collected": graded outcomes building up, history depth per source, training size per run, frozen held-out sets (/lab/data).
import { fmtDay, fmtHM } from '../../timeline/format'
import { Chart, Legend, Line, Ranges, extent, type Tone } from '../charts'
import type { LabData } from '../types'
import { count, countedFrom, outcomeSeries, sourceSpans, uniqueHoldouts } from './shape'
import './live.css'

export interface DataCollectedProps { data: LabData | null }

const MODE_TONE: Record<string, Tone> = { live: 'accent', backtest: 'warn', all: 'accent' }
const MODE_NAME: Record<string, string> = { live: 'live feed', backtest: 'backtest replay', all: 'live and backtest' }
const date = (t: number | null) => (t == null ? '–' : new Date(t).toISOString().slice(0, 10))
const year = (t: number) => String(new Date(t).getUTCFullYear())
const short = (s: string) => (s.length > 20 ? `${s.slice(0, 19)}…` : s)

export function DataCollected({ data }: DataCollectedProps) {
  if (!data) return <section className="ll-sec"><h3>Data collected</h3><p className="ll-muted">Loading…</p></section>
  const outs = outcomeSeries(data.outcomes)
  const opts = outs.flatMap((s) => s.points)
  const total = outs.reduce((a, s) => a + (s.points.at(-1)?.cumulative ?? 0), 0)
  const from = countedFrom(data, opts[0]?.t)
  const since = from == null ? '' : `since ${fmtDay(from)} ${fmtHM(from)}`
  const spans = sourceSpans(data.sources)
  const holdouts = uniqueHoldouts(data.holdouts)
  const training = data.training.filter((t) => t.n_train != null).sort((a, b) => a.created_at - b.created_at)
  const runLabel = (id: string) => { const t = training.find((r) => r.run_id === id); return t ? `${t.target} · ${fmtHM(t.created_at)}` : id }
  const [s0, s1] = extent(spans.flatMap((s) => [s.oldest, s.newest]))

  return (
    <section className="ll-sec" aria-labelledby="ll-data">
      <h3 id="ll-data">Data collected</h3>
      <div className="ll-grid2">
        <div className="ll-card">
          <h4>Graded predictions</h4>
          {!opts.length ? <p className="ll-muted">No graded predictions yet.</p> : (
            <>
              <p className="ll-say">{data.truncated ? 'At least ' : ''}<b>{total.toLocaleString('en-GB')}</b> predictions graded against what happened {since}: the evidence every promotion and recalibration is judged on.
                {data.truncated ? ' The oldest hours are left out (row limit), so this total is a lower bound.' : ''}</p>
              <Chart label={`Cumulative graded predictions ${since}`} x={{ type: 'time', domain: extent(opts.map((p) => p.t)) }} y={{ domain: [0, Math.max(1, ...opts.map((p) => p.cumulative)) * 1.05], format: count, ticks: 4 }} height={180}>
                {outs.map((s) => (
                  <Line key={s.mode} label={MODE_NAME[s.mode] ?? s.mode} tone={MODE_TONE[s.mode] ?? 'ink'} dots data={s.points.map((p) => ({ ...p, x: p.t, y: p.cumulative }))}
                    tip={(p) => <>{fmtDay(p.t)} {fmtHM(p.t)}<br />+{p.n.toLocaleString('en-GB')} graded, <b>{p.cumulative.toLocaleString('en-GB')}</b> in total</>} />
                ))}
              </Chart>
              <Legend items={outs.map((s) => ({ label: `${MODE_NAME[s.mode] ?? s.mode}, cumulative ${since}`, tone: MODE_TONE[s.mode] ?? 'ink' }))} />
            </>
          )}
          <h4>Frozen held-out sets</h4>
          <p className="ll-muted">Never trained on; every candidate is scored on the same rows, so runs compare fairly.</p>
          {!holdouts.length ? <p className="ll-muted">None recorded.</p> : (
            <table className="ll-table">
              <thead><tr><th>Model</th><th>Set</th><th>Period</th><th className="num">Rows</th></tr></thead>
              <tbody>{holdouts.map((h) => <tr key={`${h.target}|${h.name}|${h.hash}`}><td>{h.target}</td><td title={h.hash ? `hash ${h.hash}` : undefined}>{h.name}</td><td>{date(h.start)} to {date(h.end)}</td><td className="num">{h.n == null ? '–' : h.n.toLocaleString('en-GB')}</td></tr>)}</tbody>
            </table>
          )}
        </div>
        <div className="ll-card">
          <h4>History behind each source</h4>
          {!spans.length ? <p className="ll-muted">No source history recorded.</p> : (
            <>
              <Chart label="History depth per source, oldest to newest" x={{ type: 'time', domain: [s0, s1], format: year }} y={{ type: 'band', domain: spans.map((s) => s.label), format: short }} height={40 + 34 * spans.length}>
                <Ranges data={spans.map((s) => ({ ...s, y: s.label, x0: s.oldest, x1: s.newest }))} label="source history"
                  tip={(s) => <><b>{s.label}</b><br />{date(s.oldest)} to {date(s.newest)}<br />{s.rows.toLocaleString('en-GB')} rows in {s.windows.toLocaleString('en-GB')} windows</>} />
              </Chart>
              <p className="ll-muted">{spans.map((s) => `${s.label}: ${count(s.rows)} rows`).join(' · ')}</p>
            </>
          )}
          <h4>Training examples per run</h4>
          {!training.length ? <p className="ll-muted">No runs with a recorded training size.</p> : (
            <Chart label="Training examples per run" x={{ domain: [0, Math.max(...training.map((t) => t.n_train ?? 0)) * 1.05], format: count }} y={{ type: 'band', domain: training.map((t) => t.run_id), format: runLabel }} height={40 + 30 * training.length}>
              <Ranges data={training.map((t) => ({ ...t, y: t.run_id, x0: 0, x1: t.n_train ?? 0 }))} label="training run"
                tip={(t) => <><b>{t.run_id}</b><br />{(t.n_train ?? 0).toLocaleString('en-GB')} training examples, trained {fmtDay(t.created_at)} {fmtHM(t.created_at)}</>} />
            </Chart>
          )}
        </div>
      </div>
    </section>
  )
}
