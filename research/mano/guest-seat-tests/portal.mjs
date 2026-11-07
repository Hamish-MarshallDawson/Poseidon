// STAND-IN TEST PORTAL. Not a real system and not a substitute for the ERPNext test.
// It behaves like a simple third-party portal: one shared company login, an MFA step,
// and a record form whose save overwrites every field (last write wins, no version check).
// Only what the browser tool does against it is evidence. Anything it does because we
// coded it that way (for example forced logout) is an assumption, and is reported as one.
import http from 'node:http';
import { randomUUID } from 'node:crypto';

export const ACCOUNT = { user: 'acme-supplier', pass: 'stand-in-password', mfa: '492817' };
const FIELDS = ['company', 'vat', 'po_ref', 'bank_account', 'answer'];
const INITIAL = {
  company: 'Acme Ltd', vat: 'GB123456789', po_ref: 'PO-1000',
  bank_account: '12-34-56 00000001', answer: '',
};

export function startPortal({ port = 0, singleSession = false, clock = false } = {}) {
  const sessions = new Map(); // sid -> { mfa: boolean }
  let record = { ...INITIAL };
  const recordB = { ...INITIAL, company: 'Bravo Ltd', answer: '' };
  let version = 1;
  const log = [];
  const event = (type, sid, extra = {}) => log.push({ t: Date.now(), type, sid: sid?.slice(0, 8), account: ACCOUNT.user, ...extra });

  const page = (body) => `<!doctype html><html><head><title>Stand-in portal</title></head><body>
<p role="note">STAND-IN TEST PORTAL, not a real system</p>${body}</body></html>`;
  const readForm = (req) => new Promise((res) => {
    let s = ''; req.on('data', (d) => (s += d));
    req.on('end', () => res(Object.fromEntries(new URLSearchParams(s))));
  });
  const esc = (v) => String(v).replace(/[&<>"]/g, (c) => `&#${c.charCodeAt(0)};`);

  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, 'http://x');
    const sid = /sid=([\w-]+)/.exec(req.headers.cookie ?? '')?.[1];
    const sess = sid && sessions.get(sid);
    const send = (html, code = 200, h = {}) => { res.writeHead(code, { 'content-type': 'text/html', ...h }); res.end(html); };
    const go = (to, h = {}) => { res.writeHead(303, { location: to, ...h }); res.end(); };
    const json = (o) => { res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify(o)); };

    // Harness-only endpoints: stand in for "the portal's own record".
    if (url.pathname === '/__state') return json({ record, version, log, sessions: sessions.size });

    if (url.pathname === '/login' && req.method === 'POST') {
      const f = await readForm(req);
      if (f.user !== ACCOUNT.user || f.pass !== ACCOUNT.pass) return send(page('<h1>Login failed</h1>'), 401);
      if (singleSession) { event('forced_logout_others', sid, { dropped: sessions.size }); sessions.clear(); }
      const id = randomUUID(); sessions.set(id, { mfa: false }); event('login', id);
      return go('/mfa', { 'set-cookie': `sid=${id}; Path=/; HttpOnly` });
    }
    if (url.pathname === '/login') return send(page(`<h1>Supplier access</h1><form method="post" action="/login">
<label>Username <input name="user"></label><label>Password <input name="pass" type="password"></label>
<button>Sign in</button></form>`));
    if (!sess) return go('/login');

    if (url.pathname === '/mfa' && req.method === 'POST') {
      const f = await readForm(req);
      if (f.code !== ACCOUNT.mfa) return send(page('<h1>Wrong code</h1>'), 401);
      sess.mfa = true; event('mfa_ok', sid);
      return go('/record');
    }
    if (url.pathname === '/mfa') return send(page(`<h1>Enter your code</h1><form method="post" action="/mfa">
<label>One-time code <input name="code" autocomplete="one-time-code"></label><button>Verify</button></form>`));
    if (!sess.mfa) return go('/mfa');

    // A second supplier whose form has the same labels, to test where a held ref lands.
    if (url.pathname === '/record-b') {
      if (req.method === 'POST') { Object.assign(recordB, await readForm(req)); event('record_b_saved', sid); return go('/record-b'); }
      const inputs = FIELDS.map((k) => `<p><label>${k} <input name="${k}" value="${esc(recordB[k])}"></label></p>`).join('');
      return send(page(`<h1>Supplier record (Bravo Ltd)</h1><form method="post" action="/record-b">${inputs}<button>Save record</button></form>`));
    }
    if (url.pathname === '/record' && req.method === 'POST') {
      const f = await readForm(req);
      const changed = FIELDS.filter((k) => k in f && f[k] !== record[k]);
      for (const k of FIELDS) if (k in f) record[k] = f[k];
      version++;
      event('record_saved', sid, { changed });
      return go('/record');
    }
    if (url.pathname === '/record') {
      const inputs = FIELDS.map((k) => `<p><label>${k} <input name="${k}" value="${esc(record[k])}"></label></p>`).join('');
      const tick = clock ? `<p>Server time <span id="clock" role="status">0</span></p>
<script>let n=0;setInterval(()=>{document.getElementById('clock').textContent=String(++n)},200)</script>` : '';
      return send(page(`<h1>Supplier record</h1>${tick}<form method="post" action="/record">${inputs}<button>Save record</button></form>`));
    }
    return go('/record');
  });
  return new Promise((resolve) => server.listen(port, '127.0.0.1', () => resolve({
    url: `http://127.0.0.1:${server.address().port}`,
    state: () => ({ record: { ...record }, recordB: { ...recordB }, version, log: [...log] }),
    close: () => new Promise((r) => { server.closeAllConnections(); server.close(r); }),
  })));
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const p = await startPortal({ port: Number(process.argv[2] ?? 4100), clock: process.argv.includes('--clock') });
  console.log(p.url);
}
