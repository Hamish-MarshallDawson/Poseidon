// Token access for code that can't use CSS variables directly (MapLibre paint, canvas). Colours resolve to hex
// (#rrggbb or #rrggbbaa), which MapLibre accepts.

const prop = (name: string) => (name.startsWith('--') ? name : `--dvm-${name.replaceAll('/', '-')}`)

/** Current value of a token, e.g. readToken('ship-dark') or readToken('--dvm-ship-dark') or readToken('ship/dark'). */
export function readToken(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(prop(name)).trim()
}

/** Calls cb after any mode change (theme, signals, text size), once per change. Returns an unsubscribe. */
export function onTokensChange(cb: () => void): () => void {
  const mo = new MutationObserver(() => cb())
  mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'data-signals', 'data-text'] })
  return () => mo.disconnect()
}
