// shortcut: local stand-in for src/theme/tokens.ts (tokens agent). Same API, so integration is changing the import
// path in map/ and deleting this file. Reads --dvm-* from <html>; falls back to R1-AGENT1-COLOUR.md values.

type Theme = 'light' | 'dark' | 'light-hc' | 'dark-hc'
const T = (light: string, dark: string, lightHc: string, darkHc: string) => ({ light, dark, 'light-hc': lightHc, 'dark-hc': darkHc })

const THEME: Record<string, Record<Theme, string>> = {
  'bg-app': T('#f3efe4', '#15232d', '#ffffff', '#0c171e'),
  'bg-panel': T('#fbf8f1', '#1c2d38', '#ffffff', '#0f1c24'),
  'border-default': T('#b9b09b', '#4a6474', '#4a4740', '#a9bcc6'),
  'text-primary': T('#1d2529', '#eee9dc', '#000000', '#ffffff'),
  'text-muted': T('#5d6466', '#a5a99f', '#33393c', '#d2cdbf'),
  'accent-default': T('#1c5f86', '#86c9e8', '#0b4468', '#a6dbf3'),
  'map-water': T('#d6e6ec', '#1f3b4b', '#e4f1f6', '#132b38'),
  'map-land': T('#efe4c6', '#3b3a32', '#f3e2b2', '#3e3c32'),
  'map-coast': T('#3f4b4f', '#c3cccb', '#000000', '#f2f2ec'),
  'coverage-dead': T('rgba(107,114,117,0.22)', 'rgba(141,150,154,0.24)', 'rgba(61,67,70,0.30)', 'rgba(163,171,175,0.30)'),
  'focus-dim-opacity': T('0.40', '0.45', '0.35', '0.35'),
}
// DVM Signals: [standard, colour-blind safe] per theme.
const SIGNAL: Record<string, Record<Theme, [string, string]>> = {
  'ship-normal': { light: ['#1d2529', '#1d2529'], dark: ['#eee9dc', '#eee9dc'], 'light-hc': ['#000000', '#000000'], 'dark-hc': ['#ffffff', '#ffffff'] },
  'ship-selected': { light: ['#1c5f86', '#0c63e1'], dark: ['#86c9e8', '#95cee9'], 'light-hc': ['#0b4468', '#0f3f6a'], 'dark-hc': ['#a6dbf3', '#39c1f9'] },
  'ship-dark': { light: ['#b3266b', '#522a03'], dark: ['#f26aa0', '#c98269'], 'light-hc': ['#8f0f4e', '#4e2b02'], 'dark-hc': ['#ff7fb0', '#f59453'] },
  'ship-spoof': { light: ['#9a6400', '#807a03'], dark: ['#f2b33d', '#beaf3a'], 'light-hc': ['#6e4700', '#7c7d18'], 'dark-hc': ['#ffc24d', '#e5cd11'] },
  'ship-sanctioned': { light: ['#c2331c', '#c64b8a'], dark: ['#ff7650', '#ff5aa8'], 'light-hc': ['#9a2010', '#d209d0'], 'dark-hc': ['#ff8a63', '#fb4c95'] },
}

export function currentTheme(): Theme {
  const t = document.documentElement.dataset.theme as Theme | undefined
  return t && t in THEME['bg-app'] ? t : 'dark'
}

// name: '--dvm-ship-dark' style. Resolved value, or the fallback for the current modes.
export function readToken(name: string): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  if (v) return v
  const key = name.replace(/^--dvm-/, '')
  const theme = currentTheme()
  if (key === 'ship-keyline') return readToken('--dvm-bg-app')
  if (THEME[key]) return THEME[key][theme]
  if (SIGNAL[key]) return SIGNAL[key][theme][document.documentElement.dataset.signals === 'cvd' ? 1 : 0]
  return '#ff00ff'
}

// Fires when any mode attribute on <html> changes (theme, signals, text size) or a stylesheet swaps tokens.
export function onTokensChange(cb: () => void): () => void {
  const obs = new MutationObserver(cb)
  obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'data-signals', 'data-text', 'style', 'class'] })
  return () => obs.disconnect()
}
