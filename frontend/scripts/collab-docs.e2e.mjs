// End to end for the session channel, saved briefings and the summary, with two browser contexts (two users).
// Needs: a backend with AISSTREAM_API_KEY= TIGER_DATABASE_URL= AUTH0_DOMAIN= AUTH0_AUDIENCE= DIGITRAFFIC=0 GEMINI_API_KEY=
// on API (default 8123) and `VITE_AUTH=off VITE_API_URL=http://localhost:8123 npx vite --port 5193 --strictPort`.
//   node scripts/collab-docs.e2e.mjs [--api 8123] [--port 5193] [--out <dir>]
// Installed Edge, headed (headless has no WebGL2). Exits 1 on the first failed expectation.
import { chromium } from 'playwright-core'
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'

const val = (n, d) => { const i = process.argv.indexOf(`--${n}`); return i < 0 ? d : process.argv[i + 1] }
const API = `http://localhost:${val('api', '8123')}`
const APP = `http://localhost:${val('port', '5193')}`
const out = val('out', 'collab-docs-shots')
mkdirSync(out, { recursive: true })
const SHIP = 230000001, OTHER = 244660000

const fail = (m) => { console.error(`FAIL: ${m}`); process.exitCode = 1; throw new Error(m) }
const expect = (c, m) => { if (!c) fail(m); console.log(`ok: ${m}`) }
const rest = async (user, method, path, body) => {
  const r = await fetch(API + path, { method, headers: { 'X-Dev-User': user, ...(body ? { 'Content-Type': 'application/json' } : {}) }, body: body && JSON.stringify(body) })
  return { status: r.status, json: r.status === 204 ? null : await r.json() }
}

