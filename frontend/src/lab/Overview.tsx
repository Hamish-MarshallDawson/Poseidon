import { Chart, Legend, Markers, Ranges, RefLine, extent, pad } from './charts'
import { baselineOf, calValue, count, horizon, interval, proposerLabel, signedPct, sourceLabel, when } from './format'
import type { ModelSummary, Summary } from './types'

// One card per model (champion, since when, offline skill with its interval, live primary metric and calibration
// with pass/fail written out, deployed or not), then the totals strip and the improvement cycle's state.

export function Overview({ summary }: { summary: Summary | null }) {
  if (!summary) return <p className="lab-muted" role="status">Loading the models…</p>
  const { totals, cycle } = summary
  return (
    <section className="lab-overview" aria-label="Models at a glance">
      <div className="lab-cards">
        {summary.models.map((m) => <ModelCard key={m.target} m={m} />)}
      </div>
      <dl className="lab-totals">
        <div><dt>Training runs</dt><dd>{count(totals.runs)}</dd></div>
        <div><dt>Gemini proposals</dt><dd>{count(totals.proposals)}</dd></div>
        <div><dt>Graded outcomes</dt><dd>{count(totals.graded_outcomes)} <span>+{count(totals.graded_last_hour)} last hour</span></dd></div>
        <div>
          <dt>Improvement cycle</dt>
          <dd>{cycle.state === 'scheduled' ? 'Scheduled' : 'Run by hand'} <span>{cycle.last ? `last ${when(cycle.last)}` : 'not run yet'}{cycle.next ? `, next ${when(cycle.next)}` : ''}</span></dd>
        </div>
      </dl>
    </section>
  )
}

export function ModelCard({ m }: { m: ModelSummary }) {
  const base = baselineOf(m.target)
  const h = horizon(m.offline.primary_h)
  const iv = interval(m.offline.skill_lo, m.offline.skill_hi)
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
        {m.offline.skill == null ? (
          <p>No held-out skill recorded for this champion.{m.offline.holdout ? <span className="lab-muted"> Tested on {m.offline.holdout}.</span> : null}</p>
        ) : (
          <p>
            <b className="lab-num">{signedPct(m.offline.skill)}</b> skill over {base} at {h}
            <span className="lab-muted"> {iv ? `95% interval ${iv}` : 'no interval recorded'}{m.offline.holdout ? ` · ${m.offline.holdout}` : ''}</span>
          </p>
        )}
      </div>
      <div className="lab-card__row">
        <span className="lab-k">Live, last {m.live?.hours ?? 24} h</span>
        {!m.live ? (
          <p className="lab-muted">Not graded live.</p>
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
      <SkillStrip m={m} />
      {m.note && <p className="lab-card__note">{m.note}</p>}
    </article>
  )
}

/** Held-out skill (with its interval) against live skill on one axis, with zero (no better than the baseline) marked. */
function SkillStrip({ m }: { m: ModelSummary }) {
  const off = m.offline.skill
  const live = m.live?.primary.value ?? null
  if (off == null && live == null) return null
  const rows = [...(off != null ? ['held-out'] : []), ...(live != null ? ['live'] : [])]
  const dom = pad(extent([0, off, m.offline.skill_lo, m.offline.skill_hi, live]), 0.12)
  const iv = m.offline.skill_lo != null && m.offline.skill_hi != null ? [{ y: 'held-out', x0: m.offline.skill_lo, x1: m.offline.skill_hi }] : []
  const pts = [
    ...(off != null ? [{ x: off, y: 'held-out', tone: 'accent' as const, shape: 'circle' as const, what: 'Held-out test' }] : []),
    ...(live != null ? [{ x: live, y: 'live', tone: live < 0 ? ('bad' as const) : ('ink' as const), shape: 'diamond' as const, what: `Live, last ${m.live?.hours ?? 24} h` }] : []),
  ]
  return (
    <figure className="lab-strip">
    <Chart label={`${m.label}: held-out skill ${signedPct(off)} and live ${signedPct(live)} over ${baselineOf(m.target)}`}
      height={rows.length * 26 + 24} x={{ domain: dom, percent: true, ticks: 4, noGrid: true }} y={{ type: 'band', domain: rows }} margin={{ top: 4, bottom: 18 }}>
      <RefLine x={0} label="no skill" />
      <Ranges data={iv} tone="accent" thickness={8} tip={(d) => <>95% interval {interval(d.x0, d.x1)}</>} />
      <Markers data={pts} size={4.5} tip={(p) => <><b>{p.what}</b>: {signedPct(p.x)} over {baselineOf(m.target)}</>} label="skill" />
    </Chart>
    <figcaption><Legend items={[
      ...(off != null ? [{ label: 'held-out test', tone: 'accent' as const, kind: 'circle' as const }] : []),
      ...(iv.length ? [{ label: '95% interval', tone: 'accent' as const, kind: 'band' as const }] : []),
      ...(live != null ? [{ label: `live, last ${m.live?.hours ?? 24} h`, tone: live < 0 ? ('bad' as const) : ('ink' as const), kind: 'diamond' as const }] : []),
      { label: `skill over ${baselineOf(m.target)}; left of 0 is worse`, tone: 'muted' as const, kind: 'dashed' as const },
    ]} /></figcaption>
    </figure>
  )
}
