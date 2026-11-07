# Project angles for the JetBrains track (ranked)

Baseline: a Wordsmith-track **agentic browser** (an agent that completes a complex end-to-end workflow in a real browser). Each idea below is a developer-facing version of that baseline, run as an **ACP agent or MCP tool inside a JetBrains IDE** (see [02-track.md](02-track.md), section 3, route B+C). Repos are in [03-github-projects.md](03-github-projects.md). Sources are in [sources.md](sources.md).

Shared rules for all four:
- Main feature must carry the demo alone. No dashboard.
- Keep the OpenAI key out of the repo. Log every AI session in `AI_LOG.md`.
- Privacy answer (team rule): all browser runs stay on the developer's machine; the app under test is the developer's own preview URL; no page content leaves the machine except to the model API.

---

## Idea 1 (rank 1): Repro Pilot — bug report in, failing test out

**Pitch.** A developer pastes a bug report into the IDE's AI Chat. The agent opens the app in a real browser, follows the steps, records what it sees (accessibility snapshots, screenshots, console errors), and writes a **failing Playwright test** into the repo. The developer sees the plan, approves it, and reviews the test as a normal diff. It turns "I can't reproduce this" into a red test in minutes.

**Why it is rank 1.** It is the clearest "help the developer" story. It is a complex end-to-end browser workflow (the Wordsmith bar). It fits JetBrains' process requirement (runs in AI Chat via ACP). It also fits Metaview (creativity) and, with Wordsmith's legal bonus, can check the target site's terms before the agent acts.

**Demo flow (step by step, ~3 minutes):**
1. Judge opens WebStorm (or PyCharm) with a small demo app. AI Chat is open with our agent selected.
2. Judge pastes a bug report: "Checkout total is wrong after removing an item." Three steps and an expected result.
3. Agent shows its **plan** (steps it will take) as a document. Judge approves.
4. A browser window opens. The steps play out, with a live snapshot or screenshot on each step in the chat.
5. The step where the bug shows is highlighted with the console error or the wrong total.
6. Agent writes `tests/repro/checkout-total.spec.ts` that fails with the expected vs actual value. The judge sees the **diff**.
7. The judge runs `npx playwright test` in the IDE terminal: red. Then the agent fixes nothing (the brief says reproduction only), and the report says "reproduced, not fixed".

**Other tracks it also enters:** Wordsmith (complex browser workflow, legal bonus if we check robots.txt and terms), Metaview (creative use of agents). Not a fit for Viridien, HRT, G-Research, Bank of Scotland.

**Stack and repos.**
- TypeScript. ACP SDK (`agentclientprotocol/agent-client-protocol`, Apache-2.0) for the agent.
- Playwright MCP (`microsoft/playwright-mcp`, Apache-2.0) for the browser tools. Or Stagehand (`browserbase/stagehand`, MIT) for AI steps.
- Chrome DevTools MCP (`ChromeDevTools/chrome-devtools-mcp`, Apache-2.0) for console and network evidence.
- Ideas from `browser-use/qa-use` and the `anna-pearson/qa-agent` (no licence: ideas only).

**Riskiest part.** The agent reproduces the bug from natural language, reliably enough to show live. Failure mode: wrong element, or the agent gives up.

**Check in under 30 minutes.** Take 3 real GitHub issues with clear repro steps from a small open-source web app. Run the agent's planned steps through Playwright MCP by hand. If 2 of 3 reach the bug, go. If not, narrow to a demo app we control.

**24-hour build plan (rough):**
- 0 to 2 h: repo, ACP agent skeleton that answers in AI Chat. Test in JetBrains. Commit the first `AI_LOG.md` entry.
- 2 to 6 h: Playwright MCP connected. Agent runs three scripted steps on the demo app and reports snapshots.
- 6 to 10 h: plan document step. Approval gate. Live step timeline in the chat.
- 10 to 14 h: test writer. Writes a failing spec from the observed bug. Runs it.
- 14 to 18 h: error states (wrong selector, page did not load, login needed). Privacy and key handling.
- 18 to 21 h: second demo app and two more bug reports. Fix the worst failures.
- 21 to 23 h: feature freeze at 09:00 Sunday (team rule). Record backup video. Write AI log summary.
- 23 to 24 h: submit. Rehearse the 3-minute demo.

---

## Idea 2: Preview Auditor — audit a deployed preview before merge

**Pitch.** After a PR, the agent opens the **preview deployment** and audits it end to end: does the main flow work, are there console or network errors, is a page slow, does the UX break on mobile width. It returns a ranked list of findings, each with a screenshot or trace as evidence, and posts them to the PR or into the IDE's AI Chat.

**Why rank 2.** It is the most direct extension of the baseline (audit a web app end to end). Its output is easy to judge. Weakness: "audit" is broad, and the findings may look generic unless the demo app has planted bugs.

**Demo flow (~3 minutes):**
1. Judge opens a PR in the IDE with a preview URL in the description.
2. Judge runs "Audit preview" in AI Chat.
3. Agent visits the page, runs the main flow, and records the console and network errors (DevTools MCP).
4. A performance trace flags a slow request (DevTools `performance_start_trace`).
5. A mobile-width screenshot shows a button off-screen.
6. Report: four findings, ranked by severity, each linked to its evidence.
7. Judge clicks a finding, and the IDE opens the file that likely caused it.

**Other tracks.** Wordsmith (end-to-end audit), Metaview (creativity). Possibly Bank of Scotland if the demo is a consumer checkout (stretch).

