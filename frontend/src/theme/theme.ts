import { createStore } from '../store/store'

// Display modes: theme, signal colour set, text size and motion. Applied as attributes on <html> (tokens.css keys off
// them). Each mode follows the system setting until the user picks one; picks persist in localStorage.
export const THEMES = ['light', 'dark', 'light-hc', 'dark-hc'] as const
export const SIGNAL_SETS = ['standard', 'cvd'] as const
export const TEXT_SIZES = ['default', 'large', 'largest'] as const
export type ThemeName = (typeof THEMES)[number]
export type SignalSet = (typeof SIGNAL_SETS)[number]
export type TextSize = (typeof TEXT_SIZES)[number]
export interface ThemeState { theme: ThemeName; signals: SignalSet; text: TextSize; reducedMotion: boolean }

const KEY = 'dvm-theme' // index.html reads the same key before first paint
const mq = (q: string) => (typeof matchMedia === 'function' ? matchMedia(q) : null)
const prefersDark = mq('(prefers-color-scheme: dark)')
const prefersMore = mq('(prefers-contrast: more)')
const prefersStill = mq('(prefers-reduced-motion: reduce)')

// localStorage is user-editable: keep only values we know.
function readChoice(): Partial<ThemeState> {
  let raw: Record<string, unknown> = {}
  try { raw = JSON.parse(localStorage.getItem(KEY) ?? '{}') ?? {} } catch { /* corrupt or blocked: use system */ }
  const c: Partial<ThemeState> = {}
  if (THEMES.includes(raw.theme as ThemeName)) c.theme = raw.theme as ThemeName
  if (SIGNAL_SETS.includes(raw.signals as SignalSet)) c.signals = raw.signals as SignalSet
  if (TEXT_SIZES.includes(raw.text as TextSize)) c.text = raw.text as TextSize
  if (typeof raw.reducedMotion === 'boolean') c.reducedMotion = raw.reducedMotion
  return c
}

let choice = readChoice()
const resolve = (): ThemeState => ({
  theme: `${prefersDark?.matches ? 'dark' : 'light'}${prefersMore?.matches ? '-hc' : ''}` as ThemeName,
  signals: 'standard',
  text: 'default',
  reducedMotion: !!prefersStill?.matches,
  ...choice,
})

export const themeStore = createStore<ThemeState>(resolve())
export const useTheme = () => themeStore.use((s) => s)

/** Record the user's pick (it stops following the system for those modes) and apply it. */
export function setTheme(patch: Partial<ThemeState>) {
  choice = { ...choice, ...patch }
  try { localStorage.setItem(KEY, JSON.stringify(choice)) } catch { /* private mode: the pick lasts this session */ }
  themeStore.set(resolve())
}

/** Forget the user's picks and follow the system again. */
export function resetTheme() {
  choice = {}
  try { localStorage.removeItem(KEY) } catch { /* nothing stored */ }
  themeStore.set(resolve())
}

for (const m of [prefersDark, prefersMore, prefersStill]) m?.addEventListener('change', () => themeStore.set(resolve()))

function apply(s: ThemeState) {
  const d = document.documentElement.dataset
  d.theme = s.theme
  d.signals = s.signals
  d.text = s.text
  d.motion = s.reducedMotion ? 'reduce' : 'full' // CSS uses [data-motion=reduce] so the user's pick beats the media query
}

apply(themeStore.get())
themeStore.subscribe((s, prev) => {
  const looks = s.theme !== prev.theme || s.signals !== prev.signals || s.text !== prev.text
  // Crossfade: the browser snapshots the old page and fades it out over the new one (opacity only, on the compositor).
  // shortcut: browsers without View Transitions switch instantly; add an overlay fallback if one of them matters.
  if (looks && !s.reducedMotion && 'startViewTransition' in document && document.visibilityState === 'visible') {
    document.startViewTransition(() => apply(s))
  } else apply(s)
})
