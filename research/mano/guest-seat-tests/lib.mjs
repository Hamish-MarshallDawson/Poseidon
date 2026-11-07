// Thin wrapper over the agent-browser CLI. Every call runs in a dedicated namespace and
// named session, so tests never touch the default session or anyone's Chrome profile.
// It is async because the portal runs in this same process and must keep serving.
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { ACCOUNT } from './portal.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const BIN = path.join(here, 'node_modules/.bin/agent-browser');
export const NS = 'guest-seat-tests';

export function ab(session, args, { allowFail = false, extra = [] } = {}) {
  const t0 = performance.now();
  return new Promise((resolve, reject) => {
    const c = spawn(BIN, ['--namespace', NS, '--session', session, ...extra, ...args], { stdio: ['ignore', 'pipe', 'pipe'] });
    let out = '', err = '';
    c.stdout.on('data', (d) => (out += d));
    c.stderr.on('data', (d) => (err += d));
    // Resolve on exit, not close: the first command starts a daemon that can inherit these pipes.
    c.on('exit', (status) => setTimeout(() => {
      const r = { ok: status === 0, out: out.trim(), err: err.trim(), ms: performance.now() - t0 };
      if (!r.ok && !allowFail) reject(new Error(`agent-browser ${args.join(' ')} failed (${status}): ${r.err || r.out}`));
      else resolve(r);
    }, 20));
  });
}

// Find a ref like @e3 in a snapshot by the accessible name of the element.
export function refFor(snapshot, name) {
  const line = snapshot.split('\n').find((l) => l.includes(`"${name}"`) && /ref=e\d+/.test(l));
  if (!line) throw new Error(`no ref for "${name}" in:\n${snapshot}`);
  return '@' + /ref=(e\d+)/.exec(line)[1];
}

export async function login(session, base, opts) {
  await ab(session, ['open', `${base}/login`], opts);
  let s = (await ab(session, ['snapshot', '-i'], opts)).out;
  await ab(session, ['fill', refFor(s, 'Username'), ACCOUNT.user], opts);
  await ab(session, ['fill', refFor(s, 'Password'), ACCOUNT.pass], opts);
  await ab(session, ['click', refFor(s, 'Sign in')], opts);
  await ab(session, ['wait', 'input[name=code]'], opts);
  s = (await ab(session, ['snapshot', '-i'], opts)).out;
  await ab(session, ['fill', refFor(s, 'One-time code'), ACCOUNT.mfa], opts);
  await ab(session, ['click', refFor(s, 'Verify')], opts);
  await ab(session, ['wait', 'input[name=company]'], opts);
}

export const closeAll = () => new Promise((r) => {
  spawn(BIN, ['--namespace', NS, 'close', '--all'], { stdio: 'ignore' }).on('exit', r);
});
