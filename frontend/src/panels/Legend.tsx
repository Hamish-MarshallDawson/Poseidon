import type { CSSProperties, ReactNode } from 'react'
import { ui } from '../store/ui'
import { useTheme } from '../theme/theme'
import { usePresence } from '../motion'
import hullTanker from './glyphs/hull-tanker.svg'
import hullCargo from './glyphs/hull-cargo.svg'
import hullFishing from './glyphs/hull-fishing.svg'
import hullPassenger from './glyphs/hull-passenger.svg'
import hullOther from './glyphs/hull-other.svg'
import hullDark from './glyphs/hull-dark.svg'
import spoofImplied from './glyphs/spoof-implied.svg'
import spoofReported from './glyphs/spoof-reported.svg'
import sanctioned from './glyphs/overlay-sanctioned.svg'
import hatch from './glyphs/hatch.svg'
import lastCourse from './glyphs/last-course.svg'
import hullGhost from './glyphs/hull-ghost.svg'
import cross from './glyphs/cross.svg'
import hullBack from './glyphs/hull-back.svg'
import hullFront from './glyphs/hull-front.svg'
import noReceiver from './glyphs/no-receiver.svg'

// Legend toggle (R2/Legend/Toggle 56:3123) and the compact panel (R2/Legend/Panel 56:95), opening upward
// from the bottom-left with an 8 px gap. Glyphs are the Figma symbols used as CSS masks and painted with the
// signal tokens, so they follow theme and colour-blind mode like the map does.

// One masked symbol at its Figma position inside the 48 × 40 water tile.
function G({ src, color, s }: { src: string; color: string; s: CSSProperties }) {
  return <i className="g" style={{ ...s, background: `var(${color})`, maskImage: `url("${src}")`, WebkitMaskImage: `url("${src}")` }} />
}
const HULL = { left: 17, top: 3, width: 12, height: 32 }
const MARK = { left: 17, top: 3, width: 12, height: 32 }

function Tile({ children, replay }: { children?: ReactNode; replay?: boolean }) {
  return <span className={`tile ${replay ? 'tile-replay' : ''}`} aria-hidden>{children}</span>
}

function Entry({ label, children, extra }: { label: string; children: ReactNode; extra?: ReactNode }) {
  return (
    <li className="lg-entry">
      {children}
      <span className="lg-label">{label}{extra}</span>
    </li>
  )
}

function LegendPanel() {
  const byClass = useTheme().classColour
  return (
    <div className="panel legend" id="legend-panel" role="region" aria-label="Legend">
      <h2 className="lg-title">Legend</h2>
      <ul className="lg-ships">
        {([['Tanker', hullTanker], ['Cargo', hullCargo], ['Fishing', hullFishing], ['Passenger', hullPassenger], ['Other', hullOther]] as const).map(([label, src]) => (
          <li key={label}><Tile><G src={src} color="--dvm-ship-normal" s={HULL} /></Tile><span>{label}</span></li>
        ))}
      </ul>
      {byClass && <p className="lg-note">Class A: commercial and SOLAS ships, used for gap detection. Class B: small craft and leisure, drawn smaller.</p>}
      <ul className="lg-grid">
        <Entry label="Normal"><Tile><G src={hullCargo} color="--dvm-ship-normal" s={MARK} /></Tile></Entry>
        {byClass && <Entry label="Class A"><Tile><G src={hullCargo} color="--dvm-ship-class-a" s={MARK} /></Tile></Entry>}
        {byClass && <Entry label="Class B"><Tile><G src={hullCargo} color="--dvm-ship-class-b" s={{ left: 19.5, top: 9, width: 9, height: 24 }} /></Tile></Entry>}
        <Entry label="No AIS received"><Tile><G src={hullDark} color="--dvm-ship-dark" s={MARK} /></Tile></Entry>
        <Entry label="Possible spoofing">
          <Tile>
            <G src={spoofImplied} color="--dvm-ship-spoof" s={{ left: 20.5, top: -0.5, width: 12, height: 32 }} />
            <G src={spoofReported} color="--dvm-ship-spoof" s={{ left: 13.5, top: 6.5, width: 12, height: 32 }} />
          </Tile>
        </Entry>
        <Entry label="Sanctions match">
          <Tile>
            <G src={hullCargo} color="--dvm-ship-normal" s={MARK} />
            <G src={sanctioned} color="--dvm-ship-sanctioned" s={{ left: 34.6, top: -2.4, width: 9.8, height: 9.8 }} />
          </Tile>
        </Entry>
        <Entry label="Heard, inferred">
          <Tile><i className="g-heard" /><i className="g-inferred" /></Tile>
        </Entry>
        <Entry label="Could be in here">
          <Tile>
            <span className="g-ghost">
              {/* The hatch sheet's lines start 1,183 px in; Figma centres it 600 px right of the circle. */}
              <G src={hatch} color="--dvm-ship-dark" s={{ inset: 0, maskSize: '3600px 1200px', WebkitMaskSize: '3600px 1200px', maskPosition: '-1183px -583px', WebkitMaskPosition: '-1183px -583px' }} />
            </span>
            <G src={lastCourse} color="--dvm-ship-dark" s={{ left: 22.8, top: 13.9, width: 14.2, height: 5.6 }} />
            <G src={hullGhost} color="--dvm-ship-dark" s={{ left: 17, top: 3, width: 12, height: 32, transform: 'rotate(74deg)' }} />
            <G src={cross} color="--dvm-ship-dark" s={{ left: 17.3, top: 13.3, width: 11.4, height: 11.4 }} />
          </Tile>
        </Entry>
        <Entry label={'Chance, next 6\u00a0h'}>
          <Tile><span className="g-tag"><i className="risk-3" />3</span></Tile>
        </Entry>
        <Entry label="Stacked ships">
          <Tile>
            <span className="g-stack">
              <span className="g-stack-glyph">
                <G src={hullBack} color="--dvm-ship-normal" s={{ left: 7, top: 0, width: 5.6, height: 11.2 }} />
                <G src={hullFront} color="--dvm-ship-normal" s={{ left: 1.7, top: 1.1, width: 5.6, height: 11.2 }} />
              </span>
              12
            </span>
          </Tile>
        </Entry>
        <Entry label="No receiver here">
          <Tile><G src={noReceiver} color="--dvm-text-muted" s={{ left: 5, top: 5, width: 36, height: 28 }} /></Tile>
        </Entry>
        <Entry label="Replay" extra={<span className="replay-chip">REPLAY</span>}><Tile replay /></Entry>
      </ul>
    </div>
  )
}

export function Legend() {
  const open = ui.use((s) => s.legendOpen)
  const { mounted, attach } = usePresence(open, { y: 12, opacity: 0 })
  return (
    <>
      <button type="button" className={`legend-toggle ${open ? 'on' : ''}`} aria-expanded={open} aria-controls="legend-panel"
        onClick={() => ui.set((s) => ({ legendOpen: !s.legendOpen }))}>
        <span className="lt-icon" aria-hidden><i /><i /><i /></span>
        Legend
        <span className="lamp" aria-hidden />
      </button>
      {mounted && <div className="legend-wrap" ref={attach}><LegendPanel /></div>}
    </>
  )
}
