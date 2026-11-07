# br-multiagent: many agents, one browser

Research agent br-multiagent, Saturday 7 November 2026. Track: what breaks when many agents share browsers, logins and sites, and what a shared browser must do about it. Everything was searched today rather than recalled; vendor claims are labelled.

## 1. Bottom line

1. **Sharing a browser is currently solved by refusing to share it.** Every product hands each session a private browser — Kernel a VM per session, Cloudflare Browser Run concurrency caps, Browserbase a Context it tells you not to use concurrently. The only real shared browser in the wild is a human's Chrome with an agent bolted on (Claude in Chrome), and it breaks when the human touches a tab.
2. **The failures are specific and reproducible.** One shared Chrome profile hits Chrome's profile lock; one shared daemon means one active-page pointer, so agent B's navigate replaces agent A's page and A reads B's console. `agent-browser` reproduced it with before/after output (#326) and fixed the hijacking in v0.34.0, leaving four related issues open. MCP is single-client too (#1215, #2297, no session id reaching servers).
3. **Vendor docs admit the real obstacle.** Browserbase: "Avoid simultaneous logins … Sites may force a log out." Businesses have one seat, one account, one MFA phone — exactly the configuration vendors tell you not to automate.
4. **Locks cannot fix this, structurally.** Kleppmann's fencing argument (2016) needs the *resource* to reject stale tokens; a third-party website never will. So safety lives at the browser boundary: read-back before dispatch, verify after write, at-most-once submit. That, not the plumbing, is the hard part of §5.
5. **The gap is coordination, and it is small enough to build.** Every vendor isolates; nobody leases a *record* or a *site account*, because that requires our action gate, our epoch and our read-back — about a day of work for the demo in §6.

## 2. Findings

### 2.1 What actually breaks

**Profile and process collisions** (best evidenced). Chrome allows one live process per user-data directory, so any tool defaulting to a persistent profile fails on the second concurrent user: `playwright-mcp` returns `Browser is already in use … use --isolated` (#1594); `browser-use`'s default `user_data_dir` causes `SingletonLock` contention (#4548, Mar 2026) and its parallel-agents example was withdrawn, not fixed (#1832); `agent-browser` crashes Chrome silently when a second `--session` meets a configured profile (#1378); sub-agents inherit the parent profile, so tabs close and focus jumps (openclaw #3605, Jan 2026).

**Shared state inside one browser** (the interesting one). agent-browser #326 reproduces it: the daemon holds one active-page pointer, one frame, one console array, one ref map, no per-connection state. A opens `example.com`; B navigates `httpbin.org` on the same session; A's `get url` now reports `httpbin.org`, and A sees B's console output. Fixed in v0.34.0 via unique `--session` plus `--pin-tab`; still open: shared `--profile` dirs (#896), cookie and storage isolation (#1068), fallback to `about:blank` (#1211), reconnection after an external Chrome restart (#1272). **Isolation was added as an opt-out from sharing; coordination was not built.**

**Human/agent collision in one real browser.** In the same thread a user reports that opening a tab or switching profile mid-run makes the agent's `open` navigate *their* tab; his workaround reselects a tab index before every command and breaks when tabs close. Claude Code's Chrome docs describe the intended model: the agent "shares your browser's login state", collects tabs into a per-session tab group, and pauses for login/CAPTCHA — one person, effectively serial. No doc describes two sessions sharing one Chrome safely.

**Lost updates and duplicate writes.** Once two actors can act, "submit" stops being idempotent: a timeout after a successful submit invites a second. I found no rigorous measurement in a browser-agent setting, so the evidence is weak and the reasoning is ours. Salesforce shows the shape: blocking concurrent sessions for one username needs a login-flow workaround, not a setting, and people sharing a username has no declarative answer.

**Rate limits are quota, not bugs.** Browserbase: 3/25/100/250+ concurrent browsers by plan, 5–150 new sessions a minute, 429 with `retry-after`. Cloudflare Browser Run: 3 on Free, 200 on paid since Aug 2026. The scarce resource is the *site account*, not the agent.

### 2.2 Prior art, and what each piece does not solve

| Thing | Gives | Doesn't |
|---|---|---|
| Kernel (commercial) | Dedicated VM per session, <30ms cold start, profiles, live view, replays (vendor claims) | Any coordination between sessions |
| Browserbase (commercial) | Contexts persist cookies/storage/IndexedDB; explicit "don't use one Context concurrently"; per-org concurrency accounting | Leases, presence, handoff |
| Cloudflare Browser Run (commercial) | Sessions, live debug, human intervention, replays, 200 concurrent on paid | Anything beyond one session |
| Claude in Chrome (commercial) | The real thing: the user's logged-in Chrome, tab group per session, pauses for CAPTCHA, allow/block lists | Multi-agent guarantees of any kind |
| A2A spec | Task lifecycle, streaming, `tasks/resubscribe` — handing a *task* between agents | Browser state; gap-free handoff is still open (#1635: do events lost during a disconnect replay?) |
| MCP spec/SDKs | A natural place for browser tools | Multi-client concurrency (#1215, #2297, no session id) |
| Distributed locks (Kleppmann; etcd; Hazelcast) | Leases, fencing tokens, proof that a lease alone is unsafe | Enforcement at the resource — impossible for a website |
| CRDTs / optimistic concurrency | Merge semantics for concurrent document edits | HTML forms carry no per-field authorship, so merge must be reconstructed |

**Research that says this is the right problem.** TheAgentCompany (CMU; 175 tasks over GitLab, ownCloud, Plane and RocketChat) benchmarks agents doing real work in a company's web services, where tasks need coordination with colleagues. AgentWebBench (ICML/PMLR 306, 2026) has a user agent coordinate with website-side content agents and finds coordination generally lags centralised retrieval, shrinking with scale and planning. WeClawArena (arXiv 2608.03499) formalises delegated agents acting across several owners' workspaces and scores utility separately from attack success — the shape a shared browser should be judged in. None supplies an implementation.

## 3. Workflow table

| Who does the work | Trying to | Where API/MCP fail | Browser adds | What goes wrong with several actors | Evidence |
|---|---|---|---|---|---|
| Two devs, one coding agent each | Reproduce a bug on staging, prove the fix | No API for "does this render right"; each browser MCP binds a singleton profile | Rendering, console, network, screenshot | Second client dies on the profile lock; a shared seeded account means whoever runs second sees mutated state; one dev's deploy makes the other's snapshot stale | playwright-mcp #1594; browser-use #4548; agent-browser #326 |
| Analyst + their side-panel agent | File an expense or update one CRM record | No API; user already signed in | The existing login, no credential handling | Human opens a tab and the agent drives it; agent fills a field the human just edited | agent-browser #326 comment (Mar 2026); Claude Code Chrome docs |
| Two lawyers + paralegal, one CLM seat | Send one contract for signature, record it | Seat-tiered APIs; envelope creation usually needs admin | Works through the entitled seat | One seat, two sessions: forced logout mid-run; a retry creates a second envelope | Browserbase Contexts doc; Salesforce session material; vendor specifics **(unverified)** |
| Three AP clerks, one portal login, one MFA phone | Submit an approved payment batch | Portal has no API; MFA bound to one device | One authenticated session, three queues | MFA prompt goes to whoever holds the phone; session invalidated on second login; batch submitted twice | Browserbase Contexts doc; MFA specifics **(unverified)** |
| Two support agents' agents, one shared web inbox | Triage and reply to one queue | Helpdesk APIs are seat/rate limited; internal consoles have none | Console is where queue truth lives | Both reply to the same ticket; the "assign to me" race; no idempotency on send | MCP #1215/#2297; duplicate-submit write-ups (weak) |
| Several officers' agents, one registry account | File a statutory form once | Filing APIs gated; browser filing is the only route | Real portal, real validations | One submission per form; a retry duplicates a filing; session expires mid-form | Pattern only; **(unverified)** per registry |
| Nightly regression agent + human QA, one tenant | Verify a release, then let QA explore | Test APIs need fixtures; no per-run isolation | Whole product incl. auth and rendering | Agent's test data pollutes the human's session; human edits fail agent assertions | browser-use #1832; agent-browser #326 |

## 4. Removal test

| Workflow | What stops working without a browser | Verdict |
|---|---|---|
| Devs' agents on staging | Everything after the build: visual check, console, logged-in flow | **Keep** — browser is the task |
| Analyst's agent in their own tab | Everything; the point is the existing login and no API | **Keep** — strongest browser-native case |
| Two lawyers, one seat | Envelope creation could be API if the plan allowed; the seat is the only reason for the browser | **Weaken** — a licensing workaround, not a capability gap. Don't lead with it |
| AP clerks, one portal login | The submission; no API, MFA on one device | **Keep**, if the queue and MFA handoff are shown honestly |
| Support inbox | Reply could be API; shared-console truth is the browser part | **Weaken** — a decent API erases most of it |
| Registry filing | Filing itself; and we have nothing legitimate to file | **Drop** |
| Nightly QA vs human | Visual/behavioural verification on a shared tenant | **Keep** as a fixture, not a product |

Two of seven survive cleanly, which is the useful result: browser-shared work is strongest where the login *is* the permission and the page *is* the system of record.

## 5. Shared browser requirements

| Part | What it does | Hardest problem |
|---|---|---|
| Identity vault | One profile per *site account*, released as a ready-authenticated context; password and MFA seed never enter the model; identity recorded per action | Sites log out concurrent sessions, so identity and concurrency conflict head-on, and one seat is the customer's reality |
| Lease manager | Leases on page (exclusive write), record (advisory "I intend to change supplier X"), account (capacity), each with a monotonic epoch | Expiry while a process is paused — resolved by epoch comparison, never clocks |
| Action gate outside the model | Checks epoch, the page digest the agent reasoned about, and policy fixed before the run; stale ⇒ drop and re-observe | The site never enforces our epoch, so the gate protects only our dispatch; a submit already sent is irreversible |
| Versioned observation | Each accessibility snapshot stamped with digest + epoch; refs valid only for that stamp; another actor's write invalidates it | Separating SPA cosmetic churn from "the thing I meant to click changed" |
| Intent registry / presence | Who is on which record, doing what, having touched what — presence with intent, not a cursor | Staying honest when an actor crashes or goes silent |
| Per-account scheduler | Token bucket and fair queue per site account, so 429s become waiting and one agent cannot starve another | Fairness across *people*, since quota is per account |
| Handoff protocol | Agent→agent and agent→human at a checkpoint: URL, pending action, intent, dirty fields, evidence, screenshot | Live JavaScript state cannot be serialised, so handoff is always "resume at a boundary" |
| Field-level form merge | Track fields this actor dirtied; never write a field another actor touched since your snapshot | No authorship in HTML, so it must be reconstructed from diffs, and a validation error can force a rewrite of someone else's field |
| Audit store | Per action: actor, on-behalf-of, lease, epoch, digest before/after, screenshot, outcome | Proving causality, not adjacency |

**Four rules.** Isolation is not coordination: private browsers stop profile locks and do nothing about two actors editing supplier X. Serialise at the account, parallelise elsewhere. Give each actor one MCP tool surface keyed to its identity, not one per browser — the gateway must inject identity, since MCP cannot tell concurrent sessions apart, and tool schemas cost tokens every turn. Submit at most once: read back before submitting, record the intent, and halt for a human when the outcome is ambiguous. Verify, don't trust — success is the site's state, never the agent's claim.

## 6. One end-to-end workflow

**"One portal, three seats": supplier onboarding through a shared browser.**

Setup: one headful Chrome on the projector; one labelled mock procurement portal with a single supplier account; three actors — Agent A (diligence), Agent B (documents and bank details), a human procurement lead — each with their own credential to the shared browser, all driving the same portal session.

1. The human opens case `SUP-1042` and puts three work items into the shared browser queue. Agent A claims the *Security questionnaire* (board: `SUP-1042/security — A, epoch 7`); Agent B claims *Bank details* on the same record, gets a shared-record intent read (not a block), and the board shows two actors on one record in different sections.
2. A reads the supplier's public pages and the prior questionnaire, drafting each answer with its source URL; every action is gated on epoch and digest.
3. **Seeded collision.** The human opens the security page and edits one answer. The digest changes, A's next action is dropped with `stale snapshot (7 ≠ 8)`, A re-observes, sees the human's edit, and fills only the fields it still owns. *This is the visible moment.*
4. B's bank-details submit hits a validation error on a field the human changed; the merge rule blocks the overwrite and raises a handoff card.
5. **Handoff.** A hands the section to the human with the exact pending action, page state, evidence bundle and a "could not verify" list.
6. The human approves, binding to an epoch, and the submit executes once. On a forced timeout the gate reads the portal back, finds `status = Submitted`, and does not resubmit.
7. **End state:** `SUP-1042` submitted, one submission event, all sections complete.

**How a judge confirms it.** The portal's event log (one submission, three distinct actors, per-field authorship); the audit export (actor, on-behalf-of, lease, epoch, digest, outcome — the dropped stale action shown as *dropped*); a board replay of lease handoffs and queue waits replacing 429s; and a negative check that the human's hand-edited field still holds the human's text.

**Why this one:** several people and their agents genuinely must touch one account, success is checked in the portal rather than our logs, and the browser is irreducible — the task exists because there is one login and no API.

## 7. Risks and unknowns

- **Exactly-once submission is not achievable in general.** We can show at-most-once via read-back; a judge asking "what if the read-back is wrong" has a fair point.
- **Terms of service.** Sharing one seat across people usually violates vendor terms; I verified no per-site position. The mock portal is the safe demo; a team/legal call, not settled here.
- **Weak evidence, flagged.** The 2026 "parallel browser agent" blog posts (capsolver, screenshotneo, browserspin, dev.to lease posts) read as SEO or self-promotion, likely AI-written. I used them for vocabulary only.
- **Vendor numbers are vendor claims:** Kernel's 97.5M sessions/Sept 2026 and <30ms cold start, Cloudflare's 200, Browserbase's plan table.
- **Unverified:** Steel (docs URL 404'd, search rate-limited) and whether two Claude-in-Chrome sessions can share one Chrome safely — the latter worth a two-minute test.
- **Chrome profile exclusivity** rests on four independent tool issue trackers, not Chromium's own docs, which I did not fetch. **MCP multi-client gaps** come from SDK and transport issues; some have closed, so re-check #1215 before quoting it as current.
- **No product was found that coordinates rather than isolates.** If one launched recently this track would have missed it: searches covered the named vendors plus issue trackers, not every startup.

## 8. Three openings

**O1. Lease-and-epoch action gate for a shared agent browser.** *New:* "claim this section, then act under an epoch", with the gate enforcing it and stale actions visibly dropped. *Nearby:* profile leases and browser pools (orion-browser's leases, Reticle's per-project daemons, the `orcheems` package, a single-slot mutex in a public repo) and agent-browser's per-session isolation — all single-tenant locks or isolation, none with record-level intent or read-back. *Evidence:* agent-browser #326 and its four open follow-ups, playwright-mcp #1594, browser-use #4548/#1832.

**O2. Stale-view guard with field-level form merge.** *New:* a versioned DOM snapshot bound to a lease epoch, plus dirty-field tracking, so a human edit survives an agent's form fill — collaborative-editing semantics for plain HTML forms. *Nearby:* Playwright's actionability checks handle disabled or covered elements, not concurrent authorship; CRDTs handle documents, not forms. *Evidence:* the tab hijack when a human touches the browser; Kleppmann for why "just lock it" fails.

**O3. Per-account presence board and queue.** *New:* one board showing who is on which site account and record, with a fair queue and token bucket, so 429s and forced logouts become waiting. *Nearby:* Browserbase and Cloudflare concurrency controls are admission control, not fairness or presence, and neither knows a record exists. *Evidence:* Browserbase's "avoid simultaneous logins", the 429 tables, Salesforce's missing concurrent-session setting.

For a 09:00 freeze: O1 and O2 are the demo-critical pair, both visible on a labelled mock portal with two agents and one human. O3 is a thin read-only board over the same lease data — cheap if O1 exists, and it is what makes the shared browser legible to a judge. Licences, checked today via the GitHub API: agent-browser and Playwright are both Apache-2.0 (permissive, fine to adopt as low-level driving); the browser-infrastructure vendors are commercial services to rent, not code to copy.

## 9. Sources

Primary defects (all read today): vercel-labs/agent-browser #326 (reproduction, v0.34.0 fix, open #896/#1068/#1211/#1272) and #1378 (profile/`--session` crash); microsoft/playwright-mcp #1594 (second client, profile lock); browser-use #4548 (`SingletonLock` contention) and #1832 (example withdrawn); sumyapp/playwright-parallel-mcp #4 (`--isolated`); openclaw #3605 (sub-agents share profile); NousResearch/hermes-agent #49691 (single global CDP endpoint).

Vendor docs: docs.browserbase.com/features/contexts (persistence + "avoid simultaneous logins"); docs.browserbase.com/optimizations/concurrency/overview (limits, 429, retry-after); docs.browserbase.com/account/billing/plans (tiers); developers.cloudflare.com/browser-run/limits/ and /changelog/post/2026-08-20-limits-increase/ (3 → 200 concurrency); kernel.sh/browsers and /docs/overview/concepts (VM per session, live view); code.claude.com/docs/en/chrome (shares login state, tab group, pauses for CAPTCHA); support.claude.com/en/articles/12902446 (permissions).

Protocols: a2a-protocol.org/latest/topics/life-of-a-task/ (task lifecycle); a2aproject/A2A #1635 (events lost on resubscribe); modelcontextprotocol/servers #1215 (one-client design) and #2297 (cross-session mixing); anthropics/claude-code #41836 (no session id to MCP servers); confluentinc/mcp-confluent #122 (HTTP transport crash with concurrent clients).

Coordination theory: martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html (fencing tokens); antirez.com/news/101 (rebuttal); etcd contrib/lock/README.md (lease false expiry); hazelcast.com/blog/long-live-distributed-locks/ (fenced locks in practice).

Site-side session practice: salesforce.stackexchange.com/questions/3870 (no declarative way to block one username across sessions); help.salesforce.com `security_login_flow_limit_concurrent_sessions` (login-flow workaround).

Research: the-agent-company.com and arxiv.org/html/2412.14161 (175 tasks, GitLab/ownCloud/Plane/RocketChat); proceedings.mlr.press/v306/zhong26n.html (AgentWebBench, ICML 2026); arxiv.org/html/2608.03499 (WeClawArena).

Weak, vocabulary only: danmercede.com/guides/multi-agent-browser-pool, dev.to/web4browser profile-lease posts, docs.reticle.sh/multi-agent-testing, pypi.org/project/orcheems/, github.com/taracodlabs/aiden core/playwrightBridge.ts (the mutex), capsolver/screenshotneo/browserspin/roboqa 2026 posts.
