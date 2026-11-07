import { useEffect, useState } from 'react'
import { adapter } from '../data/index'
import { mockBaselines } from '../data/mock'
import { ui } from '../store/ui'
import { fmtDay, fmtDuration, fmtHM } from '../timeline/format'
import { shownNow } from '../timeline/replay'
import type { Outcome, RiskScore } from '../types'
import { BASELINE_LABEL, FREEZE_TS, HORIZON_MS, OUTCOME_LABEL, RESOLVE_LAG_MS } from './labels'
import { forecastUi } from './state'
import { wilson } from './stats'

const H = 3_600_000
const K = 10
const range = ([a, b]: [number, number]) => `${Math.round(a * 100)}–${Math.round(b * 100)} %`

interface Check { made: number; frozen: boolean; rows: { s: RiskScore; o: Outcome | undefined }[]; baselines: ReturnType<typeof mockBaselines> | null }

// "Forecast check": the frozen top-10 forecast against what happened, with honest intervals (forecast report, Sunday card).
// Uses the frozen forecast once it has resolved at the shown time; before that, the newest resolved hourly forecast.
export function ForecastCheck() {
  const isMock = ui.use((s) => s.feed.isMock)
  const [check, setCheck] = useState<Check | null>(null)
  const close = () => forecastUi.set({ checkOpen: false })

  useEffect(() => {
    const t = shownNow()
    const frozen = t >= FREEZE_TS + HORIZON_MS + RESOLVE_LAG_MS
    const made = frozen ? FREEZE_TS : Math.floor((t - HORIZON_MS - RESOLVE_LAG_MS) / H) * H
    const resolved = made + HORIZON_MS + RESOLVE_LAG_MS
    if (!adapter) return
    Promise.all([adapter.scores(made), adapter.outcomes(resolved, resolved)]).then(([scores, outs]) => {
      const top = scores.filter((s) => s.made_at === made).sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99)).slice(0, K)
      setCheck({ made, frozen, rows: top.map((s) => ({ s, o: outs.find((o) => o.score_id === s.id) })), baselines: adapter?.isMock ? mockBaselines(made, K) : null })
    }, () => setCheck({ made, frozen, rows: [], baselines: null }))
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && close()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const scored = check?.rows.filter((r) => r.o && !r.o.censored) ?? []
  const hits = scored.filter((r) => r.o!.label === 'hit').length
  const censored = check?.rows.filter((r) => r.o?.censored).length ?? 0
  const ci = wilson(hits, scored.length)
  const ciAll = wilson(hits, check?.rows.length ?? 0)
  const expected = scored.reduce((a, r) => a + r.s.p, 0)
  const leads = scored.flatMap((r) => (r.o!.lead_s != null ? [r.o!.lead_s] : [])).sort((a, b) => a - b)
  const overlap = check?.baselines?.some((b) => b.ci[1] >= ci[0])

  return (
    <section className="fc-check" role="dialog" aria-labelledby="fc-check-title">
      <header>
        <h2 id="fc-check-title">Forecast check · top {K}</h2>
        {isMock && <span className="fc-tag">Illustrative data</span>}
        <button className="fc-x" onClick={close} aria-label="Close forecast check">×</button>
      </header>
      {!check ? <p className="fc-muted">Loading…</p> : !check.rows.length ? <p className="fc-muted">No resolved forecast at the shown time.</p> : (
        <>
          <p className="fc-muted">
            {check.frozen ? 'Frozen forecast' : 'Hourly forecast'} made {fmtDay(check.made)} {fmtHM(check.made)}, scored {fmtHM(check.made + HORIZON_MS + RESOLVE_LAG_MS)}.
            {!check.frozen && <> The frozen forecast ({fmtDay(FREEZE_TS)} {fmtHM(FREEZE_TS)}) is scored {fmtHM(FREEZE_TS + HORIZON_MS + RESOLVE_LAG_MS)}.</>}
          </p>
          <p className="fc-head"><b>{hits} of {scored.length}</b> went silent with reception normal nearby <span>({range(ci)})</span></p>
          <p className="fc-muted">
            The p values predicted {expected.toFixed(1)} of {scored.length}.{leads.length > 0 && <> Median warning {fmtDuration(leads[leads.length >> 1] * 1000)}.</>}
            {censored > 0 && <> {censored} not scored; counted as a miss: {hits} of {check.rows.length} ({range(ciAll)}).</>}
          </p>
          <ol className="fc-rows">
            {check.rows.map(({ s, o }) => {
              const label = !o ? 'pending' : o.censored ? 'censored' : o.label
              return (
                <li key={s.id}>
                  <i className={`fc-sq ${label}`} aria-hidden />
                  <span className="fc-rank">{String(s.rank ?? '').padStart(2, '0')}</span>
                  <span>MMSI {s.mmsi}</span>
                  <span className="fc-p">{Math.round(s.p * 100)} %</span>
                  <span className="fc-muted">{label === 'pending' ? 'Pending' : OUTCOME_LABEL[label as keyof typeof OUTCOME_LABEL]}{o?.censored ? ` (${o.censored.replace('_', ' ')})` : ''}</span>
                </li>
              )
            })}
          </ol>
          <h3>Against three baselines</h3>
          {check.baselines ? (
            <ul className="fc-base">
              {check.baselines.map((b) => <li key={b.model_version}><span>{BASELINE_LABEL[b.model_version]}</span><span>{b.hits} of {b.n} ({range(b.ci)})</span></li>)}
            </ul>
          ) : <p className="fc-muted">Waiting for the evaluation read (precision at {K} per model version).</p>}
          {check.baselines && <p>{overlap ? 'The ranges overlap, so this check cannot yet tell the model from the baselines.' : 'The model’s range sits above all three baselines.'}</p>}
        </>
      )}
    </section>
  )
}
