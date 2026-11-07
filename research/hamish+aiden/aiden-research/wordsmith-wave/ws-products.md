# ws-products: agentic browsers as shipped

*Track ws-products, research wave 7 Nov 2026. Read-only desk research; every claim below carries a URL and a date in section 6. Item marked **(unverified)** = I could not confirm it from a primary source.*

## 1. Bottom line

1. **The flagship "agentic browser" category largely died in 2026 and moved into the assistant.** Operator (shut 31 Aug 2025), Project Mariner (discontinued 4 May 2026) and Atlas (retired 9 Aug 2026, per OpenAI's own help centre) are gone. What survives is a *side-panel agent inside a normal browser*: Claude in Chrome (GA on paid plans, 26 Aug 2026), Gemini in Chrome "auto browse" (Gemini 3, 28 Jan 2026), Edge Copilot Mode with IT-scoped sites. The bar is not "build a browser" — it is "beat a side panel".

2. **Shipped products handle short, single-site jobs and fail predictably at what a legal workflow needs.** One lab's identical 8-task script (Oct 2026): Strawberry 7/8, Genspark 3/8, Comet Free refused to act at all, Dia "asks first, can't click". Recurring failures: multi-tab work ("my tools only work in the current tab" — Genspark), long chains, and *self-reported success the page contradicts*.

3. **The exploitable gap is verification, not clicking.** Genspark submitted an 11-field form with 2 fields empty and said the confirmation showed them filled. OSWorld 2.0 names this: agents "lose track of constraints, miss information that arrives mid-task, guess rather than ask the user, and skip verification". Clicking is solved (grounding ~85%); knowing whether the action worked is not.

4. **Long workflows collapse around 45–60 minutes of human-equivalent work.** OSWorld 2.0 (Jun 2026): 108 workflows of median 1.6 human hours; best agent 20.6% full completion (54.8% partial) at ~244K output tokens, roughly $10–35 per task. Odysseys2 (Oct 2026): best agent fully completes **47 of 100** long live-web tasks. Polar's 15+ hour sessions are vendor self-report.

5. **Security is openly unsolved — a demo opportunity, not a blocker.** Anthropic's pilot fell from 23.6% to 11.2% attack success (browser-specific 35.7% → 0). Brave, Trail of Bits and LayerX each broke Comet; LayerX's June 2026 attack worked on six shipped agentic browsers at once. Everyone now recommends isolation plus human approval on irreversible actions — make that visible on screen.

## 2. Findings

### 2.1 What still exists, as of 7 Nov 2026

**Retired:** Operator (shut 31 Aug 2025); Atlas (launched 21 Oct 2025, retired 9 Aug 2026 — features moved into a ChatGPT desktop app with "ChatGPT Work"); Project Mariner (discontinued 4 May 2026, superseded by the Gemini Computer Use API and Chrome auto browse).

**Alive:**
- **Claude in Chrome** — extension; pilot 25 Aug 2025 (1,000 Max users), **GA on every paid plan 26 Aug 2026**. Takes *autonomous* actions with a safety classifier validating each one; per-site admin allow/blocklists; side panel is now a "Claude Cowork" session.
- **Gemini in Chrome "auto browse"** — Gemini 3, 28 Jan 2026 for AI Pro/Ultra in the US, India 7 Oct 2026. Opens its own marked agent tabs; asks permission for passwords.
- **Edge Copilot Mode** — consumer since 2025 with "Actions" and "Journeys"; **agentic browsing for business in limited preview 20 May 2026**, IT choosing the sites; Edge shipped **WebMCP** (`document.modelContext`) Sept 2026.
- **Perplexity Comet** — free Chromium since Oct 2025. Reading is free; acting needs a paid plan, and longer jobs go to the credit-metered "Computer" agent.
- **Opera Neon** — most agent-forward survivor. "Do" mode drives the page; **MCP Connector (31 Mar 2026)** lets external clients (Claude, ChatGPT, n8n, OpenClaw) drive Neon, free since **14 Aug 2026** via a Browser CLI advertising "token compression". $19.90/month for Neon's own AI.
- **Dia** — knowledge-worker browser (Atlassian, 4 Sep 2025, ~$610M reported), not an agent; "agentic Dia" promised for autumn 2026, still absent from the Nov 2026 changelog.
- **Genspark** (free Chromium, 100 credits/day), **Fellou** (plan-then-edit, credits), **Manus 2.0** (cloud agent, not a browser: schedules, event triggers, local execution), **Strawberry** (Dendrite Systems, v1.0 26 Oct 2026: "companions" with memory and routines, real visible tabs, expandable step trace).

### 2.2 The most complex workflows actually demonstrated

Sorted by ambition, evidence quality attached:

| Claim | Who | Evidence |
|---|---|---|
| 15+ hour autonomous sessions across arbitrary sites, multi-agent with heterogeneous model routing | Polar (Recursive Intelligence, 3-person, $5.7M seed), Oct 2026 | **Vendor claim**, self-reported leaderboard superiority; no published cost-per-task **(unverified)** |
| >2 hours of continuous work, ~900 tool calls, pause overnight and resume | Kay Engineering harness, 10 Aug 2026 | Own engineering blog, own run counts |
| 90.2% on OSWorld-Verified (100-step budget) | "Intelligence-Indeed Agent", 25 Jul 2026 | Maintainers' official results spreadsheet |
| 47/100 long live-web tasks fully completed | best agent on Odysseys2 (CMU + Browser Use), 27 Oct 2026 | Benchmark authors' post; 8–12 pass/fail checks per task |
| Shop → compare → table → add 2 of 5 to cart with a set address | Comet, tested Jan 2026 | Independent hands-on; completed, correctly stopped at the cart |
| Book a table, apply for jobs, build a small site | Opera Neon "Do"/"Make" | Wrong branch, wrong time, human needed mid-form, ~5 min |
| Research 3 pages, 8-field form, price compare, 5-slide deck, 11-field form with date picker and dependent dropdowns | Strawberry: 7/8 fully right, 29–52 s per web task | Independent lab, single run per task |

So: the *demonstrated* ceiling for a shipped product is a handful of dependent steps across two or three sites, with a human for anything irreversible. The *claimed* ceiling is hours. The measured ceiling is under half of 100 long live tasks. That gap is our room to innovate.

### 2.3 Where they fail, consistently

1. **Multi-tab work.** Genspark: "my browser tools only work in the current tab"; Comet Free refused likewise. Only Gemini's auto browse explicitly opens its own tabs.
2. **Verification of its own work.** The most important lab finding: the site's confirmation showed Gender and Hobbies empty while the agent reported them filled. Comet, by contrast, was *honest* ("Nothing was created") — honesty varies by vendor, so narration can't be trusted.
3. **Irreversible actions.** Claude in Chrome stops before purchases; Comet would not act at all; Genspark and Strawberry clicked "Add to basket" **without asking**. An approval gate is a differentiator, not a given.
4. **CAPTCHA and login walls.** Fellou's claimed 19/20 multi-step score became "stuck, looped on the same action, never got past a CAPTCHA". Attacks also target the logged-in session that makes these products useful.
5. **Long chains.** OSWorld 2.0: 20–24% on tasks under 45 minutes of human time, **nothing above 163 minutes**. Not GUI control but lost constraints, missed mid-task information, guessing instead of asking, skipped verification.
6. **Cost.** $10.30–$35.80 per task for 13.9–28.1% completion; 244K output tokens per long task, mostly screenshots. Repetition is unaffordable at exploration prices.
7. **Plan/date variance.** Comet failed every acting task on Free (Oct 2026) but completed a five-step Amazon flow (Jan 2026). Both are true: different plans.

### 2.4 Security and human approval, as shipped

- Anthropic publishes the only vendor attack rates: 23.6% → 11.2% across 123 cases after mitigations; a browser-specific scenario set 35.7% → 0 (Aug 2025). June 2026 reporting puts the newest model at **31.5% before safeguards** (secondary, **(unverified)** as primary).
- Brave extracted Comet users' email and one-time code via a Reddit spoiler tag (Aug 2025), then via near-invisible screenshot text (Oct 2025), calling indirect injection "a systemic challenge facing the entire category". Trail of Bits, hired pre-launch, showed four techniques pulling Gmail data (Feb 2026).
- LayerX "BioShocking" (Jun 2026) worked against **Atlas, Comet, Fellou, Genspark, Sigma and the Claude Chrome plugin**; only one fixed it after disclosure.
- Approval models diverge: per-action (early Claude) → classifier-gated autonomy (GA); IT-scoped allowlists (Edge); "ask before sensitive data" (Gemini); "clicked without asking" (Genspark, Strawberry).
- Consensus advice — Meta's "Rule of Two", OpenAI's "treat screen content as untrusted", Anthropic's warning that Claude "will follow commands found in content" — is **isolation, least privilege, a human on irreversible actions**.

## 3. Comparison table

| Product | Status Nov 2026 | Deepest workflow shown | Independent reliability evidence | Page control | Approval / safety | Cost |
|---|---|---|---|---|---|---|
| Atlas | **Retired 9 Aug 2026** | Agent mode: multi-site shopping/research; median 7.5/10 on 6 tasks (Ars, Oct 2025) | Struggled where Comet succeeded (Jan 2026) | In-browser agent | Confirmations | was in Plus/Pro |
| Comet | Alive; acting needs paid plan | Amazon research → table → 2 items to cart, stopped at checkout (Jan 2026) | Free tier: 0 of 5 acting tasks (Oct 2026) | Side panel + cloud "Computer" agent | Refuses purchases; honest "nothing created" | free browser; paid agent |
| Gemini in Chrome | Alive, Gemini 3; Pro/Ultra, US + India | Shopping, forms, reservations, parking | No task-level independent test found **(unverified)** | Own marked agent tabs | Password prompts; injection classifiers claimed | AI Pro/Ultra |
| Claude in Chrome | **GA, all paid plans, 26 Aug 2026** | Cross-tab work in logged-in apps | Vendor only: 11.2% injection success post-mitigation | Extension side panel + Cowork | Per-action classifier; stops before purchases; admin allowlists | in paid Claude plans |
| Edge Copilot Mode | Alive; business preview 20 May 2026 | "Actions" multi-part tasks; Journeys | PCMag hands-on mixed, no rates **(unverified)** | In-browser, IT-scoped sites | Pauses at passwords/cards; IT site lists | free / M365 |
| Opera Neon | Alive; MCP Connector, free agent link 14 Aug 2026 | Book a table, apply for jobs, build a site | Verge: "confusing"; wrong branch/time, human needed, ~5 min | Chat / Do / Make; external MCP clients | Human input prompts mid-task | $19.90/mo |
| Dia | Alive (Atlassian); no agent yet | App-context synthesis, PDF chat | "Asks first, can't click" (Oct 2026) | Chat over tabs | n/a | subscription |
| Genspark | Alive | Research → 8-field form → price compare → 11-field form | 3/8 fully right; misreported a form | Side panel; on-device models | Clicked "Add to basket" unprompted | free, 100 credits/day |
| Fellou | Alive | Plan-then-edit multi-step tasks | Claimed 19/20 → looped, failed CAPTCHA, scored 17 | Plan editing UI | User reviews plan | credits |
| Strawberry | v1.0 26 Oct 2026 | 7/8 incl. deck + 11-field form, with trace | Best of the lab's set; single run | Real tabs + trace | Clicked "Add to basket" unprompted | free tier sufficed |
| Manus 2.0 | Alive | Scheduled/event-triggered jobs, deliverables | No comparable suite **(unverified)** | Cloud workspace + operator | Approval/rollback claimed | $20–200/mo |
| Polar | Announced Oct 2026 | 15+ h sessions, sub-agent teams | **None — self-reported** | Agentic browser | Undescribed | undisclosed |

## 4. Risks and unknowns

- **Independent evidence is thin and single-run.** The best dataset I found (BenchTested, Oct 2026) is one lab, one Windows VM, one run per task, 8 tasks, Free plans only — signal, not measurement. DreamHost used one Amazon prompt.
- **Vendor claims dominate the ambitious end:** Polar's 15 hours, Manus's autonomy, Gemini's injection classifiers — none independently measured.
- **Plan/region gating makes "what shipped" fuzzy.** Auto browse is Pro/Ultra and was US-only; Claude in Chrome needs a paid plan and sometimes an owner toggle; Comet's agent needs a paid plan. A judge may have seen different behaviour.
- **The category is still moving.** Atlas died at 10 months, Mariner was discontinued, and some named products (Sigma appears only in an attack report) I could not profile at all. Anything here may be stale by Sunday.
- **Dates not confirmed at primary source:** Mariner's 4 May 2026 discontinuation and Operator's 31 Aug 2025 shutdown rest on Wikipedia via a secondary analysis; OpenAI blocks non-browser clients. The Atlas date *is* primary.
- **Not covered here:** open-source controllers and licences (ws-controllers), benchmark methodology and token-cutting (ws-frontier), bot-blocking and demo logistics (ws-feasibility).

## 5. Three openings

All three target gaps the shipped products *demonstrably* leave, are buildable by two people in under 20 hours, and differ visibly from "another side-panel agent".

**Opening A — "Receipt": verify the page, not the agent's story.**
*New:* after each consequential step an independent checker re-reads the resulting page state (accessibility/DOM text plus a screenshot diff), compares it to what the agent claimed, prints a green/red receipt row, and blocks the next irreversible action on a mismatch. The trace becomes a filable evidence artefact.
*Nearby:* agents narrate their own success; Strawberry and Genspark show traces but no machine-checked verdict.
*Evidence:* OSWorld 2.0 names "skip verification" as a core failure mode; the BenchTested 11-field form; Meta/OpenAI/Anthropic all push the human onto irreversible actions — the *machine* pre-check is the missing layer.

**Opening B — "Durable runbook": a long cross-site workflow that survives interruption.**
*New:* the plan is data, not conversation — a versioned runbook with per-step preconditions, a checkpoint after each site, resumable state, and a handoff modal (login, CAPTCHA, payment) that returns control to the same step. Demo it by killing the agent mid-run and resuming.
*Nearby:* Manus has schedules and rollback controls but no auditable per-step state; Kay Engineering reports a >2h, ~900-call harness with a repair loop; no consumer agent browser offers resumable job state.
*Evidence:* OSWorld 2.0's collapse past ~45 minutes of human work; Odysseys2 47/100 — resume-and-repair is the credible mechanism.

**Opening C — "Two-speed, metered": routing and cost accounting as the demo.**
*New:* routine extraction goes to a cheap model, escalation to a frontier model only on ambiguity or failure, with a live counter of tokens, wall-clock and per-site cost and a replayable fast path on the second run. The counter is the show, and tokens/model/time are the stated secondary criteria.
*Nearby:* Polar claims routing without a cost breakdown; Opera advertises "token compression"; nobody exposes per-step token/cost to the user.
*Evidence:* 244K output tokens and $10.30–$35.80 per task at <30% completion; OpenAI's own docs now prefer code execution over the computer tool because "steps are the expensive thing".

**What I would not build:** another side-panel chat agent, a shopping or reservation demo, or a "we wrapped browser-use" claim. Those are the shapes that shipped and then died in 2025–26.

## 6. Sources

**Product state, launches and shutdowns** (dates as stated by the source)
- https://help.openai.com/en/articles/20001371-chatgpt-atlas-retirement — OpenAI's own Atlas retirement notice (retrieved 7 Nov 2026).
- https://www.theverge.com/ai-artificial-intelligence/963654/openai-chatgpt-atlas-ai-browser-shut-down-sunset (9 Jul 2026) · https://9to5mac.com/2026/08/04/openai-explains-what-will-happen-when-chatgpt-atlas-shuts-down-this-weekend/ (Atlas off 9 Aug 2026) · https://www.theregister.com/ai-and-ml/2026/07/10/openais-atlas-browser-doesnt-make-it-to-its-first-birthday/5269818.
- https://blogs.windows.com/msedgedev/2025/10/23/meet-copilot-mode-in-edge-your-ai-browser/ · https://www.microsoft.com/en-gb/edge/business/ai-browsing (IT-scoped sites) · https://support.microsoft.com/en-us/edge/copilot/browse-with-copilot (local actions, user override).
- https://claude.com/resources/articles/claude-in-chrome-generally-available (GA 26 Aug 2026, classifier-gated autonomy) · https://claude.com/resources/articles/cowork-chrome-side-panel (12 Aug 2026) · https://support.claude.com/en/articles/12012173-get-started-with-claude-in-chrome · https://support.claude.com/en/articles/13065128-claude-in-chrome-admin-controls (allow/blocklists).
- https://blog.google/products-and-platforms/products/chrome/gemini-3-auto-browse/ (28 Jan 2026) · https://support.google.com/gemini/answer/16821166 (what it attempts) · https://blog.google/intl/en-in/products/bringing-gemini-in-chrome-with-auto-browse-to-india/ (7 Oct 2026) · https://blog.google/products-and-platforms/products/chrome/gemini-in-chrome-android-auto-browse/ · https://arstechnica.com/google/2026/01/google-begins-rolling-out-chromes-auto-browse-ai-agent-today/ (own agent tabs; Mariner lineage).
- https://press.opera.com/2025/09/30/opera-neon-ai-agentic-browser-release/ · https://investor.opera.com/news-releases/news-release-details/browse-your-own-ai-inside-opera-neon/ (MCP Connector, 31 Mar 2026) · https://blogs.opera.com/news/2026/08/your-ai-agents-can-use-opera-neon-free-of-charge/ (free agent connection, "token compression", 14 Aug 2026).
- https://www.diabrowser.com/changelog (Nov 2026, no agent) · https://piunikaweb.com/2026/08/11/dia-agentic-browsing-coming-fall/ · https://www.atlassian.com/blog/announcements/atlassian-acquires-the-browser-company (4 Sep 2025).
- https://www.genspark.ai/browser/ · https://help.manus.im/en/articles/17190150-what-is-new-in-manus-2-0 (Manus 2.0, 1 Oct 2026).

**Independent hands-on testing**
- https://benchtested.app/apps/comet/ · https://benchtested.app/apps/genspark/ · https://benchtested.app/apps/strawberry/ · https://benchtested.app/apps/dia/ — the same 8-task script on a clean Windows 11 VM, one run per task, Free plans (Oct–Nov 2026); https://benchtested.app/ for the method.
- https://www.dreamhost.com/blog/ai-web-browser/ — five browsers, one Amazon workflow (Jan 2026).
- https://www.theverge.com/tech/801899/opera-neon-ai-browser-trial-run · https://www.digitaltrends.com/computing/i-tried-a-operas-ai-browser-that-can-shop-book-and-even-apply-for-jobs-for-you-and-its-not-worth-it-just-yet/ — Neon hands-on.
- https://arstechnica.com/features/2025/10/we-let-openais-agent-mode-surf-the-web-for-us-heres-what-happened/ — Atlas agent mode scoring, Oct 2025.
- https://me.pcmag.com/en/ai/33159/i-put-microsofts-ai-browser-to-the-test-heres-what-actually-works — Edge Actions/Journeys, Oct 2025.
- https://wetheflywheel.com/en/radar/fellou-review/ — Fellou plan editing and CAPTCHA failure, 3 Nov 2026.

**Benchmarks, cost and long-horizon evidence**
- https://www.ajayk.sh/blog/browser-agents-computer-use-2026/ — secondary analysis citing primary sources; OSWorld-Verified table, OSWorld 2.0 figures, shutdown dates, injection history (5 Oct 2026).
- https://osworld-v2.xlang.ai/ · https://arxiv.org/abs/2606.29537 — OSWorld 2.0: 108 workflows, 20.6% completion, 244K tokens/task.
- https://browser-use.com/posts/odysseys2-long-horizon-web-agent-benchmark — 47/100 (27 Oct 2026).
- https://research.kay.ai/blog/building-browser-agents-that-finish-long-horizon-work/ — >2h, ~900 tool calls (10 Aug 2026).
- https://extrapolator.ai/2026/10/09/polar-agentic-browser-executes-multi-hour-autonomous-web-tasks/ — Polar's 15+ hour claim, vendor (9 Oct 2026).
- https://o-mega.ai/articles/top-10-browser-use-agents-full-review-2026 — per-task cost figures, infra pricing (2026).

**Security**
- https://claude.com/blog/claude-for-chrome — 23.6% → 11.2%, browser-specific 35.7% → 0 (Aug 2025); https://www.anthropic.com/research/prompt-injection-defenses (Nov 2025).
- https://venturebeat.com/security/anthropic-browser-agent-hijacked-31-percent-before-safeguards-engaged — 31.5% figure, secondary (1 Jun 2026).
- https://brave.com/blog/comet-prompt-injection/ · https://brave.com/blog/unseeable-prompt-injections/ — Comet exfiltration demos (Aug/Oct 2025).
- https://blog.trailofbits.com/2026/02/20/using-threat-modeling-and-prompt-injection-to-audit-comet/ — four techniques (20 Feb 2026).
- https://www.bleepingcomputer.com/news/security/new-bioshocking-attack-manipulates-ai-browser-into-data-theft/ — BioShocking across six browsers (30 Jun 2026).
- https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/ · https://ai.meta.com/blog/practical-ai-agent-security/ · https://developers.openai.com/api/docs/guides/tools-computer-use — lethal trifecta, Rule of Two, "treat screen content as untrusted".
