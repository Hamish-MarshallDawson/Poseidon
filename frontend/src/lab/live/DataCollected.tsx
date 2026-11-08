// "Data collected": graded outcomes building up, history depth per source, training size per run, frozen held-out sets (/lab/data).
import { fmtDay, fmtHM } from '../../timeline/format'
import { Plot } from './Plot'
import { count, path, outcomeSeries, sourceSpans, uniqueHoldouts } from './shape'
import type { LabData } from './types'
import './live.css'

export interface DataCollectedProps { data: LabData | null }

const MODE_COLOR: Record<string, string> = { live: 'var(--dvm-accent-default)', backtest: 'var(--dvm-ship-class-b)', all: 'var(--dvm-accent-default)' }
const MODE_NAME: Record<string, string> = { live: 'live feed', backtest: 'backtest replay', all: 'live and backtest' }
const date = (t: number) => new Date(t).toISOString().slice(0, 10)

export function DataCollected({ data }: DataCollectedProps) {
  if (!data) return <section className="ll-sec"><h3>Data collected</h3><p className="ll-muted">Loading…</p></section>
  const outs = outcomeSeries(data.outcomes)
  const opts = outs.flatMap((s) => s.points)
  const total = outs.reduce((a, s) => a + (s.points.at(-1)?.cumulative ?? 0), 0)
  const spans = sourceSpans(data.sources)
  const holdouts = uniqueHoldouts(data.holdouts)
  const training = [...data.training].sort((a, b) => a.created_at - b.created_at)
  const nMax = Math.max(1, ...training.map((t) => t.n_train ?? 0))
  const s0 = Math.min(...spans.map((s) => s.oldest)), s1 = Math.max(...spans.map((s) => s.newest))

  return (
    <section className="ll-sec" aria-labelledby="ll-data">
      <h3 id="ll-data">Data collected</h3>
      <div className="ll-grid2">
        <div className="ll-card">
          <h4>Graded predictions</h4>
          {!opts.length ? <p className="ll-muted">No graded predictions yet.</p> : (
            <>
              <p className="ll-say"><b>{total.toLocaleString('en-GB')}</b> predictions graded against what happened since {fmtDay(opts[0].t)} {fmtHM(opts[0].t)}: the evidence every promotion and recalibration is judged on.</p>
              <Plot label="Cumulative graded predictions" x={[Math.min(...opts.map((p) => p.t)), Math.max(...opts.map((p) => p.t))]} y={[0, Math.max(...opts.map((p) => p.cumulative))]} time yTick={count}>
                {(c) => outs.map((s) => (
                  <g key={s.mode} style={{ color: MODE_COLOR[s.mode] ?? 'var(--dvm-text-secondary)' }}>
                    <path className="ll-line" d={path(s.points.map((p) => [c.x(p.t), c.y(p.cumulative)]))} />
                    {s.points.map((p) => <circle key={p.t} className="ll-dot" cx={c.x(p.t)} cy={c.y(p.cumulative)} r={2.5}><title>{`${fmtDay(p.t)} ${fmtHM(p.t)}: +${p.n.toLocaleString('en-GB')} graded (${MODE_NAME[s.mode] ?? s.mode}), ${p.cumulative.toLocaleString('en-GB')} in total`}</title></circle>)}
                  </g>
                ))}
              </Plot>
              <ul className="ll-keys">{outs.map((s) => <li key={s.mode}><i style={{ color: MODE_COLOR[s.mode] ?? 'var(--dvm-text-secondary)' }} />{MODE_NAME[s.mode] ?? s.mode}</li>)}</ul>
            </>
          )}
          <h4>Frozen held-out sets</h4>
          <p className="ll-muted">Never trained on; every candidate is scored on the same rows, so runs compare fairly.</p>
          {!holdouts.length ? <p className="ll-muted">None recorded.</p> : (
            <table className="ll-table">
              <thead><tr><th>Model</th><th>Set</th><th>Period</th><th className="num">Rows</th></tr></thead>
              <tbody>{holdouts.map((h) => <tr key={`${h.target}${h.hash}`}><td>{h.target}</td><td title={`hash ${h.hash}`}>{h.name}</td><td>{date(h.start)} to {date(h.end)}</td><td className="num">{h.n.toLocaleString('en-GB')}</td></tr>)}</tbody>
            </table>
          )}
        </div>
        <div className="ll-card">
          <h4>History behind each source</h4>
          {!spans.length ? <p className="ll-muted">No source history recorded.</p> : (
            <ul className="ll-spans">
              {spans.map((s) => (
                <li key={`${s.src}/${s.stream}`}>
                  <span className="ll-span-label">{s.label}<small>{count(s.rows)} rows · {date(s.oldest)} to {date(s.newest)}</small></span>
                  <span className="ll-track"><span className="ll-bar" style={{ left: `${((s.oldest - s0) / (s1 - s0 || 1)) * 100}%`, right: `${100 - ((s.newest - s0) / (s1 - s0 || 1)) * 100}%` }} /></span>
                </li>
              ))}
              <li className="ll-span-axis"><span /><span className="ll-track"><span>{new Date(s0).getUTCFullYear()}</span><span>{new Date(s1).getUTCFullYear()}</span></span></li>
            </ul>
          )}
          <h4>Training examples per run</h4>
          {!training.length ? <p className="ll-muted">No runs with a recorded training size.</p> : (
            <ul className="ll-bars">
              {training.map((t) => (
                <li key={t.run_id}>
                  <span className="ll-span-label" title={t.run_id}>{t.target}<small>{fmtDay(t.created_at)} {fmtHM(t.created_at)}</small></span>
                  <span className="ll-track"><span className="ll-bar" style={{ left: 0, right: `${100 - ((t.n_train ?? 0) / nMax) * 100}%` }} /></span>
                  <span className="num">{t.n_train == null ? '–' : count(t.n_train)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  )
}
