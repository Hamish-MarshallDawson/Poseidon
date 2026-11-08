// Overlap check for the floating UI. Run (dev server up, e.g. `npx vite --port 5188 --strictPort`):
//   node scripts/overlap.mjs [--port 5188] [--tag after] [--phone] [--out <dir>]
// Opens /dev/monitor.html (the real Monitor, no login, VITE_DATA=offline) in installed Edge, headed (headless has no
// WebGL2), at 1920x1009, 1366x768 and 1280x720 (plus 390x844 with --phone), steps through ten UI states and reports
// every pair of visible position:fixed/absolute UI elements that intersect by more than 2 px in both directions.
// Writes <out>/<tag>/results.json and screenshots; exits 1 when any pair overlaps.
import { chromium } from 'playwright-core'
import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

const flag = (n) => process.argv.includes(`--${n}`)
const val = (n, d) => { const i = process.argv.indexOf(`--${n}`); return i < 0 ? d : process.argv[i + 1] }
const port = val('port', '5188')
const tag = val('tag', 'after')
const outDir = join(val('out', 'G:/GitHub/dvm-fe/stacking/layout'), tag)
const sizes = [[1920, 1009], [1366, 768], [1280, 720], ...(flag('phone') ? [[390, 844]] : [])]
mkdirSync(outDir, { recursive: true })

// In-page: every visible fixed/absolute UI box, minus the exclusions below.
function collect() {
  // Exclusions: the map, tooltips, leader lines, the replay edge frame, full-screen layers.
  const SKIP = '.dvm-map, canvas, .maplibregl-marker, .leader, .tl-edge, .dvm-chip-tip, .tl-tip, .dvm-stack, .sw-layer, .dvm-overlay'
  const POPOVER = '.dvm-theme-menu__panel, .tl-pop'   // absolute children that are separate UI (menus)
  const MLCTRL = '.maplibregl-ctrl-bottom-right, .maplibregl-ctrl-bottom-left, .maplibregl-ctrl-top-left, .maplibregl-ctrl-top-right'
  const vw = innerWidth, vh = innerHeight
  const cands = []
  for (const el of document.body.querySelectorAll('*')) {
    const cs = getComputedStyle(el)
    if (cs.position !== 'fixed' && cs.position !== 'absolute') continue
    if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) < 0.05) continue
    if (el.matches(SKIP)) continue
    if (el.closest('.dvm-map') && !el.closest('.maplibregl-ctrl')) continue
    const r = el.getBoundingClientRect()
    if (r.width < 1 || r.height < 1) continue
    if (r.right <= 0 || r.bottom <= 0 || r.left >= vw || r.top >= vh) continue
    if (r.width >= vw * 0.95 && r.height >= vh * 0.95) continue
    cands.push({ el, r })
  }
  const set = new Set(cands.map((c) => c.el))
  const label = (el) => `${el.tagName.toLowerCase()}${el.id ? '#' + el.id : ''}${[...el.classList].slice(0, 2).map((c) => '.' + c).join('')}${el.getAttribute('aria-label') ? `[${el.getAttribute('aria-label')}]` : ''}`
  // Keep top-level units: drop an element that sits inside another candidate, unless it is a menu popover.
  const roots = cands.filter(({ el }) => {
    if (el.matches(POPOVER)) return true
    for (let p = el.parentElement; p; p = p.parentElement) if (set.has(p) && !p.matches(MLCTRL)) return false
    return true
  })
  const boxes = roots.map(({ el, r }) => ({ name: label(el), x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height), el }))
  const out = []
  for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
    const a = boxes[i], b = boxes[j]
    if (a.el.contains(b.el) || b.el.contains(a.el)) continue
    const dx = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x)
    const dy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y)
    if (dx > 2 && dy > 2) out.push({ a: a.name, b: b.name, w: dx, h: dy })
  }
  return { count: boxes.length, overlaps: out, boxes: boxes.map((b) => ({ name: b.name, x: b.x, y: b.y, w: b.w, h: b.h })) }
}

// In-page inner check: inside Review rows and ship windows, leaf text/control boxes that intersect, and children
// that stick out of their card's content box horizontally.
function collectInner() {
  const out = []
  const nm = (el) => `${el.tagName.toLowerCase()}${[...el.classList].slice(0, 2).map((c) => '.' + c).join('')}${el.textContent && el.children.length === 0 ? `"${el.textContent.trim().slice(0, 18)}"` : ''}`
  const shown = (el) => { const cs = getComputedStyle(el); const r = el.getBoundingClientRect(); return cs.visibility !== 'hidden' && cs.display !== 'none' && Number(cs.opacity) > 0.05 && r.width > 0 && r.height > 0 }
  const CONTROL = 'input, img'   // a button or row with children is judged by its leaves
  for (const scope of document.querySelectorAll('.watchlist .wl-item, .sw:not(.sw-pill)')) {
    const where = scope.classList.contains('sw') ? `window ${scope.dataset.mmsi}` : `row ${scope.textContent.trim().slice(0, 14)}`
    const leaves = [...scope.querySelectorAll('*')].filter((el) => shown(el) && (el.matches(CONTROL) || (el.children.length === 0 && el.textContent.trim())))
    const rs = leaves.map((el) => ({ el, r: el.getBoundingClientRect() }))
    for (let i = 0; i < rs.length; i++) for (let j = i + 1; j < rs.length; j++) {
      const a = rs[i].r, b = rs[j].r
      const dx = Math.min(a.right, b.right) - Math.max(a.left, b.left), dy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top)
      if (dx > 2 && dy > 2 && !rs[i].el.contains(rs[j].el) && !rs[j].el.contains(rs[i].el)) out.push({ where, kind: 'intersect', a: nm(rs[i].el), b: nm(rs[j].el), w: Math.round(dx), h: Math.round(dy) })
    }
    const card = scope.classList.contains('sw') ? scope.querySelector('.sc') : scope
    if (card) {
      const cr = card.getBoundingClientRect(), cs = getComputedStyle(card)
      const left = cr.left + parseFloat(cs.paddingLeft) + parseFloat(cs.borderLeftWidth), right = cr.right - parseFloat(cs.paddingRight) - parseFloat(cs.borderRightWidth)
      for (const { el, r } of rs) if (card.contains(el) && (r.right > right + 1 || r.left < left - 1)) out.push({ where, kind: 'overflow', a: nm(el), b: '', w: Math.round(Math.max(r.right - right, left - r.left)), h: 0 })
    }
  }
  return out
}

