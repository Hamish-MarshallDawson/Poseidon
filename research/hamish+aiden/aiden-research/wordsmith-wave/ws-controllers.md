# ws-controllers: open-source browser controllers

Track owner: research agent ws-controllers. Written 7 Nov 2026, ~13:40 GMT. All licence claims below are read from the repository's actual LICENSE file via the GitHub licence API (fetched 7 Nov 2026); star counts and last-push dates are from `api.github.com` the same day.

## 1. Bottom line

1. **Almost everything we want to adopt is permissively licensed.** browser-use MIT, Stagehand MIT, Midscene MIT, and Playwright, playwright-mcp, playwright-cli, chrome-devtools-mcp, Vercel agent-browser, Puppeteer, Selenium and Steel all Apache-2.0. The only AGPL-3.0 traps on the list are **Skyvern, Lightpanda and nodriver** — for a network-served hackathon demo, an AGPL dependency is a real exposure, not a theoretical one.
2. **The low-level layer should be a CLI/daemon over CDP with stable element refs, not an MCP server.** Microsoft says this itself: coding agents "increasingly favor CLI-based workflows... because CLI invocations are more token-efficient: they avoid loading large tool schemas and verbose accessibility trees into the model context" (playwright-mcp README). That is the strongest single argument for our stack shape.
3. **Vercel's `agent-browser` is the closest off-the-shelf "adoptable floor"**: Apache-2.0, native Rust CLI, accessibility-tree snapshot with `@e1`-style refs, browser kept alive in a daemon between commands, tabs/frames/upload/download/PDF/trace/headed. It is the piece most likely to save us a day, and it is emphatically *not* the product.
4. **Page representation has converged on the accessibility tree plus stable refs.** Playwright MCP: "structured accessibility snapshots, bypassing the need for screenshots or visually-tuned models". Stagehand: "hybrid accessibility-tree trimming". browser-use: DOM element tree, vision off/auto/on. Skyvern is the vision-first outlier. Nobody in this layer publishes an honest tokens-per-step number — that is a gap we can occupy on stage.
5. **Nothing in this layer does workflow-level planning, verification or domain work.** The one adjacent feature — browser-use's `save_history()` / `load_and_rerun()` — is a code-replay, not a workflow engine, and it "raises `RuntimeError` at the first step it cannot match". That gap is exactly what the brief says must be substantially ours.

## 2. Findings

### 2.1 Licence, language, maintenance (verified from LICENSE files)

| Project | Licence (file) | Lang | Stars | Last push |
|---|---|---|---|---|
| browser-use | MIT | Python (+TS) | 120,244 | 2026-11-07 |
| Stagehand | MIT | TypeScript | 25,978 | 2026-11-07 |
| Playwright | Apache-2.0 | TypeScript | 99,513 | 2026-11-07 |
| playwright-mcp | Apache-2.0 | TypeScript | 39,293 | 2026-11-06 |
| playwright-cli | Apache-2.0 | TypeScript | 15,021 | 2026-11-05 |
| chrome-devtools-mcp | Apache-2.0 | TypeScript | 54,919 | 2026-11-06 |
| agent-browser (Vercel Labs) | Apache-2.0 | Rust | 46,443 | 2026-11-07 |
| Puppeteer | Apache-2.0 | TypeScript | 95,809 | 2026-11-07 |
| Selenium | Apache-2.0 | Java | 34,577 | 2026-11-07 |
| Steel Browser | Apache-2.0 | TypeScript | 7,934 | 2026-11-04 |
| Midscene (ByteDance) | MIT | TypeScript | 15,537 | 2026-11-07 |
| patchright | Apache-2.0 | TypeScript | 5,112 | 2026-11-05 |
| Nanobrowser | Apache-2.0 | TypeScript | 14,256 | 2026-10-24 |
| browser-harness | MIT | Python | 18,920 | 2026-11-07 |
| **Skyvern** | **AGPL-3.0** | Python | 23,358 | 2026-11-07 |
| **Lightpanda** | **AGPL-3.0** | Zig | 41,540 | 2026-11-07 |
| **nodriver** | **AGPL-3.0** (`LICENSE.txt`) | Python | 4,919 | 2026-10-26 |
| LaVague | Apache-2.0 | Python | 6,397 | **2025-01-21** |
| WebDriver BiDi (spec) | W3C doc licence, no SPDX id | Bikeshed | 513 | 2026-11-06 |

Things that changed since our lead list was written: **LaVague is effectively dormant** — last push 21 January 2025, roughly 21 months ago, so it is a 2024-era framework, not a live option. **`agent-browser` did not exist a year ago** (repo created 2026-01-11) and is now the most-starred Rust browser CLI for agents. **`browser-harness`** (MIT, 18.9k stars) and **`playwright-cli`** (Apache-2.0) are new arrivals on our list.

