# Project angles for the InstaLILY track

Ranked. Each one builds on the baseline agentic browser (Wordsmith) where it honestly can. Research basis is in `02-track.md`, `03-github-projects.md` and `04-ui-design.md`.

Ranking criteria: hidden-test value first (stage 1 is a gate), then persona visibility (stage 2 and 3), then build risk in 24 hours.

## 1. "Same bug, three answers": a persona-routed coding agent with a hint ladder (recommended)

**Pitch.** One agent, one repo, three personas switched on screen. The beginner gets a question and a hint ladder, not the fix. The engineer gets a minimal diff, a test run and a one-line report. The third persona (a teacher marking a class's code, or a hardware engineer) gets its own tool set and check. Persona changes tools and defaults, not just tone. The agent never claims a test passed unless it ran.

**Demo flow (for the InstaLILY engineers):**
1. Open the repo with a broken `for` loop (off-by-one). Persona bar shows "Beginner".
2. Agent reads the code, does not edit. It asks one question: "Which number should the loop stop at?" Offers hint level 1 (orientation: look at the condition).
3. Learner clicks "show me more": hint level 2 (next step), then level 3 (worked example on a different loop), then level 4 (exact line, only if asked twice).
4. Judge switches to "Engineer". Same bug. Agent makes a one-line diff, runs the test command, reports "1 test failed before, passes now. Not verified: edge case with empty list."
5. Judge switches to "Teacher" (third persona). Agent reads three student files, lists a check per file and asks the teacher to confirm the rubric before marking.
6. End on the honest report panel: verified, not verified.

**Other tracks it also enters:** none strongly. Metaview (best overall) is possible if the persona demo is memorable. JetBrains ("Help the developer") fits if the IDE is JetBrains and the team uses their agent in the IDE, which the brief requires for JetBrains.

**Stack and repos it builds on:**
- Agent loop: an existing open coding agent as reference (Aider edit formats for the engineer persona; Claude Code Learning pattern as an idea for the beginner).
- Persona tools: Zed-style tool profiles (Write, Ask, Minimal) as the mechanism.
- Hidden-test runner: SWE-bench harness pattern, small version: task folder, test command, pass/fail summary.
- Model: the team kit's LLM for stage 1 alignment; a local quantised model is a fallback (Hamish's local AI and quantisation experience).
- Baseline browser (optional): Playwright MCP for the beginner's "show me the page" step, behind a flag.

**Riskiest part and 30-minute check.** Risk: the hidden tests and kit harness are unknown until the QR brief and kit are read. Check: spend 30 min at the booth or scan the QR code. Confirm (a) how the harness calls our agent (CLI, API or plugin), (b) which language the repo is in, (c) the LLM provider and token budget. Also run `aider --help` style check on our chosen loop to confirm it can run headless.

**24-hour build plan:**
- 0 to 2 h: read the QR brief and kit. Freeze the interface to the harness.
- 2 to 6 h: core agent loop that edits a file and runs a test command. Pass a tiny local hidden-test set of 5 cases.
- 6 to 10 h: persona tool profiles (Beginner: read and question first; Engineer: full write; Third: own rubric).
- 10 to 13 h: hint ladder for the beginner (4 levels). Test the `for` loop example end to end.
- 13 to 16 h: honest report panel, step timeline (5 rows). Stop features here.
- 16 to 19 h: run the kit's evaluator. Fix failures in the core first.
- 19 to 21 h: persona UI polish and the on-screen switch.
- 21 to 23 h: rehearse the three-persona demo twice. Record a backup video.
- 23 h to 09:00 Sunday: feature freeze at 09:00 (team rule). Only fixes after that.

## 2. Verified-only engineer agent: "says what it ran" (minimal diff plus honest report)

**Pitch.** Narrow and strong: an agent that changes the smallest amount needed, runs the tests, and writes a report that separates verified from unverified. It addresses the brief's stage 2 directly ("does what was asked, no more, and reports honestly"). It is the engineer persona and the honesty layer, built to be the best in the room at that.

**Demo flow:**
1. Give a task with an extra temptation (a refactor is visible nearby).
2. Agent makes only the requested change. Shows the diff.
3. Runs the test command. Shows output.
4. Report: "Changed 1 line in `loop.py`. Ran `pytest`: 4 passed. Not verified: the CLI flag." Judges check the claim against the output.
5. Give the agent a task it cannot finish (missing dependency). It stops and says so. No fake success.

**Other tracks:** JetBrains (AI development quality) and Metaview.

