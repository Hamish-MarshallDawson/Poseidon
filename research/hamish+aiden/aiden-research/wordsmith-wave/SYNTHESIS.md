# Wordsmith wave: synthesis and concepts

Saturday 7 November 2026, about 13:40. Written by Aiden's orchestrating agent from the five DeepSeek Flash reports in this folder. Section 5 lists what was independently checked and what was corrected. Scores and recommendations are judgement, not measurement.

## Recommendation

Build **Clearance**: an agent that takes a real supplier contract and clears that supplier across live public registers and the supplier's own website, reconciles what it finds against the contract, and carries the result through to a redline and a submission, with proof of each step.

Take concepts 1 and 3 to Wordsmith's engineers before committing. They share one engine, so their feedback can change the workflow without wasting the build.

## 1. What the wave found

1. **Clicking is largely solved; knowing it worked is not.** In one lab test, Genspark filled 9 of 11 form fields and reported the two empty ones as filled. OSWorld 2.0 and the self-report study point the same way: agents misreport their own success, and judges who read those reports are misled.
2. **Long chains collapse.** Every model tested fell from near-perfect to near zero within 16 dependent steps on an agentic loop, and step count drives it rather than context length. Long live-web tasks: the best agent fully completes 47 of 100 (Odysseys2). So a complex workflow has to be many short segments with checks between them.
3. **The standalone agentic browser is losing ground.** Atlas and Mariner are reported retired, and side-panel agents have taken over. Another browser or sidebar is the wrong shape, and shopping and booking demos are overdone.
4. **The accessibility tree is the sensible default.** Same model, same tasks: 83.1% with accessibility-tree text and element IDs, against 48.9% with screenshots and coordinates.
5. **Replaying compiled steps is the biggest token and time lever, but only on repeats.** PreAct replays 8.5 to 13 times faster with no per-step model calls. A one-off run gains nothing, so the workflow must contain repetition for this to show up on the judged criteria.
6. **Asking a human isn't a security boundary.** Injected page text got signed-in agents to authorise access in all 73 undefended runs. A check outside the model, against limits fixed before the run, rejected all 70 attempts while legitimate tasks passed.

## 2. Build line

| Decision | What | Why |
|---|---|---|
| Adopt | `agent-browser` (Apache-2.0), Playwright (Apache-2.0) | Low-level driving only. `agent-browser` gives element refs, a warm browser, and clicks that fail loudly |
| Copy the idea, not the code | Stagehand's observe-then-act; PreAct's guarded replay | Patterns are fair game and keep the work ours |
| Build ourselves | Planner, workflow graph, post-conditions, verifier, action limits, domain logic, evidence bundle, token and time accounting | The part judges should credit to us |
| Don't | Wrap browser-use's `Agent`; Skyvern's workflow builder; `workflow-use` | Repackaging. Skyvern and `workflow-use` are also AGPL-3.0 |

## 3. Concepts

All four run on the same engine: a typed workflow graph, accessibility-tree observation, post-conditions on each segment, a verifier that never sees the agent's own success claim, an action gate fixed before the run, guarded replay, a live token and time counter, and an evidence bundle.

### Concept 1: Clearance (recommended)

A lawyer drops in a supplier's contract PDF.

1. Extract the parties, subprocessors and key promises.
2. Resolve the company on Companies House: officers, owners, charges, and filings read from PDFs (API plus downloads).
3. Check the UK Sanctions List (XML), then the ICO and FCA registers (browser).
4. Read the supplier's terms, privacy and subprocessor pages (browser, unpredictable layouts).
5. **Repeat steps 2 to 4 for every subprocessor.** The first pass is reasoned; later ones replay with guards, so the counter visibly drops.
6. Reconcile against the contract, for example a named entity that doesn't match, a lapsed ICO registration, or a subprocessor missing from the schedule.
7. Write a redline, wait for human approval, and submit to a clearly labelled mock procurement portal.
8. Verify the portal's event log and produce a bundle where every finding carries its URL, time, hash and a "could not verify" list.

**Seeded test:** a labelled mock supplier page carries injected text, and the gate visibly rejects the action it asks for.

**Why it could win:** many sites, many document types, real recovery, an end state rather than a report, and repetition that makes the tie-breakers measurable. Read-only due diligence products already exist (Scout, Glasshouse, Fasrad), so the new part is reconciling against the contract and acting on the result, not the lookups.

### Concept 2: File and Prove

Take a director's departure across a 30-company group: draft each TM01, file through a mock of WebFiling with a human handoff for credentials, and verify each result. It's the most original idea and the clearest gap beside Wordsmith's drafting Blueprints.

**The catch:** we have no company we can legitimately file for, and filing false information with Companies House is an offence. (That's general knowledge rather than a wave finding, so don't treat it as legal advice.) It would run almost entirely on our own mock, so the public-register proof that makes it compelling disappears, unless Wordsmith can suggest a route.

### Concept 3: Watchtower

Turn contract promises into recurring checks against the public source that would reveal a breach, such as subprocessor changes, terms changes, insolvency notices or a lapsed registration. The nightly run replays at almost no token cost. When a guard detects a change, the model wakes up, compares it to the clause, and drafts the notice for approval.

**Strongest on tokens and time**, because repetition is built in, and the demo moment is clear. It's less obviously "end to end" in a single sitting, and a live change must be seeded on a labelled mock page. It works well as a second act to Clearance.

### Concept 4: Hostile-site gauntlet (rejected as a product)

A tour of the page types agents fail on: PDFs, iframes, closed shadow roots, 2FA. It's reliable to demo but has no real task behind it, and the brief wants a complex task rather than complex internals. Keep the mock pages as test fixtures.

