// Map performance bench (dev only). Needs `npm run dev -- --port 5175 --strictPort` running. Opens the bench page
// with synthetic ships in a headed browser and measures, per scenario:
//   fps from requestAnimationFrame timestamps over a 5 s programmatic pan and a 5 s zoom-in, worst frame,
//   time from navigation to the map's `load` and to the first frame with ships, and (with --heap) the JS heap
//   after a GC at 15 s and at 120 s.
// Usage: node src/map/bench/run.mjs [--browser /usr/bin/chromium | --channel msedge] [--ships 25000] [--heap] [--only name]
import { chromium } from 'playwright-core'

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d }
const has = (k) => process.argv.includes(k)
const base = arg('--url', 'http://localhost:5175/src/map/bench/bench.html')
const ships = Number(arg('--ships', '25000'))
const only = arg('--only', '')
const launch = arg('--channel') ? { channel: arg('--channel') } : { executablePath: arg('--browser', '/usr/bin/chromium') }

const BALTIC = { bounds: [[4, 54.4], [36, 64.5]] }
const WORLD = { center: [10, 30], zoom: 1.6 }
const scenarios = [
  { name: 'custom, capped (default), Baltic', q: '', view: BALTIC },
  { name: 'custom, capped (default), world', q: '', view: WORLD },
  { name: 'custom, cap=0 (every ship drawn), Baltic', q: '&cap=0', view: BALTIC },
  { name: 'custom, cap=0 (every ship drawn), world', q: '&cap=0', view: WORLD },
  { name: 'symbol layer + setData per frame, Baltic', q: '&renderer=symbol', view: BALTIC },
  { name: 'symbol layer + setData per frame, world', q: '&renderer=symbol', view: WORLD },
].filter((s) => !only || s.name.includes(only))

// Runs in the page: animate the camera for `ms` and record every rAF timestamp.
async function measure(page, move) {
  return page.evaluate(async ({ move }) => {
    const map = window.__dvm.map
    const t = []
    const long = []
    const po = new PerformanceObserver((l) => { for (const e of l.getEntries()) long.push(Math.round(e.duration)) })
    po.observe({ type: 'long-animation-frame', buffered: false })
    let on = true
    const loop = (ts) => { t.push(ts); if (on) requestAnimationFrame(loop) }
    requestAnimationFrame(loop)
    const c = map.getCenter(), z = map.getZoom(), w = map.getCanvas().clientWidth
    const opts = { duration: 5000, easing: (x) => x, essential: true }
    if (move === 'pan') map.easeTo({ ...opts, center: map.unproject([w * 0.5 + w * 0.6, map.getCanvas().clientHeight / 2]) })
    else map.easeTo({ ...opts, zoom: z + 2.5, center: c })
    await new Promise((r) => setTimeout(r, 5100))
    on = false
    po.disconnect()
    const d = t.slice(1).map((x, i) => x - t[i])
    const span = (t[t.length - 1] - t[0]) / 1000
    d.sort((a, b) => a - b)
    return { fps: +((t.length - 1) / span).toFixed(1), worstMs: +d[d.length - 1].toFixed(1), p99Ms: +d[Math.floor(d.length * 0.99)].toFixed(1), frames: t.length, longFrames: long }
  }, { move })
}

const browser = await chromium.launch({ ...launch, headless: false, args: ['--enable-precise-memory-info', '--ignore-gpu-blocklist'] })
const results = []
for (const s of scenarios) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e)))
  await page.goto(`${base}?synthetic=${ships}${s.q}`)
  await page.waitForFunction(() => window.__dvm?.map?.isStyleLoaded() && performance.getEntriesByName('dvm:map-load').length + (window.__dvm.ctl ? 0 : 1), null, { timeout: 30000 })
  const marks = await page.evaluate(() => Object.fromEntries(['dvm:map-load', 'dvm:first-ship-frame'].map((n) => [n, Math.round(performance.getEntriesByName(n)[0]?.startTime ?? -1)])))
  await page.evaluate((v) => { const m = window.__dvm.map; if (v.bounds) m.fitBounds(v.bounds, { duration: 0 }); else m.jumpTo(v) }, s.view)
  await page.waitForTimeout(3000)
  const before = await page.evaluate(() => ({ zoom: +window.__dvm.map.getZoom().toFixed(2), view: window.__dvm.ui?.get().view, ships: window.__dvm.vessels?.vessels.size }))
  const pan = await measure(page, 'pan')
  await page.waitForTimeout(1500)
  await page.evaluate((v) => { const m = window.__dvm.map; if (v.bounds) m.fitBounds(v.bounds, { duration: 0 }); else m.jumpTo(v) }, s.view)
  await page.waitForTimeout(1500)
  const zoom = await measure(page, 'zoom')
  const costs = await page.evaluate(() => Object.fromEntries(['dvm:synthetic-gen', 'dvm:apply-frame', 'dvm:slot-pass', 'dvm:rebuild'].map((n) => {
    const d = performance.getEntriesByName(n).map((e) => e.duration).sort((a, b) => a - b)
    return [n, d.length ? { n: d.length, median: +d[d.length >> 1].toFixed(1), max: +d[d.length - 1].toFixed(1) } : null]
  })))
  results.push({ costs, scenario: s.name, ships, ...before, firstMapLoadMs: marks['dvm:map-load'], firstShipFrameMs: marks['dvm:first-ship-frame'], pan, zoom, errors: errors.slice(0, 3) })
  console.log(JSON.stringify(results[results.length - 1]))
  await page.close()
}

if (has('--heap')) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  const cdp = await page.context().newCDPSession(page)
  await page.goto(`${base}?synthetic=${ships}`)
  await page.waitForFunction(() => window.__dvm?.map?.loaded(), null, { timeout: 30000 })
  const heap = async () => { await cdp.send('HeapProfiler.collectGarbage'); return Math.round((await cdp.send('Runtime.getHeapUsage')).usedSize / 1048576) }
  await page.waitForTimeout(15000)
  const h15 = await heap()
  // Keep the camera busy for part of the run so the slot pass and rebuilds run too.
  await page.evaluate(() => { const m = window.__dvm.map; let i = 0; window.__pan = setInterval(() => m.panBy([i++ % 2 ? 300 : -300, 0], { duration: 800 }), 4000) })
  await page.waitForTimeout(105000)
  const h120 = await heap()
  const r = { heapMB_at15s: h15, heapMB_at120s: h120, ships }
  console.log(JSON.stringify(r))
  results.push(r)
}
await browser.close()