### 2.2 How each one represents a page to the model

- **Playwright MCP / playwright-cli** — ARIA accessibility snapshot rendered as an indented YAML-ish tree, with `ref` tokens the model passes back to `browser_click`. No vision by default; coordinate actions are opt-in via `--caps=vision`. Snapshot verbosity is controllable: `--snapshot-mode full|none` (default `full`), `--depth`, `--snapshot-boxes`, plus a `browser_find` tool that searches the snapshot and returns snippets "which is cheaper than capturing the whole snapshot". `--mobile` is explicitly recommended partly because "mobile pages are usually lighter, which saves tokens."
- **chrome-devtools-mcp** — Puppeteer under the hood, exposes DevTools: text snapshot, network, console with source-mapped stacks, and performance traces. Unique capability: it can record a trace and hand the model *actionable performance insights*, which no other controller here does.
- **agent-browser** — `snapshot -i` returns "compact text with a ref such as `@e1`"; the agent acts on refs, re-snapshots to verify. Daemon over CDP keeps the browser warm. Notably it *fails loudly*: "a click fails, instead of reporting success, when the target is hidden, disabled, outside the viewport, or covered by another element such as a consent banner." That single design choice is the most hackathon-relevant thing in the whole survey — silent false success is what kills agent demos.
- **Stagehand** — `act` / `observe` / `extract` over a browser extension, "hybrid accessibility-tree trimming"; `observe()` returns real selectors so credentials never reach the model. `cache: true` gives server-side caching of `act()`/`observe()`/`extract()` results, but the caching doc is explicit: "Browserbase manages the cache" — it is not a local feature, so a no-account hackathon build gets none of it. Its docs do cover "Using multiple tabs" and cost/speed optimisation as separate patterns rather than built-in orchestration.
- **browser-use** — DOM element tree with indices plus optional screenshots (`use_vision` default `True`, `"auto"` = screenshot tool available but only used when asked; `vision_detail_level` low/high/auto). Ships its own model (BU2) and a hosted agent API.
- **Skyvern** — "Vision LLMs" first, wrapped in a no-code workflow builder of tasks and blocks (HTTP request block, custom code block, file storage). Closest existing thing to "a workflow engine", which is precisely why adopting it would look like repackaging.
- **Steel Browser** — not a page-representation layer at all: a self-hostable browser-as-an-API (sessions, cookies, CDP endpoint, stealth plugins). Docker one-liner; also a cloud.

**Tokens per step:** no primary source publishes a measured figure for any of these. What is documented is mechanism, not cost. Best available anchors are all vendor or qualitative: Microsoft's "verbose accessibility trees" warning, Stagehand's hybrid trimming claim, Browserbase's caching claim, and browser-use's token/cost tracking docs (tooling to measure, not a result). Anyone quoting "N tokens per step" for these tools is repeating a blog post. **(unverified)**

### 2.3 WebDriver BiDi and the standards floor

BiDi is still an **Editor's Draft** at `w3c.github.io/webdriver-bidi/` (checked 7 Nov 2026), six years after the repo was created, with 310 open issues. So: cross-browser "proper" automation protocol is not a foundation to bet a 20-hour build on; CDP via Playwright/Puppeteer-pattern drivers is. Selenium is alive and Apache-2.0 but is the wrong shape for us — its value is grid/fleet testing, not a tight agent loop.

### 2.4 Stealth tools (patchright, nodriver, camoufox, Steel's anti-detection)

patchright is Apache-2.0 (undetected Playwright fork), nodriver is AGPL-3.0 (undetected-chromedriver successor), camoufox is MPL-2.0 (anti-detect Firefox), Steel advertises "stealth plugins and fingerprint management". I have not investigated evasion techniques and recommend we don't: the feasibility track owns bot-blocking, and the defensible hackathon position is *human handoff on a challenge*, not detection evasion. Licence-wise patchright is fine to link to; nodriver's AGPL plus its purpose makes it an **avoid**.

### 2.5 Recommended stack

**Adopt (all Apache-2.0, all low-level):** Chrome for Testing driven over CDP by **agent-browser** as the default tool surface (snapshot → refs → act → re-snapshot, daemon keeps the browser warm, `--session` for parallel tabs, `upload`/`download`/`pdf`/`trace` for the awkward features), with **Playwright** as the deterministic fallback we can write by hand. Add **chrome-devtools-mcp**'s network/console/trace capabilities as our evidence collector for verification. If we ever want an MCP face for a judge, put **playwright-mcp** in front — Apache-2.0, and its snapshot/ref semantics are the de-facto convention.

