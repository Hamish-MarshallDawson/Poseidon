import { Chart, Legend, Markers, Ranges, RefLine, extent, pad } from './charts'
import { baselineOf, calValue, count, horizon, interval, proposerLabel, signedPct, sourceLabel, when } from './format'
import { liveComparison, recordedOffline, type SkillFigure, type SkillRunLike } from './skill'
import type { ModelSummary, Summary } from './types'

// One card per model (champion, since when, offline skill with its interval, live primary metric and calibration
// with pass/fail written out, deployed or not), then the totals strip and the improvement cycle's state.

export function Overview({ summary, runs = [] }: { summary: Summary | null; runs?: SkillRunLike[] }) {
  if (!summary) return <p className="lab-muted" role="status">Loading the models…</p>
  const { totals, cycle } = summary
  return (
    <section className="lab-overview" aria-label="Models at a glance">
      <div className="lab-cards">
        {summary.models.map((m) => <ModelCard key={m.target} m={m} runs={runs} />)}
      </div>
      <dl className="lab-totals">
        <div><dt>Training runs</dt><dd>{count(totals.runs)}</dd></div>
        <div><dt>Gemini proposals</dt><dd>{count(totals.proposals)}</dd></div>
        <div><dt>Graded outcomes</dt><dd title={totals.graded_outcomes_estimated ? 'an estimate: past the exact-count limit the database planner\'s count is shown' : undefined}>{totals.graded_outcomes_estimated ? '~' : ''}{count(totals.graded_outcomes)} <span>+{count(totals.graded_last_hour)} last hour</span></dd></div>
        <div>
          <dt>Improvement cycle</dt>
          <dd>{cycle.state === 'scheduled' ? 'Scheduled' : 'Run by hand'} <span>{cycle.last ? `last ${when(cycle.last)}` : 'not run yet'}{cycle.next ? `, next ${when(cycle.next)}` : ''}</span></dd>
        </div>
      </dl>
    </section>
  )
}

export function ModelCard({ m, runs = [] }: { m: ModelSummary; runs?: SkillRunLike[] }) {
  const base = baselineOf(m.target)
  // The champion's held-out figure as recorded, labelled with its statistic (offline.statistic). The strip below
  // pairs live with the held-out number on the live statistic instead.
  const off = recordedOffline(m, runs)
  const h = horizon(off?.h ?? m.offline.primary_h)
  const iv = interval(off?.lo, off?.hi)
  const cal = m.live?.calibration
  return (
    <article className="lab-card" aria-labelledby={`lab-card-${m.target}`}>
      <header>
        <h3 id={`lab-card-${m.target}`}>{m.label}</h3>
        <span className={`lab-pill ${m.deployed ? 'on' : ''}`}>{m.deployed ? 'Live on the map' : 'Not deployed'}</span>
      </header>
      <p className="lab-card__champ">
        <span className="lab-k">Champion</span>
        <code>{m.champion.version}</code>
        <span className="lab-muted">since {m.champion.since ? when(m.champion.since) : 'unknown'} · {proposerLabel(m.champion.proposer)} on {sourceLabel(m.champion.source)}</span>
      </p>
      <div className="lab-card__row">
        <span className="lab-k">Held-out test</span>
        {off == null ? (
          <p>No held-out skill recorded for this champion.{m.offline.holdout ? <span className="lab-muted"> Tested on {m.offline.holdout}.</span> : null}</p>
        ) : (
          <p>
            <b className="lab-num">{signedPct(off.skill)}</b> {off.name} over {base} at {h}
            <span className="lab-muted"> {iv ? `95% interval ${iv}` : 'no interval recorded'}{m.offline.holdout ? ` · ${m.offline.holdout}` : ''}</span>
          </p>
        )}
      </div>
      <div className="lab-card__row">
        <span className="lab-k">Live, last {m.live?.hours ?? 24} h</span>
        {!m.live ? (
          <p className="lab-muted">{m.deployed ? 'No live grades for this version yet.' : 'Not graded live.'}</p>
        ) : (
          <>
            <p>
              <b className="lab-num">{m.live.primary.value == null ? 'n/a' : signedPct(m.live.primary.value)}</b> {m.live.primary.name}
              <span className="lab-muted"> · {count(m.live.n)} graded, against {m.live.primary.ref_label}</span>
            </p>
            {cal && (
              <p className={`lab-check ${cal.ok ? 'pass' : cal.ok === false ? 'fail' : ''}`}>
                <span className="lab-check__mark" aria-hidden>{cal.ok ? '✓' : cal.ok === false ? '✗' : '–'}</span>
                <span>
                  <b>{cal.ok ? 'Pass' : cal.ok === false ? 'Off target' : 'Not checked'}</b>{' '}
                  {cal.name}: {calValue(cal.name, cal.value)}{cal.nominal != null ? ` (target ${calValue(cal.name, cal.nominal)})` : ''}
                </span>
              </p>
            )}
          </>
        )}
      </div>
      <SkillStrip m={m} runs={runs} />
      {m.note && <p className="lab-card__note">{m.note}</p>}
    </article>
  )
}

