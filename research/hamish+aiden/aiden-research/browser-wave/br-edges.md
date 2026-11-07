# br-edges: where APIs and MCP run out

Research agent br-edges, 7 November 2026. Every claim carries a URL; third-party measurements and vendor claims are labelled.

## 1. Bottom line

1. **The gap is real but narrower and more temporary than vendors imply.** AWS's own engineers call console-only features "a pretty rare thing" ([Stack Overflow, 2016](https://stackoverflow.com/questions/35574645/aws-is-anything-the-api-cant-do)); what persists is narrow settings and admin screens ([Terraform AWS #49070, Jul 2026](https://github.com/hashicorp/terraform-provider-aws/issues/49070)). A browser option should be a **dated escape hatch**, not a second integration platform — and each hatch should close itself once it works.
2. **Cost is decided by the interface, not the model.** A structured API did an admin task in 8 calls / 12K tokens / 20s that vision computer use did in 53 steps / 551K tokens / 17 min — 45× ([Reflex benchmark as reported, May 2026](https://artificialcuriositylabs.ai/posts/api-first-computer-use-last/)). The same author's 8 harness runs spanned **$0.03 (purpose-built Playwright script) to $5.44** for one task; the LLM-driving-a-browser version of the *same* browser work cost $3.41. This is our biggest lever on the token and time criteria.
3. **Escalation is where agents fail, not clicking.** In a controlled 50-task study, "giving the model both interfaces doesn't automatically make it route between them" ([Scale Labs, 7 Nov 2026](https://labs.scale.com/blog/mcp-vs-cli)). In production captures, Codex never found an available MCP server in **8 of 80 runs and "tried a browser instead"** ([Spirit Room, 21 Oct 2026](https://spiritroom.app/blog/how-many-mcp-tools-is-too-many/)). Routing needs a written policy and typed failure codes.
4. **MCP is not a stable floor to build the fallback on.** The 2026-07-28 stateless revision removed `initialize`, sessions and SSE resumability; servers died with `-32601 Method not found: initialize` ([writeup, 28 Jul 2026](https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/3249), [migration note](https://particula.tech/blog/mcp-stateless-spec-migration)); a 101-server audit found 9 archived and 4 unpushed for a year ([SkillAudit, Apr 2026](https://skillaudit.dev/blog/nine-archived-mcp-servers-maintenance-signal/)). A browser path is the only tier that survives a vendor schema change.
5. **Browser schemas are expensive and browser access is being fenced.** Playwright MCP's 21 tools cost ~13.7k tokens (7% of context), Chrome DevTools MCP's 26 tools ~18k, before any work ([fsck.com, Oct 2025](https://blog.fsck.com/2025/10/19/mcps-are-not-like-other-apis/)). Cloudflare can now filter "Agent" traffic separately ([4 Nov 2026](https://blog.cloudflare.com/personal-agents-visibility-control/)), and bot checks stopped 4.4–8.6% of runs on 500 real stores in a vendor benchmark ([browser-use](https://browser-use.com/benchmarks/consumer)). Sites are starting to *offer* tools instead: WebMCP is in origin trial to Chrome 162, ending 30 Mar 2027, no ship date ([tracker](https://webmcp.com/ecosystem-tracker), [Chrome docs](https://developer.chrome.com/docs/ai/webmcp)).

## 2. Findings

### 2.1 Where APIs and MCP actually stop

| Gap | What it looks like | Evidence |
|---|---|---|
| **No endpoint for one setting** | API 95% complete; one field is console-only | Terraform AWS: Control Tower Account Factory network config ([#49070](https://github.com/hashicorp/terraform-provider-aws/issues/49070), Jul 2026), WorkSpaces `device_type_linux` ([#17553](https://github.com/hashicorp/terraform-provider-aws/issues/17553), 2021) |
| **Read-only console reports** | Data rendered in an admin UI that no API returns (until it does) | Netflix built Aardvark to log into the AWS console with PhantomJS and scrape IAM Access Advisor, "only available in the console" ([Netflix, 2017](https://netflixtechblog.com/introducing-aardvark-and-repokid-53b081bf3a7e)) |
| **Identity proof** | The wall is proving who is acting: SSO, 2FA, passkeys, consent | OpenAI's cloud browser *pauses* and shows a secure form; the model never sees credentials ([OpenAI Help Center](https://help.openai.com/en/articles/20001280-using-cloud-browser-in-chatgpt)) |
| **Page mechanics** | Cross-origin consent iframes, closed shadow DOM, canvas tables | Cookie consent (Sourcepoint) in a cross-origin iframe that Playwright cannot click from the parent ([issue #20](https://github.com/feder-cr/invisible_playwright/issues/20)); closed shadow roots unreachable ([Playwright #33725](https://github.com/microsoft/playwright/issues/33725)) |
| **Tool-surface gaps** | MCP server missing, thin, broken or too big | 9/101 archived ([SkillAudit](https://skillaudit.dev/blog/nine-archived-mcp-servers-maintenance-signal/)); Codex missed tools in 8/80 ([Spirit Room](https://spiritroom.app/blog/how-many-mcp-tools-is-too-many/)); July 2026 breakage ([#3249](https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/3249)) |

Two things are **not** edge cases: pages a plain HTTP fetch handles, and anything with a real API. Feigning a browser need is easy to spot.

### 2.2 How an agent should choose per step

The published ladder is native API → connector/MCP → browser automation → computer use → human ([artificialcuriositylabs, May 2026](https://artificialcuriositylabs.ai/posts/api-first-computer-use-last/)); Anthropic reportedly recommends the same. Two refinements matter more than the ladder:

- **"Browser" is two tiers.** A compiled Playwright script ($0.03) is a different animal from an LLM agent driving the DOM ($3.41) on the same task. Prefer the script; use the agent only to *discover* the script.
- **Escalation needs typed reasons:** `no_endpoint`, `endpoint_incomplete`, `auth_mfa`, `consent_required`, `render_only`, `challenge`, `tool_missing`, `tool_schema_changed`, `stale_route`. Each maps to escalate, ask a human, stop, or recompile. Without this, "try the browser" becomes the model's excuse for a failed API call — exactly the Codex behaviour above.

**Does anything do this well?** Partly. `Unbrowse` (paper, 1 Apr 2026) passively learns first-party "shadow" routes from browsing traffic and runs three paths — local cache, shared graph, browser fallback — averaging 950 ms warm vs 3,404 ms for Playwright (3.6×) ([arXiv 2604.00694](https://arxiv.org/abs/2604.00694)). It is a prototype with a payment model attached; no production adoption found (**unverified**). Compass sells per-request routing across scraping and browser tools ([compassrouting.com](https://www.compassrouting.com/)) — vendor claim; Arcade documents a fallback-tool pattern ([arcade.dev](https://www.arcade.dev/patterns/fallback-tool/)). None does **per-step** routing with a decision record, which is the gap.

**Can a browser run become a cheaper call later?** Three ways, increasing in ambition: (a) the agent writes a Playwright script and replays it — the 180× spread above is mostly this; (b) a route cache that skips the browser (Unbrowse, 3.6×); (c) guarded step replay, which the first wave found 8.5–13× faster with no per-step model calls. All three pay only on **repeats**, so the workflow must repeat.

### 2.3 Delivery form and its real costs

| Form | Cost profile | Strong when | Weak when |
|---|---|---|---|
| **MCP server (browser)** | 13.7k tokens (Playwright, 21 tools) to ~18k (Chrome DevTools, 26), loaded up front in eager clients; search clients load names only | Portability across hosts, remote/shared sessions, typed audited actions | Host loads eagerly; a gateway silently disables tool search |
| **CLI** | Near zero until invoked | Agent has a shell and you own the machine | Results need parsing; not portable to GUI hosts |
| **Skill (Markdown + scripts)** | Pays on load, then minimal; smallest in one head-to-head ([waylandz, 2026](https://waylandz.com/blog/mcp-webmcp-cli-skills-comparison/)) | One well-documented tool; internal team | No schema validation, shared auth or governance |
| **Extension (Claude in Chrome)** | No schema cost; uses the human's own profile and logins | Personal work where identity is the human's | Unauditable, per-user install, hard to share; the closed-shadow-DOM workaround *is* an extension |
| **Gateway / router** | Central filtering, per-key scoping, a hop | Many teams, many servers, cost control | Config traps: Claude Code behind a custom API base URL turned tool search off, sending **143,357 vs 22,446** first-request tokens ([Spirit Room](https://spiritroom.app/blog/how-many-mcp-tools-is-too-many/)) |

Two measured warnings. (1) **One tool per endpoint does not scale**: a 99-tool server was 68,286 tokens of schema, two tools were a third of it, and 5 servers × 30 tools ≈ 30–60k tokens before the user's question ([Boomi, Dec 2025](https://boomi.com/blog/why-is-there-mcp-tool-overload-and-how-to-solve-it-for-your-ai-agents/)). (2) **Discovery is the new failure**: under search-based loading a start-here tool took right-first-step from 1/24 to 24/24 ([Spirit Room](https://spiritroom.app/blog/how-many-mcp-tools-is-too-many/)). Anthropic's answer is code execution plus a Tool Search Tool, claiming 150k → ~2k tokens — **vendor claim** ([Nov 2025](https://www.anthropic.com/research/code-execution-with-mcp)).

**Implication:** ship the browser as a **small surface** — one `browser_run(goal, url, expectations)` tool plus `gap` and `promote`, not 21 verbs — and put the verb list in a document the agent fetches.

## 3. Workflow table

| # | Who | Trying to | API/MCP fails because | Browser adds | Multi-person/agent problem | Evidence |
|---|---|---|---|---|---|---|
| 1 | Platform engineer + agent | Set a Control Tower Account Factory network config | No resource or API for that field | Reaches the console screen, reads it back to prove it applied | Two agents in one console session overwrite unsaved form state; one person's MFA blocks the other's run | [#49070](https://github.com/hashicorp/terraform-provider-aws/issues/49070) |
| 2 | Security engineer (historic) | Inventory which IAM roles were used | Access Advisor was console-only | Logged-in scrape at scale | Shared admin credentials; every scraper is another login to one seat | [Aardvark, 2017](https://netflixtechblog.com/introducing-aardvark-and-repokid-53b081bf3a7e) |
| 3 | Coding agent | Confirm a preview renders and submits | HTTP 200 says nothing about layout, hydration, or a dead button | Real rendering, screenshots, accessibility tree, clicks | Parallel worktrees want parallel browsers; tabs and profiles collide | [13.7k tokens](https://blog.fsck.com/2025/10/19/mcps-are-not-like-other-apis/) |
| 4 | Anyone behind SSO+2FA | Get one number out of a vendor dashboard | API keys need an admin; SSO apps aren't scriptable | Human signs in, agent continues in that session | Whose identity? Persisting cookies hand the next person the last person's access | [OpenAI Help](https://help.openai.com/en/articles/20001280-using-cloud-browser-in-chatgpt) |
| 5 | Agent on a third-party MCP server | Finish a task whose tool surface changed | Server breaks after a protocol revision, or the tool is never found | Falls back to the site's own UI and finishes | Every user's agent rediscovers the breakage; no shared record | [#3249](https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/3249), [Spirit Room](https://spiritroom.app/blog/how-many-mcp-tools-is-too-many/) |
| 6 | Agent hitting a consent wall | Reach the page behind a CMP | Not an API problem at all | Frame-level clicking, or a recorded consent decision per user | One agent's "accept all" becomes another person's consent — a legal problem | [issue #20](https://github.com/feder-cr/invisible_playwright/issues/20) |
| 7 | Agent on a defended public site | Read or submit where there is no API | No endpoint, and the site classifies "agent" traffic | A signed, honest agent identity may be allowed where headless isn't | Per-agent reputation; blocking one can block the team's IP | [Cloudflare](https://blog.cloudflare.com/personal-agents-visibility-control/), [benchmark](https://browser-use.com/benchmarks/consumer) |

## 4. Removal test

- **1 (Control Tower setting):** impossible without a browser, not slower — a human must click. **Keep.**
- **2 (Access Advisor):** likely has an API today (`GetServiceLastAccessedDetails`); **unverified** here. Good history, and a warning that **hatches close**. Not a product.
- **3 (preview verification):** degrades to "the server said 200". Real loss, but it is br-engineering's workflow.
- **4 (2FA dashboard):** a person does it by hand instead. **Real loss**, and honestly framed as "we make the human's click go further", not "we removed the human".
- **5 (broken MCP server):** the browser keeps the task alive when the tool vanishes. **Real loss** — the clearest case for a browser tier beside MCP rather than instead of it.
- **6 (consent wall):** the browser is the only place the choice exists, but automating it is a legal risk. Keep only as a **consent ledger**.
- **7 (defended site):** without a browser there is nothing; with one there may still be nothing. **Weak** — stop and hand off, never evade.

## 5. Shared browser requirements this track implies

1. **Capability record per site and step**: tier known to work (API / MCP tool / compiled route / browser recipe), version, last-verified date, cost, failure history — one store shared by everyone's agents.
2. **Deterministic per-step router** using the typed codes above; escalation is a rule with a budget, never a model's mood.
3. **Decision record**: each step logs tier, escalation reason and the gap's citation, so the audit answers "why did a robot click that?".
4. **Per-person human handoff** for credentials, 2FA and consent; secrets never reach the model; sessions expire and never pass between people.
5. **Promotion and expiry**: a browser step that succeeds twice becomes a guarded compiled route or MCP tool with post-conditions, demoted automatically when it fails.
6. **Leases on single-seat logins and shared rate budgets**, so three agents don't fight over one console session or one quota.
7. **Access and consent gating before the first request**: robots, terms, Cloudflare agent policy, signed-agent identity — checked, recorded, refused if disallowed.
8. **Tiny tool surface**: one browser tool plus a fetched playbook, so the browser option costs hundreds of tokens, not 13,700.

## 6. One end-to-end workflow: The Escape Hatch

**Task:** three people's agents apply settings their infrastructure-as-code tooling cannot express (modelled on the Control Tower and WorkSpaces cases), prove they took effect, and never rediscover the gap.

Actors: Priya (platform), Tom (security), one agent each, one shared browser service.

1. **Plan.** Priya's agent is asked to set "Account Factory network config = isolated VPC". The capability record says no API route (**gap #1**, cited to Terraform #49070).
2. **Try the cheap tier and fail loudly.** It calls the API, records typed result `no_endpoint` with the raw error — evidence, not assertion.
3. **Lease, then escalate.** It takes a lease on `console:acct-123` (single seat) and opens the console through the shared browser. Tom's agent requests the same lease and **queues** instead of opening a second session.
4. **Human handoff.** The console demands MFA. The browser pauses, shows Priya a secure form, she approves on her phone; the model never sees the secret. Cap 60 seconds, then stop.
5. **Do the work, then verify.** It sets the field and **re-reads the console state, diffing against the expected value** — not its own success message.
6. **Second gap, different outcome.** A follow-up needs `device_type_linux`; the same path runs, and a promotion fires: two successes become a guarded Playwright route with post-conditions.
7. **Promote.** The route is registered as *browser route v1, verified 7 Nov 2026* and exposed as one MCP tool `set_account_factory_network_config`.
8. **Second person, much cheaper.** Tom's agent calls the compiled tool on another account: no page reasoning, no 21-verb schema, and the live token/time counter visibly drops for that leg.
9. **End state.** Both accounts show the settings; the register shows one gap now closed by a route; the evidence bundle lists every step with tier, reason, timestamps and hashes of before/after screens.

**How a judge confirms it:** the gap register shows the API attempt and its real error; the MFA pause is a human in real time; the read-back matches the intended value; step 8's counter is materially lower than step 5's on the same work; the bundle reconciles independently. **Honesty note:** accounts must be labelled mocks — we have no legitimate AWS account to change.

## 7. Risks and unknowns

- **I ran nothing.** Browser-mechanics claims (CMP iframes, closed shadow DOM, MCP token counts) are second-hand. Test a real consent CMP and a heavy JS register page headed before promising either.
- "Console-only is rare" is a 2016 quote; the 2026 Terraform issues show it still happens, but frequency is unknown.
- The 45× and $0.03-vs-$3.41 figures are one author's runs plus a cited vendor benchmark: directionally sound, not a guarantee on our pages.
- **Unbrowse** is a paper; no code licence found, no adoption evidence.
- **WebMCP** could change the premise by 2027: if sites expose tools, the browser becomes a tool *host*, not a scraping surface. Watch it, don't build on it.
- **Legal/ToS:** automating an admin console may breach an acceptable-use policy even with the owner's credentials. Check per site; treat a challenge as a stop, never an obstacle to work around.
- Injected content inside an admin console is the worst case for prompt injection: the first wave's action gate is mandatory here.

## 8. Three openings

1. **Gap register + escape-hatch router.** New: per-step tier decisions with typed failure codes, a shared record of which sites need a browser and why, and automatic promotion of a working browser path into a compiled route. Nearby: Unbrowse (paper), Compass (vendor routing), Arcade (fallback pattern) — none publish a step-level decision record with promotion. Evidence: Scale Labs (no self-routing), Codex 8/80, Unbrowse 3.6×, $0.03 vs $3.41. Buildable before 09:00 with `agent-browser` + a policy file + Playwright.
2. **One-tool browser surface with a fetched playbook.** New: a single `browser_run` tool whose capabilities live in a document read on demand, plus `promote` to turn a run into a tool. Nearby: Anthropic's code-execution and tool-search advice (vendor), the 4-tool-vs-99-tool result. Evidence: 13.7k/18k token schemas; 1/24 → 24/24 with a start-here tool; the 143k-vs-22k gateway trap.
3. **Access-and-consent ledger.** New: before the first request, record robots, terms, Cloudflare agent-policy class, signed-agent identity, and the human's consent decision, then surface it in the evidence bundle. Nearby: Cloudflare agent policies (Nov 2026), Web Bot Auth signed agents. Evidence: agent traffic classification, 4.4–8.6% blocked runs, CMP-iframe failures. Cheap, and it scores on the legal criterion without giving legal advice.

## 9. Sources

- stackoverflow.com/questions/35574645/aws-is-anything-the-api-cant-do — AWS engineer: console-only features, "pretty rare" (2016).
- github.com/hashicorp/terraform-provider-aws/issues/49070 (Jul 2026), /17553 (2021), /33962 (2023) — console-only settings still missing from API/Terraform.
- netflixtechblog.com/introducing-aardvark-and-repokid-53b081bf3a7e — PhantomJS login + scrape of console-only Access Advisor (2017).
- artificialcuriositylabs.ai/posts/api-first-computer-use-last/ — tier hierarchy, 45×, $0.03–$5.44 harness runs (May 2026).
- labs.scale.com/blog/mcp-vs-cli — 50-task MCP vs CLI study; agents don't self-route (7 Nov 2026).
- spiritroom.app/blog/how-many-mcp-tools-is-too-many/ — 99 tools = 68,286 tokens, per-app loading, Codex browser fallback 8/80, 1/24→24/24, gateway trap (Oct 2026).
- blog.fsck.com/2025/10/19/mcps-are-not-like-other-apis/ — Playwright MCP 21 tools ≈ 13,678 tokens.
- teamday.ai/blog/lightweight-browser-skill-beats-mcp — Chrome DevTools MCP ≈18k tokens, 26 tools.
- anthropic.com/research/code-execution-with-mcp, /advanced-tool-use — vendor: 50k+ token definitions, 150k→2k, Tool Search Tool.
- boomi.com/blog/why-is-there-mcp-tool-overload-and-how-to-solve-it-for-your-ai-agents/ — 30–60k token metadata overhead.
- arxiv.org/abs/2604.00694 — Unbrowse shadow routes, three-path execution, 950 ms vs 3,404 ms (Apr 2026).
- compassrouting.com, arcade.dev/patterns/fallback-tool/ — vendor routing and fallback patterns.
- parallel.ai/articles/mcp-vs-skills-vs-clis, waylandz.com/blog/mcp-webmcp-cli-skills-comparison/ — delivery-form comparisons.
- github.com/modelcontextprotocol/modelcontextprotocol/discussions/3249, particula.tech/blog/mcp-stateless-spec-migration — the 2026-07-28 spec change and its symptoms.
- skillaudit.dev/blog/nine-archived-mcp-servers-maintenance-signal/ — 9/101 archived, 4 unpushed a year.
- help.openai.com/en/articles/20001280-using-cloud-browser-in-chatgpt — cloud browser pauses for secure sign-in.
- github.com/feder-cr/invisible_playwright/issues/20 — consent CMP in cross-origin iframe blocks Playwright.
- github.com/microsoft/playwright/issues/33725 — iframe inside closed shadow root; extension workaround.
- blog.cloudflare.com/personal-agents-visibility-control/, developers.cloudflare.com/bots/additional-configurations/block-ai-bots/, blog.cloudflare.com/signed-agents/ — agent traffic classes, filtering, Web Bot Auth.
- browser-use.com/benchmarks/consumer — vendor: bot checks stopped 4.4–8.6% of 500-store runs.
- webmcp.com/ecosystem-tracker, developer.chrome.com/docs/ai/webmcp, developer.microsoft.com/.../origin-trials/ — WebMCP origin trial Chrome 149→162, Edge 150, ends 30 Mar 2027.