**Borrow patterns, not code:** Stagehand's `observe()`-then-act split (resolve the selector cheaply, act on it, keep secrets off the wire) and browser-use's `save_history`/`load_and_rerun` (compile a successful run, replay it with new variables).

**Build ourselves:** the planner, the workflow graph with pre/post-conditions, the verification policy, the human-approval gate, the domain logic, and the token/time accounting. That list is what makes the entry ours rather than a wrapper.

**Repackaging (don't):** importing Skyvern and using its workflow/task/block builder as the product; wrapping browser-use's `Agent` plus its shipped system prompt and presenting it as our agent; driving a stock Playwright MCP client and calling its trace "our workflow". Any of these fails the brief's "planning, workflow logic, verification and domain work must be substantially ours" test — and the first one also drags in AGPL.

## 3. Comparison table

| Item | Licence | Role for us | Page repr. | Adopt? |
|---|---|---|---|---|
| agent-browser | Apache-2.0 | Low-level CLI: snapshot/refs/act/verify, tabs, uploads, trace, headed | a11y tree + refs | **Adopt** (as plumbing) |
| Playwright (+ playwright-cli) | Apache-2.0 | Engine + deterministic fallback scripting, record/replay, selector healing | n/a (driver) | **Adopt** |
| playwright-mcp | Apache-2.0 | Reference for snapshot/ref semantics; MCP only if a judge wants it | a11y tree + refs | Adopt ideas, not the server |
| chrome-devtools-mcp | Apache-2.0 | Network/console/trace evidence for verification | snapshot + traces | **Adopt** for verification |
| Stagehand | MIT | `observe()` → selector, `act()` self-heal; caching pattern | hybrid a11y trim | Adopt pattern |
| browser-use | MIT | Reference agent loop; `save_history`/`load_and_rerun` replay idea | DOM tree + vision | Study, don't wrap |
| Midscene | MIT | Alternative vision-first planner, YAML scripts | vision | Optional |
| Steel Browser | Apache-2.0 | Self-hosted browser sessions if we need isolation | n/a | Optional |
| Browserbase | proprietary | Hosted browsers + cloud action cache | n/a | Skip (no accounts) |
| Selenium / BiDi | Apache-2.0 / W3C draft | — | — | Skip |
| Skyvern | **AGPL-3.0** | Whole workflow product | vision | **Avoid** |
| Lightpanda | **AGPL-3.0** | Fast headless engine | n/a | **Avoid** |
| nodriver | **AGPL-3.0** | Stealth | n/a | **Avoid** |
| LaVague | Apache-2.0 | — | DOM | **Avoid** (dead since Jan 2025) |

## 4. Risks and unknowns

- **AGPL is the main legal risk.** Skyvern is the single best fit for "complex end-to-end workflow" and the single worst licence for a demo served to judges over HTTP. Using it as an imported library inside a network service would, on a strict reading, oblige us to publish our source. Avoid, or use only its ideas.
- **"Adopt vs repackage" boundary.** Adopting agent-browser/Playwright/CDP as the transport is explicitly allowed by the brief. Wiring Skyvern's workflow builder or browser-use's `Agent` + its system prompt into a UI and calling it ours is repackaging. The line I'd draw: *the loop that decides what to do next, and the check that decides whether it worked, must be our code.*
- **No trustworthy tokens-per-step numbers exist** for any controller here; all figures available are vendor claims. If we want a token story we must measure it ourselves.
- **chrome-devtools-mcp collects usage statistics by default** and may send trace URLs to Google's CrUX API; disable with `--no-usage-statistics` / `--no-performance-crux` before a demo. Anything we show on a projector should be checked for telemetry.
- **Snapshot staleness is universal.** Refs are only valid for the snapshot they came from; after any DOM change every one of these tools needs a fresh snapshot. agent-browser documents it, playwright-mcp's refs behave the same. This is the root cause of most agent failures and the reason verification has to be its own explicit step.
- Stagehand's `cache: true` **is** Browserbase-managed (confirmed in its caching doc), so the zero-token claim is unavailable to us without an account.
- Unverified: whether agent-browser's Lightpanda/Obscura engine flags work in practice on a Chrome-only demo machine; how much a chrome-devtools-mcp trace costs in time on a live machine; and the real-world reliability of `observe()`-returned selectors after a redesign (the self-healing claim is vendor-side with no published failure rate).

## 5. Three openings (each buildable in <20h)

**A. A verification layer the controllers don't have.** New: after every action, our own "did that actually happen?" checker — network response, DOM state, console errors, before/after diff — feeding a structured verdict the planner must satisfy before advancing. Nearby: chrome-devtools-mcp exposes network/console/trace; agent-browser's `diff`, `errors`, `vitals` commands exist but are passive. Evidence: agent-browser's README frames false success as the failure to avoid; Microsoft's own docs admit accessibility trees are verbose and lossy. Nobody ships a *policy* for trusting an action.

**B. Compiled, self-healing workflow steps.** New: compile a successful run into a typed, parameterised step graph with explicit pre/post-conditions, so step N+1 re-locates its target semantically after a DOM change, and only escalates to the model when the precondition breaks. Nearby: browser-use `save_history`/`load_and_rerun` (code replay, raises on first mismatch, still calls the model for extraction); Stagehand `act()` self-heal (single action, no graph). Evidence: both are documented, both stop short of a workflow with invariants. This is also the story that gets us "fewer tokens, less time" as a *measured* claim.

**C. Parallel tab execution with a join and a single audit trail.** New: independent sub-goals run concurrently in separate tabs/sessions, each with its own trace, joined into one receipt; a failing branch is retried or handed to a human without killing the run. Nearby: agent-browser has `--session`, `tab`, `batch`; browser-use has multi-browser support; playwright-cli exists. No surveyed open-source project documents concurrent sub-goal execution with per-branch verification and recovery. Evidence: all building blocks are documented and permissively licensed; the orchestration is ours.

## 6. Sources

| URL | What it supported |
|---|---|
| https://github.com/browser-use/browser-use/blob/main/LICENSE | MIT, "Copyright (c) 2024 Gregor Zunic" |
| https://github.com/browser-use/browser-use | 120,244 stars, Python, pushed 2026-11-07; `save_history`/`load_and_rerun` replay and its `RuntimeError` behaviour; Cloud pricing $0.02/browser-hour; BU2 model |
| https://docs.browser-use.com/open-source/customize/agent/all-parameters.md | `use_vision` default True, `vision_detail_level`, DOM/state timeouts |
| https://github.com/browserbase/stagehand/blob/main/LICENSE | MIT, Browserbase Inc. |
| https://github.com/browserbase/stagehand | 25,978 stars; act/observe/extract; hybrid a11y-tree trimming; `cache: true` server-side caching |
| https://docs.stagehand.dev/v4/best-practices/caching | "Browserbase manages the cache" — caching is a hosted-only feature |
| https://docs.stagehand.dev/v4/best-practices/using-multiple-tabs | Stagehand documents multi-tab use as a practice, not orchestration |
| https://github.com/Skyvern-AI/skyvern/blob/main/LICENSE | AGPL-3.0 |
| https://github.com/Skyvern-AI/skyvern | 23,358 stars; vision-first; workflow/task/block model; AGPL note re managed cloud anti-bot |
| https://github.com/microsoft/playwright/blob/main/LICENSE | Apache-2.0 |
| https://github.com/microsoft/playwright-mcp | Apache-2.0; ARIA snapshots; CLI-vs-MCP token argument; `--snapshot-mode`, `--depth`, `browser_find`, `--caps=vision` |
| https://registry.npmjs.org/@playwright/mcp | latest published 0.0.84 on 2026-11-03 |
| https://github.com/microsoft/playwright-cli | Apache-2.0, 15,021 stars, pushed 2026-11-05 |
| https://github.com/ChromeDevTools/chrome-devtools-mcp | Apache-2.0; Puppeteer-based; traces, network, console; usage statistics on by default |
| https://github.com/vercel-labs/agent-browser | Apache-2.0; Rust CLI; `@e1` refs; daemon over CDP; fail-loud clicks; sessions/tabs/uploads/PDF/trace |
| https://github.com/puppeteer/puppeteer/blob/main/LICENSE | Apache-2.0 |
| https://github.com/SeleniumHQ/selenium/blob/trunk/LICENSE | Apache-2.0 |
| https://github.com/steel-dev/steel-browser | Apache-2.0; self-hostable browser API; stealth plugins; Docker |
| https://github.com/Kaliiiiiiiiii-Vinyzu/patchright/blob/main/LICENSE | Apache-2.0 |
| https://github.com/ultrafunkamsterdam/nodriver/blob/main/LICENSE.txt | AGPL-3.0 |
| https://github.com/daijro/camoufox | MPL-2.0 |
| https://github.com/Lightpanda-io/browser | AGPL-3.0, Zig |
| https://github.com/web-infra-dev/midscene | MIT (ByteDance) |
| https://github.com/nanobrowser/nanobrowser | Apache-2.0 |
| https://github.com/browser-use/browser-harness | MIT, 18,920 stars |
| https://github.com/lavague-ai/LaVague | Apache-2.0, last push 2025-01-21 |
| https://w3c.github.io/webdriver-bidi/ | Still an Editor's Draft on 7 Nov 2026 |
