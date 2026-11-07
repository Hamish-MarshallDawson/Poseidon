// Renders ?demo=tokens in every one of the 24 mode combinations, reads the resolved tokens from the page and
// checks WCAG contrast for spot-check pairs, then times a theme switch. Needs the dev server:
//   npm run dev -- --port 5174 --strictPort   then   node scripts/tokens/check.mjs [url]
import { chromium } from 'playwright-core'

const url = process.argv[2] ?? 'http://localhost:5174/?demo=tokens'
const themes = ['light', 'dark', 'light-hc', 'dark-hc'], sets = ['standard', 'cvd'], texts = ['default', 'large', 'largest']
// [foreground, background, minimum ratio]
const pairs = [
  ['text-muted', 'bg-raised', 4.5],
  ['text-primary', 'bg-panel', 4.5],
  ['text-on-accent', 'accent-default', 4.5],
  ['map-label-water', 'map-water', 4.5],
  ['ship-dark', 'map-water-alt', 3],
  ['ship-sanctioned', 'map-water-alt', 3],
]

const lum = (hex) => {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((x) => (x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4))
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
}
const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05) }
console.assert(Math.abs(ratio('#000000', '#ffffff') - 21) < 1e-9, 'contrast self-check')

const browser = await chromium.launch({ channel: process.env.SMOKE_BROWSER ?? 'msedge', headless: true })
const page = await browser.newPage()
const errors = []
page.on('pageerror', (e) => errors.push(String(e)))
await page.goto(url)
await page.waitForSelector('.demo')

let fails = 0
const rows = {}
for (const theme of themes) for (const signals of sets) for (const text of texts) {
  const got = await page.evaluate(([theme, signals, text, names]) => {
    const d = document.documentElement.dataset
    Object.assign(d, { theme, signals, text })
    const cs = getComputedStyle(document.documentElement)
    return Object.fromEntries([...names, 'size-body'].map((n) => [n, cs.getPropertyValue(`--dvm-${n}`).trim()]))
  }, [theme, signals, text, [...new Set(pairs.flat().filter((x) => typeof x === 'string'))]])
  for (const [k, v] of Object.entries(got)) if (!v) { fails++; console.log(`MISSING ${k} in ${theme}/${signals}/${text}`) }
  if (text !== 'default') continue // sizes don't change colours
  for (const [fg, bg, min] of pairs) {
    const r = ratio(got[fg], got[bg])
    const key = `${fg} on ${bg} (≥${min})`
    ;(rows[key] ??= {})[`${theme}/${signals}`] = r
    if (r < min) { fails++; console.log(`FAIL ${key} ${theme}/${signals}: ${r.toFixed(2)}`) }
  }
}

console.log(`\n| pair | ${themes.flatMap((t) => sets.map((s) => `${t}/${s}`)).join(' | ')} |`)
console.log(`|---|${themes.flatMap(() => sets.map(() => '---')).join('|')}|`)
for (const [key, by] of Object.entries(rows)) console.log(`| ${key} | ${Object.values(by).map((r) => r.toFixed(2)).join(' | ')} |`)

// Theme switch: frame times while the crossfade runs (rAF deltas over 600 ms).
await page.evaluate(() => { localStorage.removeItem('dvm-theme') })
await page.reload()
await page.waitForSelector('.demo')
const sw = await page.evaluate(async () => {
  const { setTheme } = await import('/src/theme/theme.ts')
  setTheme({ theme: 'light' })
  await new Promise((r) => setTimeout(r, 500))
  const times = []
  const start = performance.now()
  await new Promise((resolve) => {
    const tick = (t) => {
      times.push(t)
      if (t - start < 600) requestAnimationFrame(tick)
      else resolve()
    }
    requestAnimationFrame(tick)
    setTheme({ theme: 'dark' })
  })
  const d = times.slice(1).map((t, i) => t - times[i])
  return { frames: d.length, worst: Math.max(...d), mean: d.reduce((a, b) => a + b, 0) / d.length, vt: 'startViewTransition' in document }
})
console.log(`\ntheme switch: ${sw.frames} frames in 600 ms, mean ${sw.mean.toFixed(1)} ms, worst ${sw.worst.toFixed(1)} ms, view transitions: ${sw.vt}`)
for (const e of errors) { fails++; console.log(`page error: ${e}`) }
await browser.close()
console.log(fails ? `\n${fails} FAILURES` : '\nALL 24 COMBINATIONS OK')
process.exit(fails ? 1 : 0)
