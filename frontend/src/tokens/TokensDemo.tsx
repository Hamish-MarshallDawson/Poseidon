import { useEffect, useState } from 'react'
import tokens from './tokens.json'
import { useTheme } from '../theme/theme'
import { onTokensChange, readToken } from '../theme/tokens'
import ThemeMenu from '../theme/ThemeMenu'
import { Button, Chip, IconButton, Kbd, Lamp, Panel, Switch, Tooltip } from '../ui'
import './demo.css'

// Review page at ?demo=tokens: every token in the current modes, a map specimen and the base components.
// Switch modes with the Display menu (top right) and compare with the Figma specimens on page 39:448.

function Swatch({ name }: { name: string }) {
  const value = readToken(name)
  return (
    <div className="demo-swatch">
      <span className="demo-swatch__chip" style={{ background: `var(${name})` }} />
      <code>{name.slice(6)}</code>
      <code className="t-muted">{value}</code>
    </div>
  )
}

const signalNames = Object.keys(tokens.signals)
const roles = ['caption', 'label', 'data', 'body', 'heading', 'title', 'display']

export default function TokensDemo() {
  const mode = useTheme()
  const [, setTick] = useState(0)
  useEffect(() => onTokensChange(() => setTick((t) => t + 1)), []) // re-read resolved values after a mode change
  const [sw, setSw] = useState({ density: true, coverage: true, inland: false })

  return (
    <div className="demo">
      <ThemeMenu />
      <header className="demo-head">
        <h1 className="t-display">POSEIDON · tokens</h1>
        <p className="t-data t-secondary">
          theme={mode.theme} · signals={mode.signals} · text={mode.text} · motion={mode.reducedMotion ? 'reduce' : 'full'}
        </p>
      </header>

      <section>
        <h2 className="dvm-section-label">Map specimen</h2>
        <svg className="demo-map" viewBox="0 0 480 220" role="img" aria-label="Map specimen with every ship state">
          <rect width="480" height="220" fill="var(--dvm-map-water)" />
          {[60, 140, 220].map((y) => <line key={y} x1="0" x2="480" y1={y} y2={y} stroke="var(--dvm-map-grid)" />)}
          <path d="M330 0 L480 0 L480 220 L360 220 L340 160 L370 110 L330 60 Z" fill="var(--dvm-map-land)" stroke="var(--dvm-map-coast)" />
          <path d="M420 0 L430 220" stroke="var(--dvm-map-border)" strokeDasharray="6 3 1 3" fill="none" />
          <rect x="40" y="150" width="120" height="50" fill="var(--dvm-coverage-dead)" />
          <rect x="160" y="150" width="120" height="50" fill="var(--dvm-coverage-degraded)" />
          <text x="60" y="40" fill="var(--dvm-map-label-water)" fontFamily="var(--dvm-font-place)" fontStyle="italic" fontSize="16">North Sea</text>
          <text x="390" y="100" fill="var(--dvm-map-label-land)" fontFamily="var(--dvm-font-place)" fontSize="12" letterSpacing="2">NORWAY</text>
          <circle cx="60" cy="90" r="4" fill="var(--dvm-ship-normal)" opacity="var(--dvm-opacity-routine)" />
          <g stroke="var(--dvm-ship-selected)" strokeWidth="2" fill="none">
            <path d="M100 82 h-6 v6 M110 82 h6 v6 M100 98 h-6 v-6 M110 98 h6 v-6" />
          </g>
          <circle cx="105" cy="90" r="4" fill="var(--dvm-ship-normal)" />
          <circle cx="170" cy="90" r="28" fill="var(--dvm-ship-ghost-fill)" stroke="var(--dvm-ship-ghost-edge)" strokeDasharray="4 3" />
          <circle cx="160" cy="84" r="4" fill="none" stroke="var(--dvm-ship-dark)" strokeWidth="1.5" />
          <circle cx="240" cy="90" r="4" fill="var(--dvm-ship-spoof)" />
          <line x1="240" y1="90" x2="270" y2="70" stroke="var(--dvm-ship-spoof)" strokeDasharray="2 2" />
          <circle cx="270" cy="70" r="4" fill="none" stroke="var(--dvm-ship-spoof)" strokeWidth="1.5" />
          <circle cx="300" cy="110" r="4" fill="var(--dvm-ship-normal)" />
          <path d="M306 100 l4 4 l-4 4 l-4 -4 z" fill="var(--dvm-ship-sanctioned)" stroke="var(--dvm-ship-keyline)" />
          <circle cx="80" cy="120" r="4" fill="var(--dvm-focus-dim-ship)" opacity="var(--dvm-focus-dim-opacity)" />
        </svg>
        <div className="demo-row">
          {[1, 2, 3, 4].map((n) => <span key={n} className="demo-ramp" style={{ background: `var(--dvm-risk-${n})` }} />)}
          <span className="t-label t-muted">risk 1 → 4</span>
        </div>
      </section>

      <section>
        <h2 className="dvm-section-label">DVM Theme</h2>
        <div className="demo-grid">{Object.keys(tokens.theme).map((n) => <Swatch key={n} name={n} />)}</div>
      </section>

      <section>
        <h2 className="dvm-section-label">DVM Signals ({mode.signals})</h2>
        <div className="demo-grid">{signalNames.map((n) => <Swatch key={n} name={n} />)}</div>
      </section>

      <section>
        <h2 className="dvm-section-label">Aliases and constants</h2>
        <div className="demo-grid">
          {Object.keys(tokens.constants).map((n) => (
            <div key={n} className="demo-swatch">
              <span className="demo-swatch__chip" style={n.includes('opacity') ? { background: 'var(--dvm-ship-normal)', opacity: `var(${n})` } : { background: `var(${n})` }} />
              <code>{n.slice(6)}</code>
              <code className="t-muted">{readToken(n)}</code>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="dvm-section-label">DVM Text size ({mode.text})</h2>
        {roles.map((r) => (
          <p key={r} className={`t-${r} demo-type`}>
            <code className="t-muted">{r} {readToken(`size-${r}`)}/{readToken(`line-${r}`)}</code> Ranked for review · next 6 h
          </p>
        ))}
        <p className="t-water t-title demo-type">North Sea</p>
        <p className="t-place t-body demo-type">Bergen</p>
      </section>

      <section>
        <h2 className="dvm-section-label">Components</h2>
        <div className="demo-row">
          <Button variant="filled">Sign in with Auth0</Button>
          <Button variant="outline">Show all</Button>
          <Button variant="outline" aria-pressed="true">Pressed</Button>
          <Button variant="ghost">Show less</Button>
          <Button variant="outline" disabled>Disabled</Button>
          <Tooltip content="Layers and filters">
            <IconButton label="Layers">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor"><path d="M8 2 15 6 8 10 1 6Z M1 9.5 8 13.5 15 9.5" /></svg>
            </IconButton>
          </Tooltip>
          <span className="t-label t-secondary">Close <Kbd>Esc</Kbd> · focus <Kbd>F</Kbd></span>
        </div>
        <div className="demo-row">
          <Chip kind="replay">Replay</Chip>
          <Chip>AS OF 13:05:12Z</Chip>
          <Chip>Nearby</Chip>
          {[1, 2, 3, 4].map((n) => <Chip key={n} kind="signal" signal={`risk-${n}`}>{n * 20 + 4}%</Chip>)}
          <Lamp state="on" />
          <Lamp state="off" />
          <Lamp state="na" />
        </div>
        <Panel className="demo-panel">
          <p className="dvm-section-label demo-pad">Map</p>
          <Switch checked={sw.density} onChange={(v) => setSw({ ...sw, density: v })} label="Density view" hint="0.1° cells from coverage_1m" />
          <Switch checked={sw.coverage} onChange={(v) => setSw({ ...sw, coverage: v })} label="Coverage gaps" hint="hatch where no receiver heard anything in 10 min" />
          <Switch checked={sw.inland} onChange={(v) => setSw({ ...sw, inland: v })} label="Inland vessels" hint="Rhine, Danube and other inland waterways" />
          <Switch checked={false} unavailable label="Same owner / operator" hint="needs a data source" />
        </Panel>
      </section>
    </div>
  )
}