/** Live skill next to the held-out skill on the same statistic at the same horizon (the backend's live.offline), with
 *  zero (no better than the baseline) marked. When the run has no such held-out number only the live point is drawn;
 *  with no live grades, the recorded held-out figure alone. Never two statistics or horizons on one axis. */
function SkillStrip({ m, runs }: { m: ModelSummary; runs: SkillRunLike[] }) {
  const cmp = liveComparison(m, runs)
  const fig: SkillFigure | null = cmp ? cmp.offline : recordedOffline(m, runs)
  const liveFig = cmp?.live ?? null
  const off = fig?.skill ?? null
  const live = liveFig?.skill ?? null
  if (off == null && live == null) return null
  const base = baselineOf(m.target)
  const h = horizon((liveFig ?? fig)!.h)
  const stat = (liveFig ?? fig)!.name
  const rows = [...(off != null ? ['held-out'] : []), ...(live != null ? ['live'] : [])]
  const lo = fig?.lo ?? null, hi = fig?.hi ?? null
  const dom = pad(extent([0, off, lo, hi, live]), 0.12)
  const iv = off != null && lo != null && hi != null ? [{ y: 'held-out', x0: lo, x1: hi }] : []
  const pts = [
    ...(off != null ? [{ x: off, y: 'held-out', tone: 'accent' as const, shape: 'circle' as const, what: `Held-out test, ${h}` }] : []),
    ...(live != null ? [{ x: live, y: 'live', tone: live < 0 ? ('bad' as const) : ('ink' as const), shape: 'diamond' as const, what: `Live, last ${m.live?.hours ?? 24} h` }] : []),
  ]
  return (
    <figure className="lab-strip">
    <Chart label={`${m.label}: ${stat} over ${base} at ${h}, held-out ${signedPct(off)} and live ${signedPct(live)}`}
      height={rows.length * 26 + 24} x={{ domain: dom, percent: true, ticks: 4, noGrid: true }} y={{ type: 'band', domain: rows }} margin={{ top: 4, bottom: 18 }}>
      <RefLine x={0} label="no skill" />
      <Ranges data={iv} tone="accent" thickness={8} tip={(d) => <>95% interval {interval(d.x0, d.x1)}</>} />
      <Markers data={pts} size={4.5} tip={(p) => <><b>{p.what}</b>: {signedPct(p.x)} {stat} over {base} at {h}</>} label="skill" />
    </Chart>
    <figcaption><Legend items={[
      ...(off != null ? [{ label: `held-out test, ${h}`, tone: 'accent' as const, kind: 'circle' as const }] : []),
      ...(iv.length ? [{ label: '95% interval', tone: 'accent' as const, kind: 'band' as const }] : []),
      ...(live != null ? [{ label: `live, last ${m.live?.hours ?? 24} h`, tone: live < 0 ? ('bad' as const) : ('ink' as const), kind: 'diamond' as const }] : []),
      { label: `${stat} over ${base} at ${h}; left of 0 is worse`, tone: 'muted' as const, kind: 'dashed' as const },
    ]} />{cmp && off == null && live != null ? <span className="lab-muted"> No held-out {stat} at {h} recorded for this run, so nothing to compare against.</span> : null}</figcaption>
    </figure>
  )
}