### Scores (1 to 5, higher is better)

| Concept | Task complexity | Demo reliability | Tokens and time | Legal | Buildable by 09:00 | Original | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1. Clearance | 5 | 4 | 4 | 5 | 3 | 3 | **24** |
| 3. Watchtower | 4 | 4 | 5 | 4 | 3 | 4 | **24** |
| 2. File and Prove | 3 | 4 | 4 | 5 | 3 | 5 | **24** |
| 4. Gauntlet | 3 | 5 | 3 | 1 | 3 | 3 | **18** |

The totals tie, so weighting decides. Complexity is the sponsor's main criterion and Clearance leads on it, which is why it's first. Watchtower can be added on top as a stretch goal.

## 4. Next steps

### Test before building (about 30 minutes, on venue Wi-Fi)

Plain HTTP requests only show that the ICO and FCA search pages respond. None of this has been tried in a real browser.

- [ ] Drive the ICO and FCA register searches with `agent-browser`, headed. The FCA register may be heavy on JavaScript.
- [ ] Get a free Companies House API key and confirm that filing PDFs download.
- [ ] Pick 5 to 10 real supplier sites, then check robots.txt and how their pages behave.
- [ ] Measure tokens per step on real pages, because no controller publishes a reliable figure.
- [ ] Time the same check on a second company to test replay. **Within-job replay is our own extrapolation:** the evidence covers repeating a task, not similar steps inside one job.

### Questions for Wordsmith's engineers

1. Do you already have a browser agent, in beta or planned? Their agents page doesn't mention one, but one page doesn't settle it.
2. Which of Clearance, File and Prove and Watchtower would your customers actually pay for?
3. Which websites do customers still re-key work into by hand? This could replace our mock portal with something more real.
4. How do you measure complexity: number of systems, number of steps, or difficulty of the task?
5. Do tokens, model and time count throughout, or only to break ties? (The deck says "also considered"; the talk said tie-breaker.) Does a cheap model score better than a strong one?
6. Are labelled mock sites acceptable for the final write step, if the reads are live?

### Limits to respect

- **Don't use:** BAILII (proof-of-work wall against AI scrapers) or the IPO trade mark search (Cloudflare challenge). Treat a challenge as a stop or a human handoff, and never try to evade it. Land Registry is paid, so it's out too.
- **Use APIs where they exist:** Companies House, Find Case Law, legislation.gov.uk and the UK Sanctions List. Find Case Law's robots.txt names AI crawlers as disallowed, so use its documented API if we use it at all.
- **Privacy:** officer and sanctions data is personal data. Focus on companies, keep only what the output needs, and word "not found" as "not found in this search on this date".
- **Demo:** run headed, label every mock, pre-authenticate anything that needs a login, cap handoffs at about 60 seconds, and keep a recorded run ready. Rerunning the same task can change 12 to 14% of outcomes, so a clean rehearsal isn't a guarantee.
- **Team rules:** the evidence panel supports the workflow and must not become the product (no dashboards). Log AI tool use for the write-up.

## 5. Verification

The reports came back in about 4 to 15 minutes against a 30-minute budget. Treat them as leads, apart from what's confirmed below.

**Independently confirmed (7 Nov):**

- Licences and activity from the GitHub API: `agent-browser`, Playwright, browser-use, Stagehand, chrome-devtools-mcp, Skyvern, nodriver, Lightpanda.
- 12 preprints exist with matching titles, and the abstracts support the specific claims used here where the excerpt covered them: 16-step collapse, all 73 attacks, PreAct's 8.5 to 13 times, and the 43.4-point self-report gain.
- ComponentBench exists, but its 83.1% vs 48.9% figures weren't visible in the excerpt checked.
- Odysseys2's 47 of 100, and OSWorld 2.0's 108 workflows at a median of 1.6 human hours.
- Genspark's 9 of 11 fields, and its "only work in the current tab" quote.
- `agent-browser`'s fail-loud clicks, and browser-use replay raising `RuntimeError`.
- BAILII's bot-check page and the IPO's 403 response.

**Corrections to the reports:**

| Report | Claim | Correction |
|---|---|---|
| ws-legal | Wordsmith "does not act on the outside world" | Overstated. Its agents page has scenarios such as "returned to procurement portal" and "delivered to HR portal". No browser agent is mentioned, but this is an open question, not a fact |
| ws-legal | File and Prove as the demo spine | Doesn't address the lack of a company we can legitimately file for |
| ws-frontier | "$15 to under $0.10 per workflow" | The baseline in the abstract is a 5-step workflow run 500 times. It's a repeat-run saving, not a single-run one |
| ws-feasibility | Replay exists as Workflow Use | True, but it didn't flag that `workflow-use` is AGPL-3.0 |
| ws-feasibility | "Cloudflare's new headless" | Mislabelled. New headless is Chromium's, not Cloudflare's |
| ws-controllers | AGPL obligates us to publish on any network use | Too strong: the obligation centres on modified versions served over a network. Avoiding these projects is still the simple choice |
| ws-controllers | Written "~13:40" | The file was written about 13:23. Harmless, but it shows self-reported details can't be trusted |

**Not independently checked:**

- Atlas's retirement. OpenAI's help page returned 403 to my check, and the secondary check failed, so it rests on the agent's report. Mariner's date is secondary by the report's own account.
- OSWorld 2.0's completion and token figures, and the per-task dollar costs.
- Polar's and Manus's claims, which are vendor claims.
- Legora, Spellbook and Luminance's current products, per ws-legal.
- The legal commentary in ws-feasibility, which is not legal advice.