// Ship nearest to a point (fractions of the viewport), skipping those already used.
const pick = (fx, fy, used) => `(() => {
  const d = window.__dev, best = []
  for (const [m] of d.vessels.vessels) { const p = d.shipScreenPoint(m); if (p) best.push([Math.hypot(p.x - innerWidth * ${fx}, p.y - innerHeight * ${fy}), m]) }
  return best.sort((a, b) => a[0] - b[0]).map((x) => x[1]).filter((m) => !${JSON.stringify(used)}.includes(m))[0]
})()`

async function open(p, fx, fy, used = []) {
  const m = await p.evaluate(pick(fx, fy, used))
  await p.evaluate((id) => window.__dev.openShipWindow(id), m)
  await p.waitForTimeout(500)
  return m
}
async function two(p, ax, ay, bx, by) { const a = await open(p, ax, ay); const b = await open(p, bx, by, [a]); return [a, b] }

const STATES = [
  ['01-base', async () => {}],
  ['02-review', (p) => p.evaluate(() => window.__dev.ui.set({ reviewOpen: true }))],
  ['04-layers', (p) => p.evaluate(() => window.__dev.ui.set({ layersOpen: true }))],
  ['05-display', (p) => p.click('.dvm-menu-toggle')],
  ['06-legend', (p) => p.evaluate(() => window.__dev.ui.set({ legendOpen: true }))],
  ['07-two-windows', (p) => two(p, 0.5, 0.5, 0.55, 0.45)],
  ['08-focus', async (p) => { const a = await open(p, 0.5, 0.5); await p.evaluate((m) => window.__dev.ui.set({ focusMmsi: m }), a) }],
  ['09-briefing-two-windows', async (p) => {
    const [a, b] = await two(p, 0.2, 0.7, 0.28, 0.6)
    await p.evaluate(([x, y]) => window.__dev.runBriefing([x, y]), [a, b])
    await p.waitForSelector('.br-body', { timeout: 8000 })
  }],
  ['10-replay-two-windows', async (p) => { await p.evaluate(() => window.__dev.replay()); await two(p, 0.5, 0.5, 0.55, 0.45) }],
  ['11-layers-show-yachts', async (p) => {
    await p.evaluate(() => {
      const d = window.__dev, byMmsi = new Map(), list = []
      for (const m of [...d.vessels.vessels.keys()].slice(0, 6)) { const y = { imo: m, name: `Yacht ${m}`, length_m: 60, owner_reported: null, owner_source_url: null, sanctioned: m % 2 === 0, programs: [], sanctions_source: null, mmsi: m, last_seen_ts: Date.now(), status: 'ais' }; list.push(y); byMmsi.set(m, y) }
      d.yachts.set({ list, byMmsi }); d.ui.set({ layersOpen: true }); d.setShow('yachts')
    })
  }],
  ['12-layers-show-dark', (p) => p.evaluate(() => { window.__dev.ui.set({ layersOpen: true }); window.__dev.setShow('dark') })],
]

const browser = await chromium.launch({ channel: 'msedge', headless: false })
const results = []
for (const [w, h] of sizes) {
  const page = await browser.newPage({ viewport: { width: w, height: h } })
  for (const [name, run] of STATES) {
    await page.goto(`http://localhost:${port}/dev/monitor.html?synthetic=3000`)
    await page.waitForFunction(() => window.__dev?.vessels.vessels.size > 200, null, { timeout: 60000 })
    await page.waitForTimeout(1500)
    let error = null
    try { await run(page); await page.waitForTimeout(900) } catch (e) { error = String(e.message ?? e).split('\n')[0] }
    const res = await page.evaluate(collect)
    const inner = /^0[2789]|^10/.test(name) ? await page.evaluate(collectInner) : []
    res.overlaps.push(...inner.map((o) => ({ a: `${o.where} ${o.kind}: ${o.a}`, b: o.b, w: o.w, h: o.h })))
    await page.screenshot({ path: join(outDir, `${w}x${h}-${name}.png`) })
    results.push({ size: `${w}x${h}`, state: name, error, boxes: res.count, overlaps: res.overlaps, layout: res.boxes })
    console.log(`${w}x${h} ${name.padEnd(24)} boxes ${String(res.count).padStart(2)}  overlaps ${res.overlaps.length}${error ? '  ERROR ' + error : ''}`)
    for (const o of res.overlaps) console.log(`    ${o.a}  x  ${o.b}   ${o.w}x${o.h}px`)
  }
  await page.close()
}
await browser.close()
const fails = results.reduce((n, r) => n + r.overlaps.length + (r.error ? 1 : 0), 0)
writeFileSync(join(outDir, 'results.json'), JSON.stringify(results, null, 1))
console.log(`\n${fails} failures (${results.length} state runs). Results: ${join(outDir, 'results.json')}`)
process.exit(fails ? 1 : 0)
