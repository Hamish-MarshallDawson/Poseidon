import { useEffect, useState } from 'react'
import { adapter } from '../data/index'
import { mockBaselines } from '../data/mock'
import { ui } from '../store/ui'
import { fmtDay, fmtDuration, fmtHM } from '../timeline/format'
import { shownNow } from '../timeline/replay'
import type { Leaderboard, Outcome, RiskScore } from '../types'
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
  const [board, setBoard] = useState<Leaderboard | null>(null)
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
    adapter.leaderboard?.().then(setBoard, () => {})   // live skill against the baselines (#121); absent before the backend has it
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
          {board ? <LiveSkill board={board} /> : <h3>Against three baselines</h3>}
          {board ? null : check.baselines ? (
            <ul className="fc-base">
              {check.baselines.map((b) => <li key={b.model_version}><span>{BASELINE_LABEL[b.model_version]}</span><span>{b.hits} of {b.n} ({range(b.ci)})</span></li>)}
            </ul>
          ) : <p className="fc-muted">Waiting for the evaluation read (precision at {K} per model version).</p>}
          {!board && check.baselines && <p>{overlap ? 'The ranges overlap, so this check cannot yet tell the model from the baselines.' : 'The model’s range sits above all three baselines.'}</p>}
        </>
      )}
    </section>
  )
}

const hrs = (s: number) => `${Math.round(s / 3600)} h`
const signed = (x: number) => `${x >= 0 ? '+' : '−'}${Math.abs(Math.round(x * 100))} %`

// Live skill from GET /model/leaderboard (last 24 h of graded predictions): the go-dark model's Brier score against
// the observed base rate, and the route model's median error against dead reckoning, per horizon.
function LiveSkill({ board }: { board: Leaderboard }) {
  const dark = board.live_godark.filter((d) => d.n > 0)
  const route = board.live_route.filter((r) => r.n > 0 && r.target === 'route')
  return (
    <>
      <h3>Against the baselines · last {board.hours} h</h3>
      {!dark.length && !route.length ? <p className="fc-muted">No graded predictions yet.</p> : (
        <ul className="fc-base">
          {dark.map((d) => (
            <li key={`d-${d.model_version}-${d.horizon_s}`}>
              <span>Going dark, {hrs(d.horizon_s)} · {d.model_version}</span>
              <span>{d.brier_skill != null ? `${signed(d.brier_skill)} vs base rate` : 'no skill yet'} · {d.positives} of {d.n}</span>
            </li>
          ))}
          {route.map((r) => (
            <li key={`r-${r.model_version}-${r.horizon_s}`}>
              <span>Route, {hrs(r.horizon_s)} · {r.model_version}</span>
              <span>{(r.median_err_m / 1000).toFixed(1)} km{r.baseline_median_err_m != null ? ` vs ${(r.baseline_median_err_m / 1000).toFixed(1)} km dead reckoning` : ''}{r.coverage_80 != null ? ` · 80 % ring held ${Math.round(r.coverage_80 * 100)} %` : ''} · n {r.n}</span>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}