const browser = await chromium.launch({ channel: 'msedge', headless: false })
try {
  const tag = String(Date.now() % 100000)
  await rest('hamish', 'POST', '/me', { name: 'Hamish Dawson' })
  await rest('aiden', 'POST', '/me', { name: 'Aiden Ruz' })
  const sid = (await rest('hamish', 'POST', '/sessions', { title: `Baltic dark ships ${tag}` })).json.id
  const inv = (await rest('hamish', 'POST', `/sessions/${sid}/invites`)).json.token
  await rest('aiden', 'POST', `/invites/${inv}/accept`)

  const open = async (user, w = 1366, h = 768) => {
    const ctx = await browser.newContext({ viewport: { width: w, height: h } })
    const page = await ctx.newPage()
    await page.goto(`${APP}/?dev_user=${user}`)
    await page.waitForSelector('.top-right')
    await page.evaluate(async (id) => (await import('/src/collab/store.ts')).openSession(id), sid)
    await page.waitForSelector('text=Channel')
    return page
  }
  const ham = await open('hamish')
  const aid = await open('aiden')
  const panel = (p) => p.locator('#channel-panel')
  const chip = (p) => p.locator('button.chip', { hasText: 'Channel' })

  // 1. the chip shows only inside a session, and the panel carries the not-an-accusation banner above the input
  await chip(ham).click()
  await chip(aid).click()
  await panel(ham).waitFor()
  expect(await panel(ham).locator('.ch-banner').innerText() === 'A flag is a prompt to review, not an accusation.', 'banner text')
  expect(await ham.locator('.ch-banner ~ textarea').count() === 1, 'banner sits above the note input')

  // 2. a session-wide note syncs live, with the author's initials, and a ship reference focuses the ship
  await aid.locator('#channel-panel textarea').fill(`this is sus <b>x</b> ${SHIP}`)
  await aid.keyboard.press('Enter')
  await ham.locator('.ch-feed .ch-item', { hasText: 'this is sus' }).waitFor({ timeout: 4000 })
  const item = ham.locator('.ch-feed .ch-item', { hasText: 'this is sus' })
  expect(await item.locator('.ch-meta b').innerText() === 'Aiden Ruz', 'note shows its author')
  expect(await item.locator('.ch-avatar-i').innerText() === 'AR', 'initials avatar')
  expect(await item.innerText().then((t) => t.includes('<b>x</b>')), 'markup stays plain text')
  expect(await item.locator('.ch-ref').count() === 1, 'a 9-digit MMSI becomes a ship reference')
  // append-only: no edit or delete controls
  expect(await item.locator('button', { hasText: /edit|delete/i }).count() === 0, 'no edit or delete')

  // 3. the length cap
  expect(await aid.locator('#channel-panel textarea').getAttribute('maxlength') === '1000', 'note length cap in the UI')

  // 4. a saved briefing (several ships): Save to session in the briefing panel, then it shows in the other browser
  const fake = {
    generated_at: Date.now(), model: 'test', mmsis: [SHIP, OTHER], voice_available: false,
    summary: {
      headline: 'Two ships went quiet', overview: 'Both stopped transmitting near the same area.', speech_script: '',
      per_vessel: [SHIP, OTHER].map((m) => ({ mmsi: m, name: null, risk: 'low', findings: ['quiet 20 min'], caveats: ['coverage hole'] })),
      correlation: { found: false, strength: 'none', links: [], explanation: '' },
    },
  }
  await aid.route('**/briefing', (r) => r.fulfill({ json: fake }))
  await aid.evaluate(async (m) => (await import('/src/briefing/store.ts')).runBriefing(m), [SHIP, OTHER])
  await aid.getByRole('button', { name: 'Save to session' }).click()
  await aid.getByRole('button', { name: 'Saved to session' }).waitFor()
  const brief = ham.locator('.ch-feed .ch-briefing')
  await brief.waitFor({ timeout: 4000 })
  expect(/briefing · 2 ships/i.test(await brief.innerText()), 'briefing shows how many ships it covers')
  expect(await brief.locator('.ch-ships .ch-ref').count() === 2, 'briefing lists both ships')
  await brief.getByRole('button', { name: 'Open briefing' }).click()
  expect((await brief.innerText()).includes('Caveat: coverage hole'), 'the briefing text opens in the channel')
  const docId = (await brief.locator('.ch-id').innerText()).replace('doc#', '')

  // 5. report generated: both ships now count as having a saved briefing
  const reported = await ham.evaluate(async () => {
    const { reportedShips } = await import('/src/collab/docs/logic.ts')
    const { collab } = await import('/src/collab/store.ts')
    return [...reportedShips(collab.get().documents)]
  })
  expect(reported.includes(SHIP) && reported.includes(OTHER), 'reportedShips covers the briefed ships')

  // 6. a note can reference the document; clicking it opens it
  await ham.locator('#channel-panel textarea').fill(`see doc#${docId}`)
  await ham.keyboard.press('Enter')
  const ref = aid.locator('.ch-feed .ch-item', { hasText: `see doc#${docId}` }).locator('.ch-ref')
  await ref.waitFor({ timeout: 4000 })
  await ref.click()
  expect(await aid.locator('.ch-item.is-hit').count() === 1, 'clicking a document reference highlights the document')

  // 7. a per-ship note appears with "About <ship>"
  await rest('hamish', 'POST', `/sessions/${sid}/documents`, { mmsi: OTHER, body: 'worth a look' })
  await aid.locator('.ch-feed .ch-item', { hasText: 'worth a look' }).locator('.ch-about').waitFor({ timeout: 4000 })
  expect(true, 'a per-ship note shows what it is about')

  // 8. summary: 503 says so; then a (stubbed) success pins the summary at the top
  await ham.getByRole('button', { name: 'Summarise session' }).click()
  await ham.locator('.ch-summarise .ch-err').waitFor()
  expect((await ham.locator('.ch-summarise .ch-err').innerText()).includes('not set up'), 'no Gemini key: the UI says so (503)')
  await ham.screenshot({ path: join(out, 'channel-hamish.png') })
  await aid.screenshot({ path: join(out, 'channel-aiden.png') })
  const summaryDoc = (await rest('hamish', 'POST', `/sessions/${sid}/documents`, { body: 'x' })).json.document
  await ham.route('**/summary', (r) => r.fulfill({ status: 201, json: { document: { ...summaryDoc, id: summaryDoc.id + 100, kind: 'summary', body: 'The team looked at two ships.', mmsis: [SHIP] } } }))
  await ham.getByRole('button', { name: 'Summarise session' }).click()
  await ham.locator('.ch-pinned .ch-summary').waitFor()
  expect(/session summary/i.test(await ham.locator('.ch-pinned').innerText()), 'the summary is pinned in the channel')
  await ham.screenshot({ path: join(out, 'summary-hamish.png') })

  // 9. non-members and logged-out state: a third user cannot read the session
  expect((await rest('mano', 'GET', `/sessions/${sid}`)).status === 404, 'a non-member gets 404')
  console.log('ALL OK')
} finally {
  await browser.close()
}
