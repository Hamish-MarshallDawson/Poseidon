# br-engineering: agentic programming and engineering

Track report for the browser wave, Saturday 7 November 2026. Web sources only; nothing was run, installed or cloned. Vendor documentation and vendor blogs are labelled. Anything I could not confirm is marked **(unverified)**.

## 1. Bottom line

1. **Every serious coding agent now has a browser, and they all hit the same wall: one process, one browser.** Playwright MCP's own docs say "a profile can only be used by one browser at a time. If it is already locked, the server fails to start" ([playwright.dev](https://playwright.dev/mcp/configuration/user-profile), current). The tracker is full of agents "fighting over the same tab" ([playwright-mcp#893](https://github.com/microsoft/playwright-mcp/issues/893), opened Aug 2025, comments to Mar 2026).
2. **The fix everyone ships is duplication, not sharing.** The community answer is N MCP servers with N `--user-data-dir` paths; the cost is that each starts logged out, so logins are not shared ([#893](https://github.com/microsoft/playwright-mcp/issues/893) comments). One team lost a day to it: four clones, one shared `.playwright-profile`, Chromium's `SingletonLock`, and "Playwright is broken" turned out to be a profile deadlock ([dxdev.com](https://dxdev.com/blog/isolated-flag-parallel-playwright-profile-lock/), 9 May 2026). **A shared browser is the missing primitive, and the pain is already documented by others.**
3. **The interface is moving from MCP tools to CLI + skill, for token reasons.** Google's own docs: registering the MCP server "injects every tool definition and JSON schema into your LLM's system prompt in every conversation", while a CLI skill loads "a compact Markdown summary" ([developer.chrome.com](https://developer.chrome.com/docs/devtools/agents/cli), current). That is a cheap win on the judged token criterion.
4. **Concurrency is being fixed at the wrong layer.** Chrome DevTools MCP addresses pages by id (its eval suite has `page_id_routing_concurrent_form_test` and cross-page state cases), and a Playwright PR makes several clients connect to one shared browser over separate connections ([repo](https://github.com/ChromeDevTools/chrome-devtools-mcp/); [playwright#42622](https://github.com/microsoft/playwright/pull/42622), merge status **unverified**). Missing: leases, identity, stale-view detection and evidence. That gap is buildable in a weekend.
5. **Browser login is the top failure point, and doing it "properly" is unsolved.** Cookie sync and TOTP replay work but are unscoped and invisible to the site, which sees "just you clicking around" ([workos.com](https://workos.com/blog/logging-ai-agents-into-web-apps), undated). In engineering this bites hardest on SSO-protected staging and previews, where several developers' agents need the *same site* as *different people*.

## 2. Findings

### How coding agents use browsers today

| Shape | Examples | What it is |
|---|---|---|
| MCP server driving a real browser | Playwright MCP, Chrome DevTools MCP, BrowserTools MCP | tools injected into context |
| Native in-IDE browser tool | Cursor Agent Browser, Codex in-app browser | first-party panel, token-tuned, tab-isolated |
| CLI driven by the agent | `agent-browser`, `chrome-devtools` CLI | agent writes shell commands or a script |
| Extension controlling *your* logged-in browser | Claude in Chrome, BrowserSkill-style bridges | reuses the human's session |

Sources: [playwright.dev profile/state docs](https://playwright.dev/mcp/configuration/user-profile); [Chrome DevTools for agents](https://developer.chrome.com/docs/devtools/agents) and its [CLI](https://developer.chrome.com/docs/devtools/agents/cli) over one CDP daemon; `agent-browser`, a Rust CLI returning an accessibility tree with `@e1` refs over a Node/Playwright daemon ([GitHub](https://github.com/vercel-labs/agent-browser)); [Cursor's browser docs](https://cursor.com/docs/agent/tools/browser).

Two admissions in Cursor's docs are worth quoting to judges: the agent is prompted to "detect running development servers and use the correct ports instead of starting duplicate servers or guessing port numbers", and browser state reaches the model as images "rather than relying on text descriptions". Those are exactly the jobs a shared browser should take off the IDE.

### Where it hurts

**a) One browser per MCP connection and a hard profile lock.** The profile dir is a hash of the client's workspace, so two *projects* do not collide — two agents in one workspace do. The failure is not catchable: Chromium blocks on the lock, so it shows up as a hang or a generic "the browser wouldn't start" ([dxdev.com](https://dxdev.com/blog/isolated-flag-parallel-playwright-profile-lock/), May 2026). `--isolated` fixes the lock and throws away the login. Maintainers' position: "start multiple mcp servers or use playwright-cli for multiple sessions" ([playwright#40585](https://github.com/microsoft/playwright/issues/40585), May 2026, closed) — isolation left as hand-maintained configuration.

**b) Tab collisions inside one browser.** Sharing a browser means sharing window, focus, downloads and profile. A user reported parallel runs giving "very different results" from serial runs even with `--isolated`, and proposed `tabId` per call ([#893](https://github.com/microsoft/playwright-mcp/issues/893)). The community PR states the trade-off exactly: multi-server isolation is reliable but "each server needs its own `user-data-dir`, so logins aren't shared" ([playwright#39703](https://github.com/microsoft/playwright/pull/39703) — merge status **unverified**). Chrome DevTools MCP instead addresses pages by id.

**c) OS housekeeping leaks between agents.** A published implementation names the three collisions: a stale `SingletonLock` symlink pointing at `hostname-PID`, an orphan Chrome still pinned to a `--user-data-dir`, and two artifact trees racing to write `events.json` into one folder ([assrt.ai](https://assrt.ai/t/playwright-agent-isolation), 28 Apr 2026). Their fixes are lock scrubbing, orphan killing and an `--isolated` fallback: cleanup, not coordination.

**d) Authentication, especially SSO.** Practice today: copy `storage_state`, point at the human's profile, inject from a password manager, replay TOTP, poll an agent-owned inbox ([workos.com](https://workos.com/blog/logging-ai-agents-into-web-apps)). All work; none is scoped, attributable or revocable, and sessions expire with no re-auth path. The engineering case is a real identity against SSO'd staging, several identities at once, one site.

**e) Token and schema overhead.** Google: MCP schemas cost every conversation; the CLI skill costs only when used, and its "limited, highly targeted" surface is "significantly easier for even low-tier models to generate reliably without hallucinations" ([docs](https://developer.chrome.com/docs/devtools/agents/cli)). `agent-browser` sells the same idea: "compact text output minimizes context usage" ([agent-browser.dev](https://agent-browser.dev/), vendor).

**f) Security of "control my real browser".** Reported zero-click prompt-injection chains in Anthropic's Claude Chrome extension ("ClaudeBleed", disclosed Dec 2025 per reporting; "ShadowPrompt"), patched by the vendor, with ~3 million users cited ([securityweek.com](https://www.securityweek.com/vulnerability-in-claude-extension-for-chrome-exposes-ai-agent-to-takeover/), [purpleshieldsecurity.com](https://www.purpleshieldsecurity.com/post/claude-chrome-extension-vulnerability-zero-click), Mar 2026). Patch claims are vendor claims. An agent driving the developer's own logged-in browser is the riskiest shape, and a shared browser concentrates that risk.

### Several developers, several agents, one staging site

The browser side is well documented; the data side is not. Documented: profile locks, tab collisions, port guessing (Cursor), orphan processes, artifact races (assrt). I found **no primary source** for a tool that leases staging test data to an agent, or that tells an agent its view is stale because another agent just changed the record — so treat this as a gap in the literature, not proof that nobody does it **(unverified)**.

## 3. Workflow table

| # | Who | Trying to | APIs/MCP fail because | Browser adds | Multi-agent/people failure | Evidence |
|---|---|---|---|---|---|---|
| 1 | Dev + their agent | Verify its own UI fix renders | No API for "does it look right"; DOM asserts miss the visual outcome | Rendered page, screenshot, console, network | Two agents in one workspace share profile and tab; parallel ≠ serial | [#893](https://github.com/microsoft/playwright-mcp/issues/893), [Cursor](https://cursor.com/docs/agent/tools/browser) |
| 2 | Agent reproducing a user bug | Replay the click path on staging, capture the error | Logs have the error, not the path or DOM state at failure | Real reproduction, HAR + console + screenshot | Wrong dev-server port; another agent's stale cookie flips the result | [Cursor](https://cursor.com/docs/agent/tools/browser), [dxdev](https://dxdev.com/blog/isolated-flag-parallel-playwright-profile-lock/) |
| 3 | Agent setting up an integration | Create OAuth app, add redirect URI, copy the secret into env | Vendor consoles are UI-first; APIs admin-only or partial; secret shown once | The only path for many vendors; one-time secret on screen | Two agents editing one OAuth app; secret caught in a screenshot; seat limits | [workos](https://workos.com/blog/logging-ai-agents-into-web-apps) |
| 4 | Two devs' agents checking previews | Confirm each PR's preview renders | Previews behind SSO; no per-agent identity | Real authenticated session on the real deploy | Same profile lock; whose SSO session; cookies expiring mid-run | [playwright.dev](https://playwright.dev/mcp/configuration/user-profile), [workos](https://workos.com/blog/logging-ai-agents-into-web-apps) |
| 5 | Agent reading cloud dashboards | Build logs, deploy status, quota, trace viewer | Dashboards show more than their API (build logs, traces, live metrics) | Reads the console a human would | Two agents on one seat; one changes a setting the other needs | [Chrome DevTools MCP](https://developer.chrome.com/docs/devtools/agents) |
| 6 | Reviewer + their agent | See visual proof without checking out the branch | Diffs are code, not result; CI screenshots brittle or absent | Before/after images attached to the PR, reproducible | Screenshots of the wrong build; two agents overwrite one artifact dir | [assrt.ai](https://assrt.ai/t/playwright-agent-isolation), [pr-visual-review](https://github.com/vexus2/pr-visual-review) |
| 7 | Agent doing perf/a11y work | Lighthouse + trace on the real page, then fix | No API for rendered performance; CI Lighthouse is slow and separate | DevTools trace and audit on the live page | `events.json` races; trace throttling on a shared machine | [chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp/), [assrt.ai](https://assrt.ai/t/playwright-agent-isolation) |

## 4. Removal test

| # | What breaks without the browser | Verdict |
|---|---|---|
| 1 | Everything. Without rendering, "fixed" is a guess | **Real. Lead with it.** |
| 2 | Reproduction degrades to one log line; the click path is lost | **Real** |
| 3 | Fine where the vendor has an API; stops for most vendors | Moderate |
| 4 | Preview checks die; the agent can only curl HTML | **Real** — the SSO wall is the point |
| 5 | API covers part; build logs and traces are usually UI-only | Moderate |
| 6 | Reviewer is back to "trust me" | Real, but the browser is half: the verifier is the valuable half |
| 7 | Lighthouse has a CLI; trace viewer and console do not | Weak alone. Don't lead with it |

So: **the browser is necessary but not sufficient.** The value in engineering work is browser *plus* an independent check that it did what the agent says.

## 5. Shared browser requirements (this track)

1. **Session = identity + profile, not a process.** Binds (developer, origin, credential scope); leased to one agent at a time; two session ids never share a profile dir. Kills the `SingletonLock` class outright.
2. **Tab leases with owner and expiry**, lost loudly. The `tabId` idea ([#893](https://github.com/microsoft/playwright-mcp/issues/893)), brokered centrally instead of configured per server.
3. **Stale-view detection.** Every read returns a page version; another holder's write or navigation invalidates it. Compare-and-set, not last-write-wins.
4. **Per-agent credentials, never the developer's raw profile**, so actions attribute to the agent and not silently to the human ([workos](https://workos.com/blog/logging-ai-agents-into-web-apps)).
5. **Human takeover as a first-class operation.** Developer takes the leased tab, does SSO/2FA/consent, hands it back, agent continues in the same session — the only honest non-replay answer to SSO.
6. **Dev-server and preview registry**: one source of truth for "this project's port" and "this PR's preview URL" ([Cursor](https://cursor.com/docs/agent/tools/browser)).
7. **Content-addressed evidence store**: screenshot, console tail, HAR and page version per step, hashed, per run. Fixes the `events.json` race and turns claims into proof.
8. **Two faces: MCP for exploration, CLI/skill for replay.** Pay schema cost only when exploring; replay with no model in the loop ([Chrome CLI docs](https://developer.chrome.com/docs/devtools/agents/cli)).
9. **Per-site quotas and back-pressure.** One seat, one origin, many agents: the broker serialises and reports, not the website.

## 6. One end-to-end workflow: "Fix, prove, review"

Three agents, two developers, one shared browser. A bug arrives: "checkout total is wrong when a discount code is applied twice."

1. **Triage agent (CI).** Leases a staging tab, replays the reported path, captures console error and the failing request, writes an evidence bundle, releases.
2. **Reproduction agent (dev A).** New lease, **new session**, fresh seeded account. Confirms the bug. Different session means it cannot inherit the triage agent's stale cart, and its page version proves that.
3. **Fix agent (dev A).** Edits code, runs unit tests, re-leases the staging tab, repeats the click path. The **verifier** decides success, not the agent: it re-reads the total element and compares against an expected value fixed *before* the run, then hashes screenshot, console and HAR.
4. **Collision demo.** Dev B's agent, in a parallel worktree, leases a different tab on the same staging site under B's identity. Both run concurrently: no deadlock, no crossed sessions. This is the demo moment.
5. **Human takeover.** The fix agent hits the SSO-protected preview; the broker pauses the lease and prompts; dev A completes SSO in that tab; the agent resumes with the same session.
6. **Review agent (dev B).** Reads the evidence bundle, re-runs only the replay script against the preview — no model call — and attaches before/after screenshots to the PR.
7. **Human approves, merges.** End state: merged PR, one evidence bundle with per-step page versions, one replayable script, one audit log showing which agent acted as which developer.

**How a judge confirms it:** two tabs of the same staging site driven simultaneously under two identities with no profile error; the evidence bundle shows the pre-registered expected value beside the observed one; deliberately break the total and watch the *verifier* fail the run while the agent still reports success; re-run the replay script with the model disabled and watch it pass far faster. Nothing there relies on a model's self-report — which is the thesis.

## 7. Risks and unknowns

- **Vendor claims about tokens.** The Chrome CLI context-saving argument and `agent-browser`'s compactness are vendor statements, not measurements. Count our own.
- **Merge status.** `page_id` routing is confirmed by eval-scenario names; the Playwright `tabId` PR ([#39703](https://github.com/microsoft/playwright/pull/39703)) is **unverified**.
- **Cursor may already cover the single-workstation case.** Per-workspace cookie isolation and unique tab ids are documented; cross-developer sharing is not, so "the gap is real" rests partly on absence of documentation **(partly unverified)**.
- **Staging data leasing: no evidence found.** Only browser-level collisions turned up. Don't claim prior art either way.
- **Security and terms.** A shared browser holding several developers' sessions is a high-value target, and the extension reports show the surface is live. Automating SSO-protected staging or vendor consoles may breach site terms: demo on our own staging app plus one labelled mock console.
- **Telemetry.** Chrome DevTools MCP collects usage statistics **by default** and sends trace URLs to Google's CrUX unless flagged off ([README](https://github.com/ChromeDevTools/chrome-devtools-mcp/)). Check before pointing any tool at a real account.

## 8. Three openings

**A. The lease broker (strongest).** *New:* leases on tabs and sessions with identity binding, page versions and loud loss, as one small MCP + CLI service any agent can use. *Nearby:* Playwright's multi-server workaround, the `tabId` PR, Chrome DevTools `page_id` routing, assrt's lock scrubbing. All isolate; none brokers, and none handles shared login plus stale views. *Evidence:* [#893](https://github.com/microsoft/playwright-mcp/issues/893), [dxdev post-mortem](https://dxdev.com/blog/isolated-flag-parallel-playwright-profile-lock/), [profile docs](https://playwright.dev/mcp/configuration/user-profile).

**B. Independent verifier for browser claims.** *New:* a checker that never sees the agent's success message; expected values fixed before the run, rendered state re-read, hashed evidence bundle, fail-loud gate. *Nearby:* `pr-screenshots` and `pr-visual-review` capture images; UI Verify asserts visually. None is framed as distrusting the agent; none pairs a pre-registered expectation with a gate. *Evidence:* [pr-visual-review](https://github.com/vexus2/pr-visual-review), [uiverify](https://uiverify.ai/docs/quickstart-screenshot), plus the first wave's finding that agents misreport success.

**C. Acting-as registry with human takeover.** *New:* every session carries (agent, developer, origin, scope), with pause/resume so a human completes SSO in the same tab, and an audit line separating the agent's clicks from the human's. *Nearby:* cookie sync, storage state, vault injection, TOTP replay ([workos](https://workos.com/blog/logging-ai-agents-into-web-apps)) — all impersonate the human rather than representing the agent. *Evidence:* same WorkOS piece; Cursor's token-per-session, tab-ID model is the closest first-party precedent.

## 9. Sources

- https://playwright.dev/mcp/configuration/user-profile — profile modes; one browser per profile, lock ⇒ server fails to start; `--isolated` vs `--user-data-dir`; storage-state.
- https://github.com/microsoft/playwright-mcp/issues/893 — parallel Claude Code agents interfering, Aug 2025 → Mar 2026; tab fights; multi-server workaround; `tabId` proposal.
- https://github.com/microsoft/playwright/pull/39703 — `tabId` isolation and trade-offs (merge status unverified).
- https://github.com/microsoft/playwright/issues/40585 — `sessionId` proposal, May 2026; maintainer reply: multiple servers or playwright-cli.
- https://github.com/microsoft/playwright/pull/42622 — several MCP/CLI clients on one shared browser.
- https://dxdev.com/blog/isolated-flag-parallel-playwright-profile-lock/ — 9 May 2026; `SingletonLock` deadlock across four clones; `--isolated` fix and its cost.
- https://assrt.ai/t/playwright-agent-isolation — 28 Apr 2026; stale lock symlink, orphan Chrome, racing `events.json` (page discloses AI authorship).
- https://github.com/ChromeDevTools/chrome-devtools-mcp/ — MCP + CLI over one CDP daemon; `page_id` routing; default usage statistics; CrUX trace URLs.
- https://developer.chrome.com/docs/devtools/agents and .../agents/cli — tool shape; MCP schema vs CLI skill context cost; CLI caveats.
- https://cursor.com/docs/agent/tools/browser — logs to files the agent greps; per-workspace cookie isolation; tab IDs; dev-server detection; approval modes.
- https://cursor.com/blog/2-0 — parallel agents via worktrees and remote machines (vendor).
- https://github.com/vercel-labs/agent-browser and https://agent-browser.dev/ — accessibility-tree snapshots with refs (vendor).
- https://workos.com/blog/logging-ai-agents-into-web-apps — cookie sync, vault injection, TOTP replay, agent inboxes; why none scopes, attributes or revokes (undated).
- https://www.securityweek.com/vulnerability-in-claude-extension-for-chrome-exposes-ai-agent-to-takeover/ ; https://www.purpleshieldsecurity.com/post/claude-chrome-extension-vulnerability-zero-click — extension injection reports; vendor patched (vendor claim).
- https://github.com/vexus2/pr-visual-review ; https://github.com/nullswan/pr-screenshots ; https://uiverify.ai/docs/quickstart-screenshot — before/after screenshot tooling for PRs.
- https://browser-use.com/posts/best-browser-infrastructure-for-ai-agents ; https://llms.steel.dev/articles/browser-infrastructure-for-ai-agents-compared/ — vendor comparisons; used only to confirm Browserbase/Steel/Kernel exist, not their numbers.
