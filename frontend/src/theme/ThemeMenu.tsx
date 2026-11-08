import { useEffect, useId, useRef, useState } from 'react'
import { Button, Lamp, Panel, Switch } from '../ui'
import { ui } from '../store/ui'
import { resetTheme, setTheme, useTheme, type ThemeState } from './theme'
import './theme.css'

// Display menu, top-right: theme, signal colours, text size and motion, as lamp rows like the layers panel.
const groups = [
  { key: 'theme', label: 'Theme', options: [['light', 'Light (chart)'], ['dark', 'Dark (dusk)'], ['light-hc', 'Light · high contrast'], ['dark-hc', 'Dark · high contrast']] },
  { key: 'signals', label: 'Signal colours', options: [['standard', 'Standard'], ['cvd', 'Colour-blind safe']] },
  { key: 'text', label: 'Text size', options: [['default', 'Default'], ['large', 'Large'], ['largest', 'Largest']] },
] as const

// Theme, contrast, signals, text size, motion and AIS class: the Settings section of the Display panel.
export function ThemeSettings() {
  const state = useTheme()
  const id = useId()
  return (
    <>
      {groups.map((g) => (
        <fieldset key={g.key} className="dvm-theme-menu__group">
          <legend className="dvm-section-label">{g.label}</legend>
          {g.options.map(([value, text]) => {
            const on = state[g.key] === value
            return (
              <label key={value} className="dvm-row" data-state={on ? 'on' : 'off'}>
                <input type="radio" className="dvm-sr" name={`${id}-${g.key}`} checked={on}
                  onChange={() => setTheme({ [g.key]: value } as Partial<ThemeState>)} />
                <Lamp state={on ? 'on' : 'off'} text={false} />
                <span className="dvm-row__text"><span className="dvm-row__label">{text}</span></span>
                <span className="dvm-row__state" aria-hidden="true">{on ? 'on' : ''}</span>
              </label>
            )
          })}
        </fieldset>
      ))}
      <div className="dvm-theme-menu__group">
        <Switch checked={state.reducedMotion} onChange={(v) => setTheme({ reducedMotion: v })} label="Reduce motion" />
        <Switch checked={state.classColour} onChange={(v) => setTheme({ classColour: v })} label="Show AIS class" hint="Class B smaller and violet" />
      </div>
      <div className="dvm-theme-menu__foot">
        <Button variant="ghost" onClick={resetTheme}>Follow system settings</Button>
      </div>
    </>
  )
}

export default function ThemeMenu() {
  const [open, setOpen] = useState(false)
  const id = useId()
  const wrap = useRef<HTMLDivElement>(null)
  const toggle = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      setOpen(false)
      toggle.current?.focus()
    }
    const onDown = (e: PointerEvent) => !wrap.current?.contains(e.target as Node) && setOpen(false)
    document.addEventListener('keydown', onKey)
    document.addEventListener('pointerdown', onDown)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('pointerdown', onDown)
    }
  }, [open])

  return (
    <div ref={wrap} className="dvm-theme-menu" data-zone>
      <Button ref={toggle} className="dvm-menu-toggle" aria-expanded={open} aria-controls={id} onClick={() => { if (!open) ui.set({ watchlistOpen: false, reviewOpen: false, layersOpen: false }); setOpen(!open) }}>
        <Lamp state={open ? 'on' : 'off'} text={false} />
        Display
      </Button>
      {open && (
        <Panel id={id} role="dialog" aria-label="Display settings" className="dvm-theme-menu__panel">
          <ThemeSettings />
        </Panel>
      )}
    </div>
  )
}
