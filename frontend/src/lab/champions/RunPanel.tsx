import { useEffect, useRef, useState } from 'react'
import type { Proposal, RunDetail } from '../types'
import {
  STATUS_LABEL, calibrationChecks, calibrationOk, configDiff, decisionHeadline, fmtCalCheck, fmtCount, fmtMonth, fmtPct, fmtStat,
  fmtWhen, horizonLabel, horizonRows, lossLabel, proposerLabel, targetLabel, weakestStrata, type RunRecord,
} from '../runs/shape'
import { decisionSentence } from './shape'

const show = (v: unknown) => (v == null ? '—' : typeof v === 'object' ? JSON.stringify(v) : String(v))
const plain = (s: string) => s.replace(/dead reckoning/gi, 'a straight-line guess')

/** A run's story over the page: what changed, why (Gemini's reasoning), the rule as ✓/✗, then the technical numbers.
 *  Escape or the close button shuts it (Escape is consumed so the page behind stays open). */
export function RunPanel({ run, byId, proposals, loadDetail, onClose }: {
  run: RunRecord
  byId: Map<string, RunRecord>
  proposals: Proposal[]
  loadDetail: (runId: string) => Promise<RunDetail | null>
  onClose: () => void
}) {
  const [detail, setDetail] = useState<RunDetail | null | undefined>(undefined)
  const closeRef = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    let live = true
    loadDetail(run.run_id).then((d) => live && setDetail(d), () => live && setDetail(null))
    return () => { live = false }
  }, [run.run_id, loadDetail])
  useEffect(() => {
    const back = document.activeElement as HTMLElement | null
    closeRef.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      e.preventDefault(); e.stopImmediatePropagation(); onClose()
    }
    window.addEventListener('keydown', onKey, true)
    return () => { window.removeEventListener('keydown', onKey, true); back?.focus?.() }
  }, [onClose])

  const r: RunRecord = (detail as RunRecord | null | undefined) ?? run
  const parent = (detail?.parent as RunRecord | null | undefined) ?? (run.parent_run ? byId.get(run.parent_run) ?? null : null)
  const diff = (detail?.config_diff?.length ? detail.config_diff : configDiff(r.config, parent?.config ?? null)).filter((d) => d.key !== 'seed')
  const rationale = detail?.rationale ?? proposals.find((p) => p.run_id === run.run_id)?.rationale ?? null
  const headline = decisionHeadline(r, detail)
  const m = r.metrics
  const unit = m?.loss_unit
  const rows = horizonRows(r)
  const cal = calibrationChecks(r)
  const strata = weakestStrata(r)

  return (
    <div className="lc-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <aside className="lc-panel" role="dialog" aria-modal="true" aria-labelledby="lc-panel-h">
        <header className="lc-panel-head">
          <div>
            <span className="lc-kicker">{targetLabel(r.target)} · {proposerLabel(r.proposer)} · {fmtWhen(r.created_at)}</span>
            <h3 id="lc-panel-h" className="lc-mono">{r.run_id}</h3>
            <span className={`lc-pill lc-pill--${r.status}`}>{STATUS_LABEL[r.status] ?? r.status}</span>
          </div>
          <button ref={closeRef} type="button" className="lc-close" onClick={onClose} aria-label="Close the run panel">×</button>
        </header>

        <p className="lc-sentence">{decisionSentence(r, byId)}</p>
        {detail === undefined && <p className="lc-muted" role="status">Loading the run…</p>}

        <h4>What changed</h4>
        {!r.parent_run ? <p className="lc-muted">A first model: nothing to compare with.</p> : !diff.length ? (
          <p className="lc-muted">Same settings as <span className="lc-mono">{r.parent_run}</span>, trained on newer data.</p>
        ) : (
          <table className="lc-mini">
            <thead><tr><th>Setting</th><th>Before</th><th>This run</th></tr></thead>
            <tbody>{diff.map((d) => <tr key={d.key}><td>{d.key.replace(/_/g, ' ')}</td><td>{show(d.parent)}</td><td><b>{show(d.value)}</b></td></tr>)}</tbody>
          </table>
        )}

        {rationale && (<><h4>{r.proposer === 'gemini' ? "Gemini's reasoning" : 'Reasoning'}</h4><blockquote className="lc-quote">{rationale}</blockquote></>)}

        <h4>The rule decides</h4>
        {detail?.rule?.length ? (
          <ul className="lc-rule">
            {detail.rule.map((c, i) => (
              <li key={i} data-pass={c.passed == null ? 'na' : c.passed ? 'yes' : 'no'}>
                <b aria-label={c.passed == null ? 'not checked' : c.passed ? 'passed' : 'failed'}>{c.passed == null ? '–' : c.passed ? '✓' : '✗'}</b>
                <span>{plain(c.check)}</span>
              </li>
            ))}
            {detail.confirm && (
              <li data-pass={detail.confirm.passed ? 'yes' : 'no'}>
                <b>{detail.confirm.passed ? '✓' : '✗'}</b><span>A second training with another seed agrees</span>
              </li>
            )}
          </ul>
        ) : <p className="lc-muted">{detail === undefined ? '…' : m?.decision?.reasons?.length ? plain(m.decision.reasons.join(' ')) : 'No rule record for this run (it was decided by hand or before the rule existed).'}</p>}

        <details className="lc-tech">
          <summary>Technical numbers</summary>
          <p className="lc-muted">{plain(headline.main)}{headline.sub ? ` · ${plain(headline.sub)}` : ''}</p>
          {detail?.rule?.some((c) => c.detail) && (
            <ul className="lc-plainlist">{detail.rule.filter((c) => c.detail).map((c, i) => <li key={i}><b>{plain(c.check)}</b>: {plain(c.detail!)}</li>)}</ul>
          )}
          {rows.length > 0 && (
            <div className="lc-scroll"><table className="lc-mini">
              <thead><tr><th>Horizon</th><th>Skill vs baseline [95% CI]</th><th>{lossLabel(m)}</th><th>vs reference</th></tr></thead>
              <tbody>
                {rows.map(({ h, skill, vs }) => (
                  <tr key={h}>
                    <td>{horizonLabel(h)}</td>
                    <td>{fmtPct(skill?.skill)} <span className="lc-muted">[{fmtPct(skill?.skill_lo)}, {fmtPct(skill?.skill_hi)}]</span></td>
                    <td>{fmtStat(skill?.stat, unit)} <span className="lc-muted">vs {fmtStat(skill?.baseline_stat, unit)}</span></td>
                    <td>{vs?.diff == null ? '—' : <>{vs.diff > 0 ? '+' : ''}{fmtStat(vs.diff, unit)} <span className="lc-muted">[{fmtStat(vs.lo, unit)}, {fmtStat(vs.hi, unit)}] {vs.win ? 'win' : 'no win'}</span></>}</td>
                  </tr>
                ))}
              </tbody>
            </table></div>
          )}
          {cal.length > 0 && (
            <ul className="lc-rule">
              {cal.map((c, i) => {
                const ok = calibrationOk(c)
                return <li key={i} data-pass={ok == null ? 'na' : ok ? 'yes' : 'no'}><b>{ok == null ? '–' : ok ? '✓' : '✗'}</b><span>{c.name} at {horizonLabel(c.horizon_s)}: {fmtCalCheck(c)}</span></li>
              })}
            </ul>
          )}
          {strata.length > 0 && (
            <div className="lc-scroll"><table className="lc-mini">
              <thead><tr><th>Weakest stratum</th><th>n</th><th>cand vs ref</th></tr></thead>
              <tbody>{strata.map((s) => (
                <tr key={`${s.stratum}-${s.value}-${s.horizon_s}`}>
                  <td>{s.stratum}={s.value} · {horizonLabel(s.horizon_s)}</td><td>{fmtCount(s.n)}</td><td>{fmtStat(s.cand, unit)} vs {fmtStat(s.ref, unit)}</td>
                </tr>
              ))}</tbody>
            </table></div>
          )}
          <dl className="lc-dl">
            <dt>Statistic</dt><dd>{m?.statistic ?? '—'}</dd>
            <dt>Training data</dt><dd>{fmtMonth(r.train_from)}–{fmtMonth(r.train_to)} · {fmtCount(m?.split?.n_train)} examples</dd>
            <dt>Frozen test</dt><dd>{m?.holdout?.name ?? '—'} · {fmtCount(m?.holdout?.n ?? m?.split?.n_test)} cases{m?.holdout?.hash ? ` · ${m.holdout.hash.slice(0, 10)}` : ''}</dd>
            {m?.decision?.against && <><dt>Compared with</dt><dd>{plain(m.decision.against)}{m.decision.alpha != null ? ` · α ${m.decision.alpha}` : ''}{m.decision.n_comparisons ? ` / ${m.decision.n_comparisons}` : ''}</dd></>}
            {m?.seconds != null && <><dt>Train time</dt><dd>{Math.round(m.seconds)} s</dd></>}
          </dl>
        </details>
      </aside>
    </div>
  )
}