**Stack:** Aider edit format for minimal diffs; SWE-agent's limited tool surface; SWE-bench harness pattern.

**Riskiest part and 30-minute check:** The agent must not claim a verification it did not run. Check: write three tasks where one cannot pass and confirm the report says so. 30 minutes.

**24-hour build plan:** 0 to 4 h core edit and run loop; 4 to 8 h diff display and report schema; 8 to 14 h the three hidden-test-like tasks; 14 to 20 h honest-report edge cases; 20 to 24 h demo and video. Thin on persona: must be combined with idea 1 to score stage 2 across personas.

## 3. Beginner-first explainer with live browser proof (the baseline fit)

**Pitch.** The beginner's agent explains each step and shows the relevant documentation page in a browser pane, then renders a small output (a page or a plot) so the learner sees what their loop did. This is the one place the agentic-browser baseline is genuinely useful for InstaLILY.

**Demo flow:** learner asks why their loop prints wrong values. Agent opens the matching MDN or Python docs page in a browser pane (Playwright MCP), highlights the section, then runs the loop and shows the printed output in the pane. Asks one guiding question.

**Other tracks:** Wordsmith (complex end-to-end browser workflow), JetBrains lightly.

**Stack:** browser-use or Playwright MCP; the same agent core as idea 1.

**Riskiest part and 30-minute check:** browser latency and flakiness on stage. Check: time five page loads on the venue network. If above 3 s each, use cached doc snapshots.

**Honest trade-off:** adds risk and does not help hidden tests. Only build it as a supporting feature on top of idea 1.

**24-hour build plan:** 0 to 6 h beginner loop from idea 1; 6 to 12 h browser pane and docs fetch with cache; 12 to 18 h run-and-show output; 18 to 24 h demo. Only if idea 1 is passing its core tests by hour 12.

## 4. Persona-coverage evaluator (a judge that scores our own agent per persona)

**Pitch.** A small harness that runs each persona against the same tasks, scores each run with a rubric (does what was asked, asked only when needed, reported honestly), and prints a per-persona table. This turns "understanding the user" into a number we can improve before the judges arrive.

**Demo flow:** run the harness live: three personas by five tasks, a table with scores. Show one failing cell and the fix.

**Other tracks:** Metaview (creativity in evaluation), G-Research (make hidden patterns visible in our own agent's behaviour).

**Stack:** LLM-as-judge with rubric (Zheng et al., MT-Bench: GPT-4 judge agreed with humans about 80% of the time; known biases: position, verbosity, self-enhancement). Persona simulation (Park et al. generative agents as a method for simulated users). Use the kit's LLM as the judge, not ours, to avoid marking our own work.

**Riskiest part and 30-minute check:** the judge may favour long answers (verbosity bias). Check: score two answers that differ only in length. If the longer one wins more than half the time, add a length penalty.

**24-hour build plan:** 0 to 4 h rubric and 15 test runs; 4 to 10 h harness and table; 10 to 16 h tune rubric against three hand-scored examples; 16 to 24 h use the table to fix the worst persona. Good as a supporting tool; weak as a standalone demo.

## 5. Third persona options (rationale, to pick one)

- **Teacher marking a class's code:** a clear use case; the agent gives a check per file and asks the rubric first. Strong demo.
- **Hardware or embedded engineer:** a fit for Mano's embedded background, but a harder demo.
- **Non-technical founder:** a plan-first persona (Lovable and Replit Plan mode pattern). Easy to demo, but close to existing products.
- **Screen-reader user:** strong for inclusion; research shows structure-aware navigation helps (Penn State Grid Editor, Microsoft CodeTalk). Harder in 24 hours.
- **Reviewer of AI-written code:** a good fit with the team's Diff Risk idea, but it moves away from building code.

Recommendation: teacher marking, because the demo is clear and the rubric is easy to show.

## Ranking summary

| Rank | Angle | Hidden-test value | Persona visibility | Build risk | Baseline fit |
|---|---|---|---|---|---|
| 1 | Same bug, three answers | High | Very high | Medium | Optional |
| 2 | Verified-only engineer agent | High | Medium | Low | None |
| 3 | Beginner explainer with browser proof | Low | High | High | Strong |
| 4 | Persona-coverage evaluator | Medium | Low (internal) | Medium | None |
| 5 | Third persona (teacher) | n/a | High | Low to medium | None |

Idea 1 with idea 2's honesty layer is the recommended combined entry. Idea 3 is the baseline's best fit, to be added only if the core is solid.
