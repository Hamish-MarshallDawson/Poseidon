// T5: size of what an agent must read. No model is called, so these are payload estimates using
// the cl100k tokenizer, not billed usage. Claude and Gemini tokenize differently.
import { spawn } from 'node:child_process';
import { writeFileSync, mkdirSync } from 'node:fs';
import { getEncoding } from 'js-tiktoken';
import { startPortal } from './portal.mjs';
import { ab, refFor, login, closeAll } from './lib.mjs';

const enc = getEncoding('cl100k_base');
const tok = (s) => enc.encode(s).length;
const results = {};

// 1. Tool schemas: the cost before any page is read.
function toolsList(cmd, args) {
  return new Promise((resolve, reject) => {
    const c = spawn(cmd, args, { stdio: ['pipe', 'pipe', 'ignore'] });
    let buf = '';
    const timer = setTimeout(() => { c.kill(); reject(new Error('tools/list timed out: ' + args.join(' '))); }, 45000);
    c.stdin.on('error', () => {});
    c.on('error', reject);
    c.stdout.on('data', (d) => {
      const lines = (buf + d).split('\n');
      buf = lines.pop(); // keep the unfinished line for the next chunk
      for (const line of lines) {
        let m;
        try { m = JSON.parse(line); } catch { continue; }
        if (m.id === 1) c.stdin.write(JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }) + '\n' + JSON.stringify({ jsonrpc: '2.0', id: 2, method: 'tools/list' }) + '\n');
        if (m.id === 2) { clearTimeout(timer); c.kill(); resolve(m.result.tools); }
      }
    });
    c.stdin.write(JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'guest-seat-tests', version: '0' } } }) + '\n');
  });
}
const OURS = [
  { name: 'observe', description: 'Snapshot of the leased page. Returns a stamp to quote when acting.', inputSchema: { type: 'object', properties: { lease: { type: 'string' } }, required: ['lease'] } },
  { name: 'act', description: 'Click, fill or select an element. Rejected if the stamp is stale or no mandate covers it.', inputSchema: { type: 'object', properties: { lease: { type: 'string' }, stamp: { type: 'string' }, verb: { enum: ['click', 'fill', 'select'] }, ref: { type: 'string' }, value: { type: 'string' } }, required: ['lease', 'stamp', 'verb', 'ref'] } },
  { name: 'claim', description: 'Claim a lease on a page or record.', inputSchema: { type: 'object', properties: { target: { type: 'string' } }, required: ['target'] } },
  { name: 'release', description: 'Release a lease.', inputSchema: { type: 'object', properties: { lease: { type: 'string' } }, required: ['lease'] } },
  { name: 'handoff', description: 'Pause the lease so a person can act. The page is not readable until they finish.', inputSchema: { type: 'object', properties: { lease: { type: 'string' }, reason: { type: 'string' } }, required: ['lease', 'reason'] } },
];
for (const [label, cmd, args] of [
  ['playwright_mcp', 'node_modules/.bin/playwright-mcp', ['--headless']],
  ['agent_browser_mcp', 'node_modules/.bin/agent-browser', ['mcp']],
]) {
  try {
    const tools = await toolsList(cmd, args);
    results[`schema_${label}`] = { tools: tools.length, est_tokens: tok(JSON.stringify(tools)) };
  } catch (e) { results[`schema_${label}`] = { error: e.message }; }
}
results.schema_small_surface_draft = { tools: OURS.length, est_tokens: tok(JSON.stringify(OURS)), note: 'Our draft, not built' };

// 2. A real scripted task on the stand-in, counting every observation an agent would read.
const portal = await startPortal({});
const S = 't5';
try {
  await login(S, portal.url);
  const steps = [];
  const see = async (label, args = ['snapshot', '-i']) => {
    const out = (await ab(S, args)).out;
    steps.push({ label, chars: out.length, est_tokens: tok(out) });
    return out;
  };
  const s1 = await see('record, interactive');
  await see('record, full tree', ['snapshot']);
  await ab(S, ['fill', refFor(s1, 'answer'), 'Answer text']);
  const s2 = await see('after fill');
  await ab(S, ['click', refFor(s2, 'Save record')]);
  await ab(S, ['wait', '--load', 'load'], { allowFail: true });
  await see('after save');
  results.standin_observations = steps;

  // 3. Live public pages, one read each.
  const live = [];
  for (const [name, url, scope] of [
    ['DPF list', 'https://www.dataprivacyframework.gov/list', null],
    ['ICO search', 'https://ico.org.uk/ESDWebPages/Search', null],
  ]) {
    await ab(S, ['open', url]);
    await ab(S, ['wait', '2500']);
    const full = (await ab(S, ['snapshot'])).out;
    const inter = (await ab(S, ['snapshot', '-i'])).out;
    const compact = (await ab(S, ['snapshot', '-i', '-c'])).out;
    live.push({ name, full_tree_est_tokens: tok(full), interactive_est_tokens: tok(inter), interactive_compact_est_tokens: tok(compact) });
  }
  results.live_pages = live;
} finally {
  await closeAll();
  await portal.close();
}
console.log(JSON.stringify(results, null, 1));
mkdirSync('results', { recursive: true });
writeFileSync('results/t5.json', JSON.stringify(results, null, 2));
process.exit(0);
