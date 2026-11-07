# Open-source projects for a Wordsmith browser agent

Stars from `gh repo view` on 7 Nov 2026 (shown as "~N (7 Nov 2026)"). Licences from the GitHub licence API, so they are the SPDX ID GitHub detects in the repo's LICENSE file. "Last push" is the `pushedAt` timestamp.

**Licence rules we apply** (from `SlideSummaryFromTranscription.MD`, section 2 and the shared brief):
- **Permissive** (MIT, Apache-2.0, BSD): we can reuse code with attribution.
- **Copyleft** (AGPL-3.0, GPL, MPL): caution. Prefer ideas, or run the software as a separate service and do not copy code into our repo. AGPL is a network copyleft licence, so a hosted demo that users reach over a network can trigger source-release duties. Do not copy AGPL code.
- **No licence:** ideas only.

## 1. Summary table

| Name | URL | Stars (7 Nov 2026) | Licence | Last push | One-line description |
|---|---|---|---|---|---|
| browser-use | https://github.com/browser-use/browser-use | ~120,243 | MIT | 7 Nov 2026 | Python library for AI browser agents, plus a hosted Cloud with stealth browsers |
| Stagehand | https://github.com/browserbase/stagehand | ~25,978 | MIT | 7 Nov 2026 | TypeScript SDK that adds AI actions on top of Playwright, with action caching |
| Skyvern | https://github.com/Skyvern-AI/skyvern | ~23,358 | AGPL-3.0 | 7 Nov 2026 | Browser-workflow agent that reads the page visually and via DOM, with a visual workflow builder |
| Playwright MCP | https://github.com/microsoft/playwright-mcp | ~39,293 | Apache-2.0 | 6 Nov 2026 | MCP server that gives an LLM browser control through accessibility snapshots |
| Nanobrowser | https://github.com/nanobrowser/nanobrowser | ~14,256 | Apache-2.0 | 24 Oct 2026 | Chrome extension agent with a side panel that runs in your real, logged-in browser |
| Steel Browser | https://github.com/steel-dev/steel-browser | ~7,934 | Apache-2.0 | 4 Nov 2026 | Open-source, self-hostable browser API for agents |
| Magentic-UI | https://github.com/microsoft/magentic-ui | ~10,109 | MIT | 23 Sep 2026 | Microsoft's human-in-the-loop agent UI (browser and file system) |
| workflow-use | https://github.com/browser-use/workflow-use | ~4,247 | AGPL-3.0 | 6 Nov 2026 | Record a browser task once, then replay it as a workflow ("RPA 2.0") |
| LaVague | https://github.com/lavague-ai/LaVague | ~6,397 | Apache-2.0 | 21 Jan 2025 (stale) | Large Action Model framework for web agents |
| OSWorld | https://github.com/xlang-ai/OSWorld | ~3,256 | Apache-2.0 | 2 Nov 2026 | Benchmark for computer-use agents in real OS environments |
| WebArena | https://github.com/web-arena-x/webarena | ~1,643 | Apache-2.0 | 26 Nov 2025 | Realistic, self-hostable web environment and benchmark |
| VisualWebArena | https://github.com/web-arena-x/visualwebarena | ~490 | MIT | 9 Nov 2024 (stale) | Multimodal (screenshot) version of WebArena |
| Mind2Web | https://github.com/OSU-NLP-Group/Mind2Web | ~1,037 | MIT | 5 Nov 2025 | Generalist web-agent dataset and benchmark (NeurIPS'23) |
| Stagehand Python | https://github.com/browserbase/stagehand-python | ~516 | MIT | 23 Oct 2026 | **No longer maintained**; moved to the main Stagehand repo |
| Find Case Law docs | https://github.com/nationalarchives/ds-find-caselaw-docs | ~15 | MIT | 7 Nov 2026 | National Archives' docs for the Find Case Law service and API |

Not found or not checked: `browserbase/steel-browser` (returned "not found"; the correct repo is `steel-dev/steel-browser`). `MorviusLab/WebVoyager` (not found under that name; WebVoyager was in search results only, not checked on GitHub).

**Stale or dead:** LaVague (last push Jan 2025), VisualWebArena (Nov 2024), Stagehand Python (moved). Do not build on these without checking for a successor.

## 2. Groups

### 2a. Agent frameworks (what we would build on)