**Stack and repos.**
- `MigoXLab/webqa-agent` (Apache-2.0): audits performance, functionality and UX. Evaluate first; it is small (about 240 stars).
- `ChromeDevTools/chrome-devtools-mcp` (Apache-2.0) for console, network and trace.
- ACP agent wrapper as in Idea 1.

**Riskiest part.** webqa-agent may not run out of the box, or its findings may be noisy. Second risk: preview URLs need a login.

**Check in under 30 minutes.** Clone `MigoXLab/webqa-agent` and run it on one public site and one local demo app. Time it. Count false positives. If it fails, build the audit from DevTools MCP and a checklist.

**24-hour build plan (rough):**
- 0 to 3 h: ACP agent skeleton; DevTools MCP connected; page load and console errors reported.
- 3 to 7 h: main-flow script for the demo app; mobile-width screenshot.
- 7 to 11 h: performance trace; findings schema (severity, evidence, file guess).
- 11 to 15 h: ranked report in AI Chat; click-to-file.
- 15 to 19 h: planted bugs in the demo app; tune the report.
- 19 to 23 h: freeze, backup video, AI log.
- 23 to 24 h: submit.

---

## Idea 3: Test Freezer — explore once, keep the tests

**Pitch.** Browser agents are slow and sometimes vary between runs. So the agent explores a user journey **once**, then freezes the stable steps into plain Playwright code the team keeps. Next runs are fast and deterministic. The IDE shows the frozen test as a normal file, with a note of which steps were agent-chosen and which were fixed.

**Why rank 3.** It answers the main objection to browser agents (flaky and slow) with a clear mechanism. A 2026 guide recommends this exact pattern: "agent explores, then freeze stable journeys into plain Playwright code". Source: [S-F7](sources.md#dev-tools). It is also the easiest to demo.

**Demo flow (~3 minutes):**
1. Judge gives the agent a journey: "sign up, add an item, check out".
2. Agent explores in a live browser and shows each choice it made.
3. Agent writes a Playwright spec and tags each step: fixed, or agent-healed.
4. Judge changes a button label in the demo app. The frozen test fails with a clear message.
5. The agent heals the one step, shows the diff, and the test passes again.

**Other tracks.** Wordsmith (end-to-end workflow with a repeatable output), JetBrains. Possibly Metaview.

**Stack and repos.** Stagehand (`browserbase/stagehand`, MIT) for the act and observe steps. Plain Playwright for the output. `MyNameIsEdi/open-qa` (MIT) and `desplega-ai/qa-use` (MIT) for ideas.

**Riskiest part.** Freezing a journey into stable selectors. Agents often pick brittle selectors.

**Check in under 30 minutes.** Explore one demo journey with Stagehand. Freeze it by hand. Change one label. See if the frozen test fails cleanly.

**24-hour build plan (rough):** explore loop (5 h), freeze and tag steps (4 h), self-heal and diff (4 h), demo app with a planted change (2 h), IDE integration and log (4 h), freeze, backup video, submit (5 h).

---

## Idea 4: Adaptive Coding Agent with browser check (team option A, extended)

**Pitch.** The team's option A: an IDE agent that behaves differently for three personas (a beginner, an engineer who wants speed, and a persona of our design). Extended with a browser check: when the agent changes a web page, it opens the page and confirms the change shows. The beginner persona explains and asks guiding questions. The engineer persona does exactly what was asked.

**Why rank 4.** It fits the most tracks (InstaLILY, JetBrains, Metaview). It is the strongest on "AI that works alongside development" and "developer education" (the JetBrains brief names both). But the InstaLILY team kit (hidden tests, evaluator harness) is **not read yet**, and this risks a diluted demo. Use it only if the InstaLILY brief confirms the fit.

**Demo flow (~3 minutes):**
1. Judge picks "Beginner" persona. Asks about a broken `for` loop. The agent asks what they expected, and does not fix it.
2. Judge switches to "Engineer". Same bug. The agent fixes it in one diff, runs the test, and says what it changed.
3. Agent opens the page and confirms the output matches.
4. Judge picks the team's third persona (for example a teacher who wants a quiz).

**Other tracks.** InstaLILY (primary), JetBrains, Metaview.

**Stack and repos.** ACP agent (TypeScript). The Cline Plan & Act and Roo Code mode ideas (borrow). Playwright MCP for the browser check. Koog is only useful if we write Kotlin (no).

**Riskiest part.** The scoring of "adapts to the user" is subjective and unseen until the brief is read.

**Check in under 30 minutes.** Scan the InstaLILY QR code for the full brief and team kit. Decide go or no-go on that alone.

**24-hour build plan (rough):** persona prompts and gating (4 h), ACP skeleton and bug fixture (3 h), browser check (4 h), harness and evaluation runs (5 h), demo polish and log (4 h), freeze and submit (4 h).

---

## Ranking summary

| Rank | Idea | Tracks it enters (in this team's list) | Riskiest part | Check time |
|---|---|---|---|---|
| 1 | Repro Pilot | JetBrains, Wordsmith, Metaview | Reliable reproduction from natural language | 30 min: 3 real issues |
| 2 | Preview Auditor | JetBrains, Wordsmith, Metaview | webqa-agent runs and is not noisy | 30 min: run webqa-agent |
| 3 | Test Freezer | JetBrains, Wordsmith, Metaview | Stable selectors after freezing | 30 min: freeze one journey |
| 4 | Adaptive Coding Agent + browser check | InstaLILY, JetBrains, Metaview | Hidden test kit not read | 30 min: read InstaLILY QR |

**Recommendation:** Idea 1, with Idea 3's freeze step as a stretch. It gives the cleanest demo on the baseline and fits JetBrains' process rule.
