// T3: the smallest stale-action gate, and where it stops working.
// observe() stamps a snapshot with a digest. gatedFill() re-reads and drops the action on mismatch.
import { createHash } from 'node:crypto';
import { writeFileSync, mkdirSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { startPortal } from './portal.mjs';
import { ab, refFor, login, closeAll } from './lib.mjs';

const N = Number(process.env.N ?? 20);
const quiet = { allowFail: true };
const results = { N };
// Ref numbers are stripped: they can change on reload without the page changing.
const digest = (s) => createHash('sha256').update(s.replace(/ref=e\d+/g, 'ref')).digest('hex').slice(0, 12);
const value = async (s, name) => (await ab(s, ['eval', `document.querySelector('[name=${name}]').value`], quiet)).out.replace(/^"|"$/g, '');
const humanEdit = (s, text) => ab(s, ['eval', `{const e=document.querySelector('[name=answer]');e.value=${JSON.stringify(text)};e.dispatchEvent(new Event('input',{bubbles:true}));}`]);
const pct = (xs, p) => [...xs].sort((a, b) => a - b)[Math.min(xs.length - 1, Math.floor(xs.length * p))];
const round = (x) => Math.round(x);
const refsOf = (s) => [...s.matchAll(/ref=(e\d+)/g)].map((m) => m[1]).join(',');

async function observe(s, args = ['snapshot', '-i']) {
  const out = (await ab(s, args)).out;
  return { snapshot: out, digest: digest(out), args };
}
async function gatedFill(s, stamp, ref, text) {
  const t0 = performance.now();
  const now = await observe(s, stamp.args);
  const checkMs = performance.now() - t0;
  if (now.digest !== stamp.digest) return { dispatched: false, checkMs };
  await ab(s, ['fill', ref, text]);
  return { dispatched: true, checkMs };
}
async function reset(s, base) {
  await ab(s, ['open', `${base}/record`]);
  await ab(s, ['wait', 'input[name=company]']);
}

const portal = await startPortal({});
const clockPortal = await startPortal({ clock: true });
try {
  await login('g', portal.url);

  // Control for the digest: do ref numbers survive a reload of an unchanged page?
  {
    await reset('g', portal.url);
    const a = (await ab('g', ['snapshot', '-i'])).out;
    await reset('g', portal.url);
    const b = (await ab('g', ['snapshot', '-i'])).out;
    results.ref_numbers_after_reload = { before: refsOf(a), after: refsOf(b), raw_snapshot_identical: a === b };
    console.log('refs', results.ref_numbers_after_reload);
  }

  // Case 1: a person edits the field in the same tab between observe and act.
  for (const gated of [false, true]) {
    let humanSurvived = 0, dropped = 0;
    const checks = [];
    for (let i = 0; i < N; i++) {
      await reset('g', portal.url);
      const stamp = await observe('g');
      const ref = refFor(stamp.snapshot, 'answer');
      await humanEdit('g', `human ${i}`);
      if (gated) {
        const r = await gatedFill('g', stamp, ref, `agent ${i}`);
        checks.push(r.checkMs);
        if (!r.dispatched) dropped++;
      } else {
        await ab('g', ['fill', ref, `agent ${i}`]);
      }
      if ((await value('g', 'answer')) === `human ${i}`) humanSurvived++;
    }
    results[gated ? 'case1_with_gate' : 'case1_no_gate'] = { trials: N, human_text_survived: humanSurvived, dropped, gate_check_ms_median: checks.length ? round(pct(checks, 0.5)) : null, gate_check_ms_p95: checks.length ? round(pct(checks, 0.95)) : null };
    console.log(gated ? 'case1 gate' : 'case1 none', results[gated ? 'case1_with_gate' : 'case1_no_gate']);
  }

  // Case 2: an unrelated live element ticks. No real conflict, so every drop here is a false alarm.
  await login('c', clockPortal.url);
  for (const [label, args] of [['full_snapshot', ['snapshot']], ['interactive_only', ['snapshot', '-i']]]) {
    let falseDrops = 0;
    for (let i = 0; i < N; i++) {
      await reset('c', clockPortal.url);
      const stamp = await observe('c', args);
      const ref = refFor((await ab('c', ['snapshot', '-i'])).out, 'answer');
      await new Promise((r) => setTimeout(r, 300));
      const r = await gatedFill('c', stamp, ref, 'agent');
      if (!r.dispatched) falseDrops++;
    }
    results[`case2_clock_${label}`] = { trials: N, false_drops: falseDrops };
    console.log('case2', label, results[`case2_clock_${label}`]);
  }

  // Case 3: another actor saves through a different browser. The agent's open tab shows nothing.
  const stateFile = path.join(tmpdir(), `gs-state3-${process.pid}.json`);
  await ab('g', ['state', 'save', stateFile]);
  await ab('other', ['open', `${portal.url}/record`], { extra: ['--state', stateFile] });
  await ab('reader', ['open', `${portal.url}/record`], { extra: ['--state', stateFile] });
  rmSync(stateFile, { force: true });
  for (const variant of ['tab_digest_only', 'fresh_reader_session', 'fresh_reader_control_no_change']) {
    let overwritten = 0, dropped = 0;
    const checks = [];
    for (let i = 0; i < N; i++) {
      await reset('g', portal.url);
      await reset('reader', portal.url);
      const stamp = await observe('g');
      const readerStamp = await observe('reader');
      const ref = refFor(stamp.snapshot, 'po_ref');
      const save = refFor(stamp.snapshot, 'Save record');
      const control = variant.endsWith('no_change');
      // the other side changes a field on the server (skipped in the control)
      if (!control) {
        await reset('other', portal.url);
        const so = (await ab('other', ['snapshot', '-i'])).out;
        await ab('other', ['fill', refFor(so, 'bank_account'), `other side ${i}`]);
        await ab('other', ['click', refFor(so, 'Save record')]);
        await ab('other', ['wait', '--load', 'load'], quiet);
        await new Promise((r) => setTimeout(r, 100));
      }
      const t0 = performance.now();
      let go = (await observe('g')).digest === stamp.digest;
      if (variant.startsWith('fresh_reader')) {
        await reset('reader', portal.url);
        go = go && (await observe('reader')).digest === readerStamp.digest;
      }
      checks.push(performance.now() - t0);
      if (!go) { dropped++; continue; }
      await ab('g', ['fill', ref, `PO-agent-${i}`]);
      await ab('g', ['click', save]);
      await ab('g', ['wait', '--load', 'load'], quiet);
      await new Promise((r) => setTimeout(r, 100));
      if (!control && portal.state().record.bank_account !== `other side ${i}`) overwritten++;
    }
    results[`case3_${variant}`] = { trials: N, other_actor_change_overwritten: overwritten, dropped, check_ms_median: round(pct(checks, 0.5)) };
    console.log('case3', variant, results[`case3_${variant}`]);
  }

  // Case 4: the race the gate cannot close. The in-page timer lands the person's edit at a random
  // moment after the check starts, so it can fall between the check and the dispatch.
  {
    const bins = { human_lost_despite_gate: 0, human_kept_dropped: 0, human_edit_landed_after_fill: 0, no_edit_seen: 0 };
    const trials = N * 2;
    const lost = [];
    for (let i = 0; i < trials; i++) {
      await reset('g', portal.url);
      const stamp = await observe('g');
      const ref = refFor(stamp.snapshot, 'answer');
      const delay = Math.round(Math.random() * 200);
      await ab('g', ['eval', `{window.__landed=0;setTimeout(()=>{const e=document.querySelector('[name=answer]');e.value='human';window.__landed=performance.now();},${delay});}`]);
      const r = await gatedFill('g', stamp, ref, 'agent');
      await new Promise((res) => setTimeout(res, 250));
      const v = await value('g', 'answer');
      if (!r.dispatched) bins.human_kept_dropped++;
      else if (v === 'agent') { bins.human_lost_despite_gate++; lost.push(delay); }
      else if (v === 'human') bins.human_edit_landed_after_fill++;
      else bins.no_edit_seen++;
    }
    results.case4_race = { trials, ...bins, note: 'human_edit_landed_after_fill means the agent text was replaced by the person, so nothing of the person is lost' };
    console.log('case4', results.case4_race);
  }

  // Case 6: same aimed race, but the check and the write are one synchronous step inside the page.
  // Page JavaScript is single-threaded, so an in-tab edit cannot land between them.
  {
    const bins = { human_lost: 0, refused_stale: 0, written_then_human_edit_landed: 0, other: 0 };
    const trials = N * 2;
    for (let i = 0; i < trials; i++) {
      await reset('g', portal.url);
      const delay = Math.round(Math.random() * 200);
      await ab('g', ['eval', `{window.__t=setTimeout(()=>{document.querySelector('[name=answer]').value='human';},${delay});}`]);
      await ab('g', ['snapshot', '-i']); // same observe cost as the gate above, keeps the timing comparable
      const r = await ab('g', ['eval', `(()=>{const e=document.querySelector('[name=answer]');if(e.value!=='')return 'stale';const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;set.call(e,'agent');e.dispatchEvent(new Event('input',{bubbles:true}));return 'written';})()`]);
      await new Promise((res) => setTimeout(res, 250));
      const v = await value('g', 'answer');
      if (r.out.includes('stale')) bins.refused_stale++;
      else if (v === 'human') bins.written_then_human_edit_landed++; // the person's later edit won
      else if (v === 'agent') bins.human_lost++; // written, and the person's edit is gone
      else bins.other++;
    }
    results.case6_atomic_check_and_set = { trials, ...bins };
    console.log('case6', results.case6_atomic_check_and_set);
  }

  // Case 5: drop, re-observe, then fill only the fields the agent still owns.
  {
    await reset('g', portal.url);
    const stamp = await observe('g');
    await humanEdit('g', 'human answer');
    const r = await gatedFill('g', stamp, refFor(stamp.snapshot, 'answer'), 'agent answer');
    const fresh = await observe('g');
    const answerLine = fresh.snapshot.split('\n').find((l) => l.includes('"answer"'));
    const stillOwned = !/: \S/.test(answerLine); // the agent only owns the answer if it is still empty
    if (stillOwned) await ab('g', ['fill', refFor(fresh.snapshot, 'answer'), 'agent answer']);
    const vat = await gatedFill('g', fresh, refFor(fresh.snapshot, 'vat'), 'GB222222222');
    results.case5_recover = { first_action_dropped: !r.dispatched, agent_left_answer_alone: !stillOwned, vat_filled: vat.dispatched, final_answer: await value('g', 'answer'), final_vat: await value('g', 'vat') };
    console.log('case5', results.case5_recover);
  }
} finally {
  mkdirSync('results', { recursive: true });
  writeFileSync('results/t3.json', JSON.stringify(results, null, 2));
  await closeAll();
  await portal.close();
  await clockPortal.close();
}
process.exit(0);
