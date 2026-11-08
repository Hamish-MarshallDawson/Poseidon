import { useEffect, useMemo, useState } from 'react'
import {
  ALL, STATUS_LABEL, calibrationChecks, calibrationOk, changeLine, currentRun, decisionHeadline, fmtCalCheck, configDiff, decisionLine, distinct, filterRuns, fmtCount, fmtMonth,
  fmtPct, fmtStat, fmtWhen, horizonLabel, horizonRows, lossLabel, primarySkill, proposerLabel, skillRows, targetLabel, weakestStrata,
  type RunFilters, type RunRecord, type SkillRow,
} from './shape'
import { Chart, RefLine, Ranges, extent, pad } from '../charts'
import type { Proposal, Run, RunDetail } from '../types'
import { againstBaseline } from '../decision'
import './runs.css'

/** Props for the runs section of the Model Lab. */
export interface RunsProps {
  /** GET /lab/runs, newest first (strata dropped). */
  runs: Run[]
  /** GET /lab/proposals, newest first. */
  proposals: Proposal[]
  /** GET /lab/runs/{run_id}; resolve null when it can't be loaded (the table row is shown instead). */
  loadDetail: (runId: string) => Promise<RunDetail | null>
  /** Primary horizon (s) per target, e.g. from /lab/summary's offline.primary_h; otherwise each run's shortest horizon. */
  primaryH?: Partial<Record<string, number>>
}