#### browser-use (MIT, ~120,243, 7 Nov 2026)
- **Architecture (from README and secondary sources):** a Python library. An LLM is given a list of interactive page elements with numeric indices, and returns actions such as "click index 5". Runs locally with any LLM or on Browser Use Cloud (stealth browsers "from $0.02/hour" per README).
- **README claim:** "top score (90.5%) on Stealth Bench V2". This is their own benchmark. **(unverified, vendor claim)**
- **Reuse:** code, under MIT with attribution. Fits the baseline directly.
- **Borrow:** the indexed-element approach to keep tokens small.
- **Gotchas:**
  - Element indices are valid only for the DOM snapshot they came from. They go stale after any page change. Re-extract after every navigation. (secondary source on the Rust port's docs, which describes the same idea)
  - Cloud pricing is a vendor price. Recheck before quoting in a pitch.
  - Human takeover is documented in their cloud docs: a live view URL lets a person complete a login or CAPTCHA, then the agent resumes in the same session. Useful for the "human takeover" requirement. [docs.cloud.browser-use.com](https://docs.cloud.browser-use.com/tips/live-view/human-takeover)
  - Not a legal project. We would add the legal layer ourselves.

#### Stagehand (MIT, ~25,978, 7 Nov 2026)
- **Architecture:** TypeScript SDK. Three calls: `act` (do one thing in natural language), `extract` (pull structured data), `observe` (list candidate actions). Built on Playwright. Browserbase is the optional hosted browser.
- **Caching:** v3 docs describe a local `cacheDir`; the first run calls the LLM, later runs replay the cached action with no LLM call. The v4 docs describe a server-side cache keyed on URL and accessibility tree, and say that small runtime differences change the key. Caching is best-effort. [act reference](https://docs.stagehand.dev/v3/references/act.md), [v4 caching](https://docs.stagehand.dev/v4/best-practices/caching)
- **Reuse:** code, MIT.
- **Borrow:** action caching as the main token-saving idea for the tie-breaker.
- **Gotchas:**
  - Two caching models exist (v3 local, v4 server). Check which one the installed version uses.
  - Caching depends on the accessibility tree, so pin the viewport before the first action (the docs recommend this).
  - Python SDK is dead. Use the TypeScript repo.

#### Skyvern (**AGPL-3.0**, ~23,358, 7 Nov 2026)
- **Architecture:** captures the page, reduces the DOM to interactive elements, and sends both a screenshot and element data to an LLM at each AI step. Can run self-hosted or in their cloud. Has a visual, no-code workflow builder. Search summaries say it "parses pixels" rather than structure; treat as secondary.
- **Benchmarks:** search results quote WebVoyager figures of 85.85% for Skyvern. Vendor claim, conflicting across sources. **(unverified)**
- **Reuse:** **do not copy code** (AGPL). Running it as a separate self-hosted service for our demo is a different question, but still check the terms before a public hosted demo.
- **Borrow:** the visual workflow builder idea, and the "pixels plus DOM" split.
- **Gotchas:** AGPL. Any judge who checks the licence will see it.

#### Playwright MCP (Apache-2.0, ~39,293, 6 Nov 2026)
- **Architecture:** a Model Context Protocol server that exposes browser actions as tools. It returns an accessibility snapshot of the page after each action. Works with any MCP-capable client.
- **Token behaviour:** snapshot costs are much lower than screenshots (search estimates 200–5,000 tokens per snapshot against 10,000–50,000 for a screenshot). These are rough secondary estimates. **(unverified)** Playwright's docs describe a `snapshot-mode` option and a `target` parameter to limit snapshot size. [playwright.dev/mcp/snapshots](https://playwright.dev/mcp/snapshots)
- **Reuse:** code, Apache-2.0. Easy to wire into a Claude or other MCP client.
- **Borrow:** accessibility snapshots as the default observation.
- **Gotchas:**
  - Snapshots can include elements hidden by modals or off-screen. The agent may try to click them. Check visibility.
  - Each action re-sends the page state, so cost grows across a session. Measure tokens per step.

#### Nanobrowser (Apache-2.0, ~14,256, 24 Oct 2026)
- **Architecture:** Chrome extension. A side panel chat takes a task. It works in your own logged-in browser. Modes: "Ask" or "Auto", per-site rules, several tasks at once in separate tab groups, export results as CSV or Markdown, voice input, long-task summarising. Asks before it submits or sends. [README](https://github.com/nanobrowser/nanobrowser)
- **Agent roles:** search results name the agents Planner, Navigator, Validator, and in another source Planner, Browser, Observer. Naming is inconsistent, so read the code. **(unverified)**
- **Reuse:** code, Apache-2.0.
- **Borrow:** side-panel layout, Ask/Auto mode, per-site permission rules, and the approval-before-submit behaviour. This is the closest open-source model to the UI we want (see `04-ui-design.md`).
- **Gotchas:**
  - Runs in the user's real browser with real sessions. A judge may worry about privacy, so have a clear answer.
  - Last push is October 2026, so active.

#### Steel Browser (Apache-2.0, ~7,934, 4 Nov 2026)
- **Architecture:** open-source browser API for agents. Self-hostable, with a managed cloud option. A session can be started through an API and controlled by Playwright or a similar tool.
- **Funding and company:** search results conflict on the Series A ($16M vs $17M) and say it is a competitor to Browserbase. Not needed for our decision.
- **Reuse:** code, Apache-2.0.
- **Borrow:** self-hosted browser sessions. Good if we want to keep data on our own machines for a privacy answer.
- **Gotchas:** a second browser layer adds one more thing to debug in 24 hours.

#### Magentic-UI (MIT, ~10,109, last push 23 Sep 2026)
- **Architecture:** Microsoft's research UI for agents that work across a browser and the local file system. Search summary calls the current version "MagenticLite", an experimental agent. **(unverified details)**
- **Reuse:** code, MIT.
- **Borrow:** likely the most relevant open UI for **human approval and co-planning**, based on its name and purpose. **(unverified: we did not read its README or screens this session.)** Check its approval and plan-editing screens before designing ours.
- **Gotchas:** research code. Expect rough edges.

#### workflow-use (**AGPL-3.0**, ~4,247, 6 Nov 2026)
- **Architecture:** record a human run of a web task, then turn it into a workflow that replays with an agent to fill in variables. Marketed as "RPA 2.0". [repo](https://github.com/browser-use/workflow-use)
- **Reuse:** **do not copy code** (AGPL). Ideas only.
- **Borrow:** the record-once-then-replay pattern. This is the same idea as Stagehand caching, at the workflow level, and it directly serves the tie-breaker (most steps run without an LLM after the first run).
- **Gotchas:** AGPL. Replays break when sites change.

#### LaVague (Apache-2.0, ~6,397, last push 21 Jan 2025 — stale)
- Large-action-model framework for web agents. Older design (2024 era). **Ideas only**, since the project has no 2025–2026 activity.

### 2b. Benchmarks and datasets (for measuring our agent)

These are what the judges' "efficiency" and "completeness" claims would be measured against. We do not need to run them in 24 hours. We should know their names.

#### WebArena (Apache-2.0, ~1,643, 26 Nov 2025)
- Self-hostable realistic web environment (shopping, forum, code hosting, maps, CMS) and benchmark. Good for a reproducible "does the agent finish" score. Uses a cleaner version called WebArena-Verified in recent work (secondary).
- **Use:** reuse the environment, not the scores.

#### VisualWebArena (MIT, ~490, 9 Nov 2024 — stale)
- Screenshot-based version of WebArena. Vendor consumer products (Anthropic, OpenAI, Google) are reported to use it as a primary number (search summary, **unverified**). Last push Nov 2024, so use with care.

#### OSWorld (Apache-2.0, ~3,256, 2 Nov 2026)
- Real-OS benchmark for computer-use agents. Search results: top runs now at or above the human baseline under standard scoring, but a stricter efficiency metric gives much lower numbers (17.4% vs 42.5% in one secondary re-analysis). **(unverified)** This is the best source for the "efficiency matters" argument. [repo](https://github.com/xlang-ai/OSWorld)

#### Mind2Web (MIT, ~1,037, 5 Nov 2025)
- Dataset of real website tasks used to train and test generalist web agents (NeurIPS'23). Useful for picking realistic tasks.

### 2c. Legal and public-data sources (code and docs)

#### Find Case Law docs (MIT, ~15, 7 Nov 2026)
- National Archives' documentation repo for Find Case Law. Read this before designing anything that touches judgments. Licence: Open Justice Licence v1.0 for the data, which excludes computational analysis. See `05-ideas.md`. [repo](https://github.com/nationalarchives/ds-find-caselaw-docs)

#### Stagehand Python (MIT, ~516, 23 Oct 2026 — no longer maintained)
- Listed for completeness. Do not use. The maintained SDK is the TypeScript repo above.

## 3. Not included, and why

- **Playwright itself** (the browser library under most of these): not checked on GitHub this session. It is the default choice in any case.
- **Browserbase's own repos**: the company's blog and Browserbase Cloud are relevant for hosted browsers. Not checked.
- **Claude quickstarts** (`anthropics/claude-quickstarts`, ~19,138, pushed 6 Nov 2026): a collection of Claude API starter projects. Licence not checked, so treat as unverified. It may contain a computer-use or browser demo worth reading. Check before relying on it.

## 4. Gotchas across the group

- **Licences:** two of the 14 projects in the table are AGPL (Skyvern, workflow-use). The rest are MIT or Apache-2.0. Stay on the permissive ones for any code we copy.
- **Star counts are not quality:** browser-use has about five times the stars of Stagehand. Choose on fit: does the SDK match our language, and does it cache?
- **Hosted products carry vendor claims:** "$0.02/hour", "90.5%", "85.85%" are all vendor figures. Measure ours.
- **Stale projects:** LaVague, VisualWebArena and Stagehand Python are old or moved. Do not depend on them.
- **Benchmarks change:** WebArena and OSWorld have newer verified versions. Quote the version you used.

## 5. Recommended stack (for `05-ideas.md`)

Default for a 24-hour build, from this research:
1. **Agent loop and browser control:** Stagehand (TypeScript, MIT, has action caching) or browser-use (Python, MIT, largest community). Pick by team language. Stagehand fits a Node or TypeScript stack, which suits Aiden. browser-use fits Python.
2. **Observation:** accessibility snapshots (Playwright MCP style) as default. Screenshots only for visual checks.
3. **Replay for efficiency:** cache successful actions (Stagehand cache) and log tokens per step.
4. **UI pattern:** Nanobrowser's side panel, Magentic-UI's approval ideas, Browser Use's human takeover.
5. **Legal data:** APIs first (Companies House, legislation.gov.uk), browser only for pages that have no API. See `05-ideas.md`.
