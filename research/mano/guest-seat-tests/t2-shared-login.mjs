// T2: two agent-browser sessions plus a scripted "person" against one portal login.
// Each experiment records raw outcomes. Nothing here is a real person; see README limits.
import { writeFileSync, mkdirSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { startPortal, ACCOUNT } from './portal.mjs';
import { ab, refFor, login, closeAll } from './lib.mjs';

const results = {};
const quiet = { allowFail: true };
const value = async (s, name) => (await ab(s, ['eval', `document.querySelector('[name=${name}]').value`], quiet)).out.replace(/^"|"$/g, '');
const snap = async (s, opts) => (await ab(s, ['snapshot', '-i'], opts)).out;
const save = async (s, opts) => {
  await ab(s, ['click', refFor(await snap(s, opts), 'Save record')], opts);
  await ab(s, ['wait', '--load', 'load'], { ...quiet, ...opts });
};
const stateFile = path.join(tmpdir(), `gs-state-${process.pid}.json`);

async function experiment(name, fn) {
  const portal = await startPortal({ singleSession: name === 'E_forced_logout' });
  try {
    results[name] = await fn(portal);
  } catch (e) {
    results[name] = { error: String(e.message).slice(0, 600) };
  }
  console.log(name, JSON.stringify(results[name], null, 1));
  await closeAll();
  await portal.close();
}

// A. Does a saved state file carry the whole login, including MFA, to a second browser?
await experiment('A_state_file_shares_login', async (p) => {
  await login('a', p.url);
  await ab('a', ['state', 'save', stateFile]);
  await ab('b', ['open', `${p.url}/record`], { extra: ['--state', stateFile] });
  const url = (await ab('b', ['get', 'url'])).out;
  const logins = p.state().log.filter((e) => e.type === 'login').length;
  return { b_landed_on: url.replace(p.url, ''), portal_login_events: logins, mfa_skipped_by_b: url.endsWith('/record') };
});

// B. Two browsers, one account, overlapping edits of one form. Who survives, and can the portal tell?
await experiment('B_lost_update_two_browsers', async (p) => {
  await login('a', p.url);
  await ab('a', ['state', 'save', stateFile]);
  await ab('b', ['open', `${p.url}/record`], { extra: ['--state', stateFile] });
  const sa = await snap('a'); const sb = await snap('b');
  await ab('a', ['fill', refFor(sa, 'answer'), 'A wrote this']);
  await ab('b', ['fill', refFor(sb, 'vat'), 'GB999999999']);
  await save('a');
  await save('b');
  const st = p.state();
  return {
    final_answer: st.record.answer, final_vat: st.record.vat,
    a_answer_lost: st.record.answer !== 'A wrote this',
    portal_log: st.log.filter((e) => e.type === 'record_saved').map(({ account, sid, changed }) => ({ account, sid, changed })),
  };
});

// C. Two agent-browser sessions attached to ONE Chrome over CDP. Does B's navigation move A?
await experiment('C_one_chrome_two_sessions', async (p) => {
  await login('a', p.url);
  const cdp = (await ab('a', ['get', 'cdp-url'])).out;
  const extra = ['--cdp', cdp];
  const out = { b_attach: (await ab('b', ['get', 'url'], { allowFail: true, extra })) };
  out.b_attach = { ok: out.b_attach.ok, url: out.b_attach.out.replace(p.url, ''), err: out.b_attach.err.slice(0, 200) };
  const sa = await snap('a');
  const answer = refFor(sa, 'answer');
  const opened = await ab('b', ['open', `${p.url}/login`], { allowFail: true, extra });
  out.b_open_ok = opened.ok;
  out.a_url_after_b_open = (await ab('a', ['get', 'url'])).out.replace(p.url, '');
  const fill = await ab('a', ['fill', answer, 'A after B navigated'], quiet);
  out.a_fill_after_b_open = { ok: fill.ok, msg: (fill.out || fill.err).slice(0, 200) };
  out.tabs_seen_by_a = (await ab('a', ['tab', 'list'], quiet)).out.replaceAll(p.url, '').slice(0, 300);
  const closed = await ab('b', ['close'], { allowFail: true, extra });
  out.b_close_ok = closed.ok;
  const alive = await ab('a', ['get', 'url'], quiet);
  out.a_alive_after_b_close = alive.ok;
  return out;
});

// D. Same session name used by two agents: the unnamed-session trap. What happens to held refs?
await experiment('D_refs_across_navigation', async (p) => {
  await login('a', p.url);
  const rec = await snap('a');
  const answer = refFor(rec, 'answer');
  await ab('a', ['open', `${p.url}/login`]); // the "other agent" navigates the shared session
  const onOther = await ab('a', ['fill', answer, 'wrong page?'], quiet);
  const login_username = await value('a', 'user');
  await ab('a', ['open', `${p.url}/record`]);
  const backOnRecord = await ab('a', ['fill', answer, 'after coming back'], quiet);
  return {
    held_ref: answer,
    fill_on_other_page: { ok: onOther.ok, msg: (onOther.out || onOther.err).slice(0, 200) },
    other_page_username_field_now: login_username,
    fill_after_returning: { ok: backOnRecord.ok, msg: (backOnRecord.out || backOnRecord.err).slice(0, 200) },
    value_after_returning: await value('a', 'answer'),
  };
});

// E. Portal enforces one session per account (OUR assumption, Browserbase documents such sites).
// Does the logged-out agent find out, or does the tool report success?
await experiment('E_forced_logout', async (p) => {
  await login('a', p.url);
  const sa = await snap('a');
  await ab('a', ['fill', refFor(sa, 'answer'), 'A wrote this']);
  await login('b', p.url); // kicks A out
  const click = await ab('a', ['click', refFor(sa, 'Save record')], quiet);
  await ab('a', ['wait', '--load', 'load'], quiet);
  const url = (await ab('a', ['get', 'url'])).out.replace(p.url, '');
  return {
    a_click_reported: { ok: click.ok, msg: (click.out || click.err).slice(0, 200) },
    a_url_after_click: url,
    saved_on_portal: p.state().record.answer === 'A wrote this',
    forced_logouts: p.state().log.filter((e) => e.type === 'forced_logout_others').length,
  };
});

// F. Takeover: the agent stops at MFA, a second connection (the scripted person) enters the code in
// the same tab, the agent resumes. Also: can the agent read the code while it sits in the field?
await experiment('F_takeover_same_tab', async (p) => {
  await ab('a', ['open', `${p.url}/login`]);
  let s = await snap('a');
  await ab('a', ['fill', refFor(s, 'Username'), ACCOUNT.user]);
  await ab('a', ['fill', refFor(s, 'Password'), ACCOUNT.pass]);
  await ab('a', ['click', refFor(s, 'Sign in')]);
  await ab('a', ['wait', 'input[name=code]']);
  const cdp = (await ab('a', ['get', 'cdp-url'])).out;
  const extra = ['--cdp', cdp];
  const person = await ab('person', ['get', 'url'], { allowFail: true, extra });
  const sp = (await ab('person', ['snapshot', '-i'], { allowFail: true, extra })).out;
  await ab('person', ['fill', refFor(sp, 'One-time code'), ACCOUNT.mfa], { extra });
  const agentView = await snap('a');
  await ab('person', ['click', refFor(sp, 'Verify')], { extra });
  await ab('a', ['wait', 'input[name=company]']);
  const after = await snap('a');
  await ab('a', ['fill', refFor(after, 'answer'), 'agent resumed']);
  await save('a');
  return {
    person_attached: person.ok,
    agent_snapshot_exposed_code: agentView.includes(ACCOUNT.mfa),
    agent_view_of_code_field: agentView.split('\n').find((l) => l.includes('One-time code')),
    password_masked_in_snapshot: !s.includes(ACCOUNT.pass),
    agent_resumed_and_saved: p.state().record.answer === 'agent resumed',
    portal_login_events: p.state().log.filter((e) => e.type === 'login').length,
  };
});

// G. Same Chrome again, but B moves the shared tab to ANOTHER supplier's identical form.
// Does A's held ref fail, or write into the wrong record while reporting success?
await experiment('G_held_ref_wrong_record', async (p) => {
  await login('a', p.url);
  const extra = ['--cdp', (await ab('a', ['get', 'cdp-url'])).out];
  const before = await snap('a');
  const answer = refFor(before, 'answer');
  const savedRef = refFor(before, 'Save record');
  await ab('b', ['open', `${p.url}/record-b`], { extra });
  const fill = await ab('a', ['fill', answer, 'meant for Acme'], quiet);
  const title = await ab('a', ['eval', `document.querySelector('h1').textContent`], quiet);
  const landed = await value('a', 'answer');
  const saveClick = await ab('a', ['click', savedRef], quiet);
  await ab('a', ['wait', '--load', 'load'], quiet);
  await new Promise((r) => setTimeout(r, 150));
  const committed = p.state();
  // Does a separate tab per session prevent it? A pins its tab, B works in a new tab.
  await ab('a', ['open', `${p.url}/record`]);
  const answer2 = refFor(await snap('a'), 'answer');
  const newTab = await ab('b', ['tab', 'new', `${p.url}/record-b`], { allowFail: true, extra });
  const fill2 = await ab('a', ['fill', answer2, 'meant for Acme 2'], quiet);
  const a_page = await ab('a', ['eval', `document.querySelector('h1').textContent`], quiet);
  return {
    same_tab: { a_fill: { ok: fill.ok, msg: (fill.out || fill.err).slice(0, 160) }, page_now: title.out, value_in_that_page: landed, a_held_save_click: { ok: saveClick.ok, msg: (saveClick.out || saveClick.err).slice(0, 160) }, bravo_record_answer_on_portal: committed.recordB.answer, acme_record_answer_on_portal: committed.record.answer },
    b_new_tab: { b_tab_new_ok: newTab.ok, a_fill: { ok: fill2.ok, msg: (fill2.out || fill2.err).slice(0, 160) }, a_page_now: a_page.out, a_value: await value('a', 'answer') },
  };
});

// H. Does --pin-tab keep two sessions apart in one Chrome? Used as documented: both sessions
// attach over CDP with --pin-tab on their first command. Cookies are shared, so B needs no login.
await experiment('H_pin_tab', async (p) => {
  const pa = `pin-a-${process.pid}`, pb = `pin-b-${process.pid}`;
  await ab('host', ['open', 'about:blank']);
  const cdp = (await ab('host', ['get', 'cdp-url'])).out;
  const opts = { extra: ['--cdp', cdp, '--pin-tab'], allowFail: true };
  await login(pa, p.url, { extra: opts.extra });
  await ab(pb, ['open', `${p.url}/record-b`], opts);
  const bLanded = (await ab(pb, ['get', 'url'], opts)).out.replace(p.url, '');
  const answerA = refFor((await ab(pa, ['snapshot', '-i'], opts)).out, 'answer');
  const answerB = refFor((await ab(pb, ['snapshot', '-i'], opts)).out, 'answer');
  const fa = await ab(pa, ['fill', answerA, 'meant for Acme'], opts);
  const fb = await ab(pb, ['fill', answerB, 'meant for Bravo'], opts);
  const h1 = `document.querySelector('h1').textContent`;
  const val = `document.querySelector('[name=answer]').value`;
  const out = {
    b_landed_without_login: bLanded,
    a_page: (await ab(pa, ['eval', h1], opts)).out, b_page: (await ab(pb, ['eval', h1], opts)).out,
    a_fill_ok: fa.ok, b_fill_ok: fb.ok,
    a_value: (await ab(pa, ['eval', val], opts)).out, b_value: (await ab(pb, ['eval', val], opts)).out,
  };
  // B tries to take A's tab.
  const tabs = await ab(pb, ['tab', 'list'], opts);
  out.tabs_seen_by_b = tabs.out.replaceAll(p.url, '').slice(0, 300);
  const firstTab = /\[(t\d+)\]/.exec(tabs.out)?.[1];
  const steal = await ab(pb, ['tab', firstTab ?? 't1'], opts);
  out.b_tab_switch = { tried: firstTab, ok: steal.ok, msg: (steal.out || steal.err).split('\n').filter((l) => !l.includes('behind the current')).join(' ').slice(0, 200) };
  out.kept_apart = out.a_value.includes('Acme') && out.b_value.includes('Bravo') && out.a_page.includes('Supplier record') && !out.a_page.includes('Bravo');
  return out;
});

rmSync(stateFile, { force: true });
mkdirSync('results', { recursive: true });
writeFileSync('results/t2.json', JSON.stringify(results, null, 2));
process.exit(0);
