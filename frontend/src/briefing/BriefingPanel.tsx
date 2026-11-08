import { briefing, closeBriefing, playVoice, runBriefing } from './store'
import { Button } from '../ui'
import { SaveToSession } from '../collab/docs/SaveToSession'
import { openShipWindow } from '../windows/open'
import { fmtMmsi, utcTime } from '../windows/format'
import './briefing.css'

// AI briefing panel: headline, per-ship findings, cross-ship correlation, optional voiceover.
// Wording rule (see the project): behaviour only, never an accusation; the caveats are always shown.

export function BriefingPanel() {
  const s = briefing.use((x) => x)
  if (!s.open) return null
  const r = s.result
  return (
    <div className="panel briefing" data-zone role="dialog" aria-labelledby="br-title" aria-busy={s.status === 'loading'}>
      <div className="br-head">
        <h2 id="br-title">AI briefing{s.requested.length > 1 ? ` · ${s.requested.length} ships` : ''}</h2>
        <Button className="btn-small" onClick={closeBriefing}>Close</Button>
      </div>

      {s.status === 'loading' && (
        <div className="br-loading" role="status">
          <span className="br-spin" aria-hidden />
          Reading the data for {s.requested.length} {s.requested.length === 1 ? 'ship' : 'ships'}. This takes about 20 seconds.
        </div>
      )}

      {s.status === 'error' && (
        <div className="br-error" role="alert">
          <p>{s.error}</p>
          <Button variant="filled" onClick={() => runBriefing(s.requested)}>Try again</Button>
        </div>
      )}

      {s.status === 'done' && r && (
        <div className="br-body">
          {r.mock && <p className="br-sample">Sample briefing. The live backend is not connected, so nothing below is real.</p>}
          <h3 className="br-headline">{r.summary.headline}</h3>
          <p className="br-overview">{r.summary.overview}</p>

          <div className="br-voice">
            {!r.mock && <SaveToSession briefing={r} />}
            <Button onClick={playVoice} disabled={!r.voice_available && !r.mock} aria-pressed={s.voice === 'playing'}>
              {s.voice === 'loading' ? 'Preparing voiceover…' : s.voice === 'playing' ? 'Stop voiceover' : 'Play voiceover'}
            </Button>
            {!r.voice_available && !r.mock && <span className="br-note">Voiceover is not set up on the server.</span>}
            {s.voiceError && <span className="br-note" role="alert">{s.voiceError}</span>}
          </div>

          {r.summary.correlation.found && (
            <div className="br-corr">
              <b>Link between ships · {r.summary.correlation.strength}</b>
              <span>{r.summary.correlation.explanation}</span>
            </div>
          )}

          <div className="br-ships">
            {r.summary.per_vessel.map((v) => (
              <section key={v.mmsi} className="br-ship">
                <button type="button" className="br-ship-head" onClick={() => openShipWindow(v.mmsi)}>
                  <b>{v.name ?? `MMSI ${fmtMmsi(v.mmsi)}`}</b>
                  <span className={`br-risk br-risk-${v.risk.toLowerCase()}`}>{v.risk}</span>
                </button>
                <ul>{v.findings.map((f, i) => <li key={i}>{f}</li>)}</ul>
                {v.caveats.length > 0 && <ul className="br-caveats">{v.caveats.map((c, i) => <li key={i}>{c}</li>)}</ul>}
              </section>
            ))}
          </div>
          <p className="br-foot">Written by {r.mock ? 'a sample' : r.model} at {utcTime(r.generated_at, false)}. Behaviour only, never an accusation.</p>
        </div>
      )}
    </div>
  )
}