/** Every run with its config, data and evaluation, why the rule promoted or rejected it, and the proposals that led to runs. */
export function Runs({ runs, proposals, loadDetail, primaryH }: RunsProps) {
  const [filters, setFilters] = useState<RunFilters>({ target: ALL, proposer: ALL, status: ALL })
  const shown = useMemo(() => filterRuns(runs, filters), [runs, filters])
  const byId = useMemo(() => new Map(runs.map((r) => [r.run_id, r])), [runs])
  const [selected, setSelected] = useState<string | null>(null)
  const shownRun = currentRun(selected, byId, shown)
  const current = shownRun?.run_id ?? null
  const champions = useMemo(() => new Map(runs.filter((r) => r.status === 'champion').map((r) => [r.target, r])), [runs])

  const select = (id: string) => {
    setSelected(id)
    requestAnimationFrame(() => document.getElementById('lr-detail')?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }))
  }
  const menu = (key: keyof RunFilters, label: string, values: string[], name: (v: string) => string) => (
    <label className="lr-filter">
      <span className="lr-kicker">{label}</span>
      <select value={filters[key]} onChange={(e) => setFilters({ ...filters, [key]: e.target.value })}>
        <option value={ALL}>All</option>
        {values.map((v) => <option key={v} value={v}>{name(v)}</option>)}
      </select>
    </label>
  )

  return (
    <div className="lr">
      <div className="lr-filters">
        {menu('target', 'Model', distinct(runs, (r) => r.target), targetLabel)}
        {menu('proposer', 'Proposed by', distinct(runs, (r) => r.proposer), proposerLabel)}
        {menu('status', 'Status', distinct(runs, (r) => r.status), (s) => STATUS_LABEL[s] ?? s)}
        <span className="lr-count">{shown.length} of {runs.length} runs</span>
      </div>
      <div className="lr-body">
        <div className="lr-table-wrap">
          {!shown.length ? <p className="lr-muted">No runs match these filters.</p> : (
            <table className="lr-table">
              <thead>
                <tr>
                  <th>When</th><th>Model</th><th>By</th><th>Change vs parent</th><th>Data</th><th>Skill vs baseline</th><th>Decision</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((r) => {
                  const s = primarySkill(r, primaryH?.[r.target])
                  return (
                    <tr key={r.run_id} className={r.run_id === current ? 'is-on' : undefined} onClick={() => select(r.run_id)}>
                      <td className="lr-mono">
                        <button type="button" className="lr-rowbtn" onClick={(e) => { e.stopPropagation(); select(r.run_id) }} aria-pressed={r.run_id === current}>
                          {fmtWhen(r.created_at)}
                        </button>
                      </td>
                      <td>{targetLabel(r.target)}<span className="lr-sub">{r.model ?? '—'}</span></td>
                      <td>{proposerLabel(r.proposer)}</td>
                      <td>{changeLine(r, byId)}</td>
                      <td className="lr-mono">{fmtMonth(r.train_from)}–{fmtMonth(r.train_to)}<span className="lr-sub">n {fmtCount(r.metrics?.split?.n_train)}</span></td>
                      <td className="lr-mono">
                        {s?.skill == null ? '—' : <>{fmtPct(s.skill)}<span className="lr-sub">[{fmtPct(s.lo)}, {fmtPct(s.hi)}] at {horizonLabel(s.h)}</span></>}
                      </td>
                      <td><StatusTag status={r.status} /><span className="lr-sub">{decisionLine(r)}</span></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
        {shownRun && <RunDetailView key={shownRun.run_id} run={shownRun} byId={byId} loadDetail={loadDetail} proposals={proposals} champion={champions.get(shownRun.target)} />}
      </div>
      <ProposalLog proposals={proposals} runs={byId} onOpen={select} />
    </div>
  )
}

function StatusTag({ status }: { status: string }) {
  return <span className={`lr-status lr-status--${status}`}>{STATUS_LABEL[status] ?? status}</span>
}

const show = (v: unknown) => (v == null ? '—' : typeof v === 'object' ? JSON.stringify(v) : String(v))

function RunDetailView({ run, byId, loadDetail, proposals, champion }: { run: RunRecord; byId: Map<string, RunRecord>; loadDetail: RunsProps['loadDetail']; proposals: Proposal[]; champion?: RunRecord }) {
  const [detail, setDetail] = useState<RunDetail | null | undefined>(undefined)
  useEffect(() => {
    let live = true
    loadDetail(run.run_id).then((d) => live && setDetail(d), () => live && setDetail(null))
    return () => { live = false }
  }, [run.run_id, loadDetail])

  const r: RunRecord = detail ?? run
  const parent = detail?.parent ?? (run.parent_run ? byId.get(run.parent_run) ?? null : null)
  const diff = detail?.config_diff?.length ? detail.config_diff : configDiff(r.config, parent?.config ?? null)
  const proposal = proposals.find((p) => p.run_id === run.run_id)
  const rationale = detail?.rationale ?? proposal?.rationale ?? null
  const loss = lossLabel(r.metrics)
  const unit = r.metrics?.loss_unit
  const rows = horizonRows(r)
  const cal = calibrationChecks(r)
  const strata = weakestStrata(r)
  const against = r.metrics?.decision?.against
  const vsChampion = !!against && !againstBaseline(against)
  const m = r.metrics
  const headline = decisionHeadline(r, detail)

  return (
    <section id="lr-detail" className="lr-detail" aria-label={`Run ${run.run_id}`}>
      <header>
        <div>
          <span className="lr-kicker">{targetLabel(r.target)} · {proposerLabel(r.proposer)}{r.source ? ` · ${r.source}` : ''}</span>
          <h3 className="lr-mono">{r.run_id}</h3>
        </div>
        <StatusTag status={r.status} />
      </header>
      <p className="lr-decision">{headline.main}</p>
      {headline.sub && <p className="lr-muted">{headline.sub}</p>}
      {detail === undefined && <p className="lr-muted">Loading run detail…</p>}

      <h4>Promotion rule</h4>
      {detail?.rule?.length ? (
        <ul className="lr-rule">
          {detail.rule.map((c, i) => (
            <li key={i} data-pass={c.passed == null ? 'na' : c.passed ? 'yes' : 'no'}>
              <i aria-hidden />
              <span>{c.check}{c.detail && <span className="lr-sub">{c.detail}</span>}</span>
              <b>{c.passed == null ? 'n/a' : c.passed ? 'pass' : 'fail'}</b>
            </li>
          ))}
          <li data-pass={detail.confirm == null ? 'na' : detail.confirm.passed ? 'yes' : 'no'}>
            <i aria-hidden />
            <span>
              Second seed confirms it
              <span className="lr-sub">{detail.confirm ? detail.confirm.run_id : 'not run: only needed after the first checks pass'}</span>
            </span>
            <b>{detail.confirm == null ? 'n/a' : detail.confirm.passed ? 'pass' : 'fail'}</b>
          </li>
        </ul>
      ) : <p className="lr-muted">{detail === undefined ? '…' : m?.decision?.reasons?.length ? m.decision.reasons.join(' ') : 'No rule record for this run (it predates the rule).'}</p>}

      <h4>Skill per horizon</h4>
      {!rows.length ? <p className="lr-muted">No holdout evaluation stored.</p> : (
        <>
          <p className="lr-muted">
            Skill = how much lower the {loss} is than the baseline (0 % = no better); interval is 95 %.
            {vsChampion ? ` Against the champion: ${loss} difference, below 0 is better.` : ''}
          </p>
          <SkillChart rows={skillRows(r, champion && champion.run_id !== r.run_id ? champion : null)} />
          <div className="lr-scroll"><table className="lr-mini">
            <thead><tr><th>Horizon</th><th>Skill vs baseline</th><th>{loss}</th><th>{vsChampion ? 'vs champion' : 'vs baseline'}</th></tr></thead>
            <tbody>
              {rows.map(({ h, skill, vs }) => (
                <tr key={h}>
                  <td>{horizonLabel(h)}</td>
                  <td>
                    <span className="lr-nowrap">{fmtPct(skill?.skill)}</span> <span className="lr-sub">[{fmtPct(skill?.skill_lo)}, {fmtPct(skill?.skill_hi)}]</span>
                  </td>
                  <td>{fmtStat(skill?.stat, unit)} <span className="lr-sub">baseline {fmtStat(skill?.baseline_stat, unit)}</span></td>
                  <td>
                    {vs?.diff == null ? '—' : <>{vs.diff > 0 ? '+' : ''}{fmtStat(vs.diff, unit)} <span className="lr-sub">[{fmtStat(vs.lo, unit)}, {fmtStat(vs.hi, unit)}] {vs.win ? 'win' : 'no win'}</span></>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table></div>
        </>
      )}

      <h4>Calibration</h4>
      {!cal.length ? <p className="lr-muted">No calibration checks stored.</p> : (
        <ul className="lr-rule">
          {cal.map((c, i) => {
            const ok = calibrationOk(c)
            return (
              <li key={i} data-pass={ok == null ? 'na' : ok ? 'yes' : 'no'}>
                <i aria-hidden />
                <span>{c.name.toUpperCase() === 'ECE' ? 'Expected calibration error' : c.name} at {horizonLabel(c.horizon_s)}
                  <span className="lr-sub">{fmtCalCheck(c)}</span>
                </span>
                <b>{ok == null ? 'n/a' : ok ? 'ok' : 'off'}</b>
              </li>
            )
          })}
        </ul>
      )}

      <h4>Change vs parent</h4>
      <p className="lr-muted">{parent ? <>Parent <span className="lr-mono">{parent.run_id}</span></> : r.parent_run ? <>Parent <span className="lr-mono">{r.parent_run}</span> (not loaded)</> : 'No parent: a fresh configuration, shown in full.'}</p>
      {diff.length > 0 && (
        <div className="lr-scroll"><table className="lr-mini">
          <thead><tr><th>Setting</th><th>Parent</th><th>This run</th></tr></thead>
          <tbody>{diff.map((d) => <tr key={d.key}><td>{d.key}</td><td>{show(d.parent)}</td><td><b>{show(d.value)}</b></td></tr>)}</tbody>
        </table></div>
      )}
      {rationale && (<><h4>Gemini's rationale</h4><blockquote className="lr-quote">{rationale}</blockquote></>)}

      <h4>Data and evaluation</h4>
      <dl className="lr-dl">
        <dt>Training window</dt><dd>{fmtMonth(r.train_from)}–{fmtMonth(r.train_to)} · {fmtCount(m?.split?.n_train)} examples</dd>
        <dt>Held-out set</dt><dd>{m?.holdout?.name ?? '—'} · {fmtMonth(m?.holdout?.start)}–{fmtMonth(m?.holdout?.end)} · {fmtCount(m?.holdout?.n ?? m?.split?.n_test)} cases (frozen, never trained on)</dd>
        {m?.split?.embargo_s != null && <><dt>Gap before test</dt><dd>{horizonLabel(m.split.embargo_s)} so no outcome leaks</dd></>}
        {m?.seconds != null && <><dt>Run time</dt><dd>{Math.round(m.seconds)} s</dd></>}
      </dl>

      {strata.length > 0 && (
        <>
          <h4>Weakest areas vs {vsChampion ? 'the champion' : 'the baseline'}</h4>
          <div className="lr-scroll"><table className="lr-mini">
            <thead><tr><th>Where</th><th>Cases</th><th>{loss}</th><th>Worse by</th></tr></thead>
            <tbody>
              {strata.map((s) => (
                <tr key={`${s.stratum}-${s.value}-${s.horizon_s}`}>
                  <td>{s.value.replace(/_/g, ' ').toLowerCase()} <span className="lr-sub">{s.stratum.replace(/_/g, ' ')}, {horizonLabel(s.horizon_s)}</span></td>
                  <td>{fmtCount(s.n)}</td>
                  <td>{fmtStat(s.cand, unit)} <span className="lr-sub">vs {fmtStat(s.ref, unit)}</span></td>
                  <td>+{fmtStat(s.diff, unit)}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        </>
      )}
    </section>
  )
}

/** Skill over the baseline with its 95 % interval, this run against the champion, per horizon; 0 = no better than the baseline. */
function SkillChart({ rows }: { rows: SkillRow[] }) {
  if (!rows.length) return null
  const domain = pad(extent([0, ...rows.flatMap((r) => [r.lo ?? r.v, r.hi ?? r.v])]), 0.1)
  const dot = (domain[1] - domain[0]) / 300
  const tip = (r: SkillRow) => (
    <>
      <b>{r.who === 'run' ? 'This run' : 'Champion'}, {horizonLabel(r.h)}</b><br />
      {fmtPct(r.v)} skill over the baseline{r.lo != null ? ` [${fmtPct(r.lo)}, ${fmtPct(r.hi)}]` : ''}
      {!r.sameHoldout && <><br />scored on a different held-out set</>}
    </>
  )
  const intervals = rows.filter((r) => r.lo != null && r.hi != null).map((r) => ({ ...r, y: r.key, x0: r.lo!, x1: r.hi!, tone: r.who === 'run' ? 'accent' as const : 'muted' as const }))
  const points = rows.map((r) => ({ ...r, y: r.key, x0: r.v - dot, x1: r.v + dot, tone: 'ink' as const }))
  return (
    <Chart
      label="Skill over the baseline per horizon, this run against the champion, with 95 % intervals"
      x={{ domain, percent: true, ticks: 5 }}
      y={{ type: 'band', domain: rows.map((r) => r.key) }}
      height={24 + rows.length * 26}
      className="lr-chart"
    >
      <RefLine x={0} label="baseline" />
      <Ranges data={intervals} tip={tip} label="95 % interval" />
      <Ranges data={points} tip={tip} label="skill" />
    </Chart>
  )
}

const OUTCOME_LABEL: Record<string, string> = { champion: 'Became champion', candidate: 'Candidate', rejected: 'Run, rejected', invalid: 'Invalid', duplicate: 'Duplicate' }

function ProposalLog({ proposals, runs, onOpen }: { proposals: Proposal[]; runs: Map<string, RunRecord>; onOpen: (id: string) => void }) {
  return (
    <section className="lr-props" aria-labelledby="lr-props-h">
      <h4 id="lr-props-h">Proposals <span className="lr-sub">every change suggested by Gemini or the fixed list, including ones that never ran</span></h4>
      {!proposals.length ? (
        <p className="lr-muted">No proposals yet. The loop's Gemini proposer runs after judging; until then runs come from people and the fixed list.</p>
      ) : (
        <table className="lr-table">
          <thead><tr><th>When</th><th>Model</th><th>By</th><th>Proposed change</th><th>Outcome</th><th>Run</th></tr></thead>
          <tbody>
            {[...proposals].sort((a, b) => b.created_at - a.created_at).map((p) => (
              <tr key={p.id}>
                <td className="lr-mono">{fmtWhen(p.created_at)}</td>
                <td>{targetLabel(p.target)}</td>
                <td>{proposerLabel(p.proposer)}</td>
                <td>
                  <span className="lr-mono">{p.proposal ? Object.entries(p.proposal).map(([k, v]) => `${k} ${show(v)}`).join(', ') : '—'}</span>
                  {p.rationale && <span className="lr-sub">{p.rationale}</span>}
                  {p.errors?.length > 0 && <span className="lr-sub lr-err">{p.errors.join('; ')}</span>}
                </td>
                <td><span className={`lr-status lr-status--${p.outcome}`}>{OUTCOME_LABEL[p.outcome] ?? p.outcome}</span></td>
                <td>
                  {p.run_id && runs.has(p.run_id)
                    ? <button type="button" className="lr-link" onClick={() => onOpen(p.run_id!)}>open run</button>
                    : <span className="lr-muted">{p.run_id ? 'not listed' : 'not run'}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
