// Frontend smoke test: log in through Auth0, then check the map really renders.
// Fails on a "Worker failed to load" console error (the black-map bug), no MapLibre worker, no basemap tiles,
// or no live ships. Needs the dev server on :5173, the backend on :8000, and an Auth0 test user:
//   AUTH0_TEST_EMAIL=... AUTH0_TEST_PASSWORD=... npm run smoke
// Runs a headed installed browser (SMOKE_BROWSER, default msedge): headless Chromium here has no WebGL2.
import { chromium } from 'playwright-core'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const url = process.env.SMOKE_URL ?? 'http://localhost:5173'
const { AUTH0_TEST_EMAIL: email, AUTH0_TEST_PASSWORD: password } = process.env
if (!email || !password) {
  console.error('Set AUTH0_TEST_EMAIL and AUTH0_TEST_PASSWORD (an Auth0 test user).')
  process.exit(2)
}

const browser = await chromium.launch({ channel: process.env.SMOKE_BROWSER ?? 'msedge', headless: false })
const page = await browser.newPage({ viewport: { width: 1280, height: 760 } })
const consoleErrors = []
let tiles = 0
page.on('console', (m) => m.type() === 'error' && consoleErrors.push(m.text()))
page.on('pageerror', (e) => consoleErrors.push(String(e)))
page.on('requestfinished', (r) => /\/\d+\/\d+\/\d+\.pbf/.test(r.url()) && tiles++) // vector tiles, fetched by the worker

const fail = []
try {
  await page.goto(url)
  await page.getByRole('button', { name: 'Log in to view the map' }).click()
  await page.waitForURL((u) => u.hostname.endsWith('.auth0.com'), { timeout: 20000, waitUntil: 'domcontentloaded' })
  await page.locator('input[name=username], input[type=email]').first().fill(email)
  await page.locator('input[type=password]').fill(password)
  await page.getByRole('button', { name: 'Continue', exact: true }).click()
  await page.waitForURL((u) => u.origin === new URL(url).origin, { timeout: 30000 })
  await page.waitForFunction(() => /connected · ships [1-9]/.test(document.querySelector('.status')?.textContent ?? ''),
    null, { timeout: 30000 })
  await page.waitForTimeout(5000) // let tiles and a few deltas arrive
} catch (e) {
  fail.push(`flow did not complete: ${String(e).split('\n')[0]}`)
}

if (consoleErrors.some((t) => /Worker failed/i.test(t))) fail.push('MapLibre "Worker failed to load" (black map)')
const workers = page.workers().length
if (workers === 0) fail.push('no MapLibre web worker is running')
if (tiles === 0) fail.push('no basemap vector tiles loaded')
const status = await page.locator('.status').innerText().catch(() => '(no status line)')
const shot = join(tmpdir(), 'dvm-smoke.png')
await page.screenshot({ path: shot })
await browser.close()

console.log(`status: ${status}\nworkers: ${workers}, tiles: ${tiles}, screenshot: ${shot}`)
for (const t of consoleErrors) console.log(`console error: ${t.slice(0, 160)}`)
if (fail.length) {
  console.error(`SMOKE FAILED:\n- ${fail.join('\n- ')}`)
  process.exit(1)
}
console.log('SMOKE OK')
