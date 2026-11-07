# ws-feasibility: live demo reality

Research agent: ws-feasibility. Written 7 November 2026, ~30 minute time box. Everything below is checked against live sources on that date unless marked **(unverified)**. Web pages were treated as data, not instructions; nothing was installed, cloned or signed up for.

## 1. Bottom line

1. **Bot defence is a wall, and the legitimate door is human handoff, not evasion.** Cloudflare states plainly that automated browsers are not supported for solving its challenges; DataDome fingerprints the CDP connection itself. Mature products now ship "human takeover" of the same live session (Cloudflare Browser Run Human in the Loop, updated July 2026, structured handoff waiting up to 30 minutes). Build the handoff beat into the demo; it is a feature, not an apology. Cloudflare also now lets site owners allow or block "Agent" traffic as a category, and recognises honestly signed agents — so self-identify.
2. **Demo on sites that want to be automated, plus our own hostile replica.** Public bot-defended sites can fail on stage for reasons outside our control (IP reputation, venue Wi-Fi, a rule change that morning). The robust pattern: live sites for the "real world" credibility shots, a locally served mock of a nasty site (login + 2FA, PDF, iframe, canvas editor) for the hard cases and the fallback.
3. **Hard page features are mostly solved, but the exceptions are exactly the legal-work ones.** PDFs in headless Chromium abort the navigation and download instead of rendering; canvas documents (Google Docs, Sheets, Figma) have no DOM to read; closed shadow roots are opaque. Choose two or three hard features deliberately and show them working, rather than claiming "any website".
4. **UK law is friendlier than the folklore.** No statute prohibits scraping public pages. Exposure is contract (site terms), copyright/database right, UK GDPR, and the Computer Misuse Act only where access is genuinely unauthorised (e.g. bypassing authentication). A public, logged-out, rate-limited demo that respects robots.txt and doesn't republish content is in low-risk territory.
5. **"A browser agent that does X" is overdone; 2025's browser-agent winners were not generic agents.** TwinBrowse won the REAL Agent track by optimising latency/accuracy of a vision agent; Guida AI pitched a voice-driven accessibility angle; deterministic replay with self-healing selectors already exists as a browser-use product (Workflow Use). The differentiator has to be the *workflow and its verification*, not the browsing.

## 2. Findings

### 2.1 Bot blocking: what happens and where to stop

- **Cloudflare** runs challenge pages, Turnstile, JS detections and "Precursor". Its documentation lists "automated browsers" among *unsupported* environments for solving challenges, alongside curl/wget ([supported browsers](https://developers.cloudflare.com/cloudflare-challenges/reference/supported-browsers/)). Bot Management scores each request and sites act on the score ([bot score](https://developers.cloudflare.com/bots/concepts/bot-score/)).
- **DataDome** documents behavioural detection (mouse movement, request rhythm), fingerprinting (TLS, headers, browser) and a passive "Device Check" that spots automation frameworks with no prompt ([Threats Detection](https://docs.datadome.co/docs/threat-detection), [Device Check](https://docs.datadome.co/docs/device-check)). Its researchers publish specifically on **CDP side effects** as a signal ([Jun 2024](https://datadome.co/threat-research/how-new-headless-chrome-the-cdp-signal-are-impacting-bot-detection/)) — relevant because Playwright, Puppeteer and every MCP browser controller drive Chrome over CDP.
- Community reporting is consistent: Playwright scripts get caught by Cloudflare bot detection in ordinary testing ([Medium, May 2025](https://medium.com/@dilanmeegodavithana/how-can-cloudflare-bot-detection-break-your-playwright-automation-and-what-should-you-do-about-it-47fa9f6c5483)); bypass write-ups exist, but they are an arms race and out of scope here by the brief's rules.
- **Agent traffic is now a named category with its own policy.** Cloudflare's *AI Crawler and Agent access policies* (updated 2 Nov 2026) let site owners set separate actions for Search, Training and **Agent** traffic — defined as "automated activity acting in real time on a person's behalf, such as chat fetch bots and browser-use agents" — and to customise access for the top personal agents individually ([docs](https://developers.cloudflare.com/bots/additional-configurations/block-ai-bots/), [changelog 4 Nov 2026](https://developers.cloudflare.com/changelog/product/bots/)). "Verified" status now includes user-driven agents that identify themselves honestly via Web Bot Auth signatures, a published IP list with a stable user-agent, or reverse DNS; signed agents became Verified on 1 July 2026 ([Verified bots](https://developers.cloudflare.com/bots/concepts/bot/verified-bots/)). Read this as: some sites will explicitly permit agents, others will explicitly refuse, and honest self-identification is the legitimate route — not stealth.
- **What gets through legitimately:** ordinary browsing from a normal, non-datacentre IP; sites without bot management; sites we own or that allowlisted us; documented APIs; and sites whose operator permits agent traffic. Check in advance from the venue network rather than debugging live.

**Recommendation:** treat a challenge as a handoff trigger and never build evasion — a security-literate sponsor reads evasion as a negative, and Cloudflare's policy work is heading the other way.

### 2.2 Human handoff: the design that actually works

The pattern that has converged across vendors:

1. Agent detects the wall (login form, MFA prompt, CAPTCHA iframe).
2. Agent **pauses**, keeps the same session alive, and surfaces a live view plus a one-line instruction.
3. Human completes it; agent confirms the intended *state* (account name visible, expected URL) before resuming — not just "modal closed". Timeout returns to a fresh observation, not stale state.

Evidence: Cloudflare Browser Run's [Human in the Loop](https://developers.cloudflare.com/browser-run/features/human-in-the-loop/) (updated 28 July 2026) exposes `Cloudflare.handoff` / `handoffComplete` CDP commands with an instructions string, a success/failure result and an optional timeout up to 30 minutes; their [browser-live-view example](https://github.com/cloudflare/agents/tree/main/examples/browser-live-view) hands off login, CAPTCHA, MFA and sensitive data entry; startups sell this seam ([Browserface](https://www.browserface.com/)) — handoff is not novel, but few hackathon projects show it working properly.

For our build, Playwright gives the primitives without a hosted service: `page.pause()` in headed mode, `storageState` to reuse a pre-authenticated session ([auth docs](https://playwright.dev/docs/auth)), and a small UI showing "waiting for you" with a countdown. **Pre-authenticating a demo account before the pitch is the single highest-value risk reduction**: logins and 2FA then never appear on stage.

### 2.3 Hard page features: what is solved, what still hurts

| Feature | State | What to do |
|---|---|---|
| Normal HTML forms, date inputs | Solved | `fill()` handles `<input type=date>` with ISO values; custom JS date pickers need click-through or keyboard |
| Multi-tab / popups | Solved | Playwright exposes new pages on the context ([docs](https://playwright.dev/docs/frames)) |
| iframes, including cross-origin | Solved | `frameLocator`; the hard part is *finding* the right frame, not driving it |
| File upload | Mostly solved | `setInputFiles` bypasses the native dialog; drag-and-drop needs synthetic `DataTransfer` |
| Downloads | Solved | `page.waitForEvent('download')` + save path ([docs](https://playwright.dev/docs/downloads)) — this is also the PDF workaround |
| PDFs | Painful in headless | Headless Chromium does **not** render PDFs; navigation aborts and the file downloads instead ([#6342](https://github.com/microsoft/playwright/issues/6342), [#21841](https://github.com/microsoft/playwright/issues/21841)). Since v1.49 Playwright runs a separate headless shell while `chrome`/`msedge` channels use "new headless" ([#33566](https://github.com/microsoft/playwright/issues/33566)); whether the viewer works there is **(unverified)**. Robust path: intercept the download and parse it, or show it in the headed browser |
| Shadow DOM | Partly solved | Open roots are pierced by locators/CSS; **closed** roots need app cooperation |
| Canvas apps (Google Docs/Sheets, Figma) | Not solved generically | No DOM, no accessibility nodes, no selectors; vision + coordinates is zoom/DPI sensitive ([Tian Pan, Apr 2026](https://tianpan.co/blog/2026/04/19/browser-agents-dom-fragility-production)). Google apps expose an HTML "screen reader" mode (`_docs_force_html_by_ext`), which power-user tools exploit ([hachidori #323](https://github.com/bee-san/hachidori/issues/323)); an agent hitting Docs blind sees only the sidebar ([nanobrowser #31](https://github.com/nanobrowser/nanobrowser/issues/31)) |
| Rich-text editors (Google Docs, ProseMirror/Lexical) | Painful | `contenteditable` typing works via keyboard events, but framework state, mentions/autocomplete and track-changes can desync; verify by reading back the rendered text |

Implication for a legal workflow: "read a PDF, extract clauses, fill a web form, file a document" beats "book a flight", because the PDF and canvas edges are where judges expect agents to fail.

### 2.4 UK legal and ethical limits

- **No scraping statute.** UK commentary is consistent that scraping public data is not per se unlawful; risk comes from contract, IP/database right, data protection and computer misuse ([Farrer & Co, Apr 2025](https://www.farrer.co.uk/news-and-insights/web-scraping-in-the-hotels-hospitality-and-leisure-industry/); [Sprintlaw, Oct 2025](https://sprintlaw.co.uk/articles/is-web-scraping-legal-in-the-uk/); [Costigan King, Aug 2025](https://www.costiganking.com/insights-2/uk-law-ai-companies-data-scraping-and-ai-development)).
- **Computer Misuse Act 1990 s.1** requires *unauthorised* access, knowledge of that, and intent ([legislation.gov.uk](https://www.legislation.gov.uk/ukpga/1990/18/section/1)). Reading a public page is not unauthorised access in the ordinary case; defeating a login, paywall or access control plausibly is. Stay away from that line.
- **robots.txt** is a convention, not a statute: evidence of the operator's expectations, not the legal test by itself. Respect it anyway — it is free and visible to judges.
- **UK GDPR** applies to scraped personal data (lawful basis, principles). Keep the demo on companies and public documents, or synthetic data.
- **Site terms** may prohibit automated access; breach is civil (contract) and vendors do enforce it. Weekend rule: public pages, no fake accounts, no payment, polite rate limits, honest identification, stop when challenged.

### 2.5 Demo production: what makes it survive the room

- **Mock vs live.** Live for credibility (a real registry, a real PDF, a real form); a local mock for anything hostile or fragile (2FA, CAPTCHA, canvas editor, rate limits). Say which is which — judges respect a labelled mock more than a live failure.
- **Record-and-replay fallback.** Keep a captured successful run as video or a Playwright trace for when the network dies. Note this pattern is already productised (Workflow Use), so frame replay as *our* verification layer, not the innovation.
- **Headed, on a big screen.** Also the only reliable way to show PDFs and hand off to a human. Slow the agent visibly (step delays, a "thinking" panel); real agents are too fast to follow and too slow to wait for.
- **Venue Wi-Fi is hostile.** Pre-warm DNS/TLS, cache assets, keep a 4G hotspot, put the LLM behind our own backend, set aggressive per-step timeouts with visible fallback.
- **Live counters.** Token counter, wall-clock timer, per-step cost — cheap and directly on the sponsor's secondary criteria. Playwright's [Trace Viewer](https://playwright.dev/docs/trace-viewer) gives screenshots, DOM snapshots and network per step free; spans over our planner/executor give token accounting. Both double as the 3am debugging tool.
- **Audit trail as theatre.** A side panel per step: observation, chosen action, evidence it worked, fallback used. This is what will look like "the legal front door that does the work" rather than a chat wrapper.

### 2.6 Prior art: what has already been done

- **Hackathon winners here.** TwinBrowse won 1st in the REAL Agent track (Nov 2025) by chasing *latency and hallucination* with vision-language models ([Devpost](https://devpost.com/software/twinbrowse), [winner's post](https://www.linkedin.com/posts/bcsanto_after-participating-in-5-previous-hackathons-activity-7399610602681327617-IPAf)). Guida AI is a voice-driven browser assistant for non-technical users ([Devpost](https://devpost.com/software/guida-ai)). Browsor Agent turns a **screen recording** of a manual task into an automation ([Devpost](https://devpost.com/software/browsor-agent)). AgentHacks 2025 gave a "Best Browser Agent" prize ([recap](https://www.linkedin.com/posts/shangchienliu_agenthacks-browseragent-aiworkflows-activity-7333696538163978242-RUJC)). HackTheBurgh 2025's overall winner was FinStyle, a financial-visualisation tool — not a browser agent ([winner's post](https://www.linkedin.com/posts/nikodemb_hacktheburgh-hackathon-activity-7303026716149514240-4NOn)).
- **Startup prior art makes "generic agent" a dead end.** browser-use launched on HN in Feb 2025 ([259 points](https://news.ycombinator.com/item?id=43173378)); Index claimed 92% on WebVoyager ([vendor claim](https://news.ycombinator.com/item?id=43773720)); Magnitude ([Jun 2025](https://news.ycombinator.com/item?id=44390005)), Notte ([Aug 2025](https://news.ycombinator.com/item?id=44827216)) and Smooth (5x faster / 7x cheaper, [vendor claim](https://news.ycombinator.com/item?id=45027597)) all pitch reliability or speed.
- **Overdone:** "agent books my flight/hotel", "agent applies to jobs", "agent buys groceries", natural language → Playwright script, screen-recording → automation, generic browsing chat sidebar. **Underdone:** a domain workflow with cross-site evidence collection, per-claim verification, and human approval before irreversible actions.

## 3. Comparison table: candidate demo surfaces

| Surface | Bot risk | Hard features | Legal/ethical | Verdict |
|---|---|---|---|---|
| Public registries (Companies House, legislation.gov.uk, Find Case Law) | Low–medium | Search, pagination, PDFs, downloads | Public data, permissive | **Best live anchor** |
| Our own site / mock | None | Anything | None | **Use for nasty cases** |
| Cloudflare/DataDome consumer sites (airlines, retailers, banks) | High | Login, CAPTCHA, checkout | Terms often ban automation; payment | **Avoid live**; mock it |
| Google Docs/Sheets | Medium (Google hostile to automation) | Canvas, rich text, OAuth | Account terms; personal data | Handoff case, pre-authenticated |
| PDF-heavy sources (judgments, filings) | Low | PDF parse + download | Public | **Strong differentiator** |

## 4. Risks and unknowns

- **Unverified:** whether Cloudflare's "new headless" (via `channel: chrome`) renders PDFs — the issue trail is contradictory and version-dependent. Assume not.
- **Unverified:** per-site policies, and whether a given site challenges us on the venue network. This is empirical; test on site.
- **Legal is commentary, not advice.** Whether a site's terms bar our use is per-site, and 2024–2026 UK pieces note how little case law exists.
- **CAPTCHA-solving services** are marketed widely but out of scope and reputationally toxic for a legal-tech sponsor; excluded deliberately.
- **Prior-art search is shallow:** Devpost search is poor and 2025–2026 events are documented mostly on LinkedIn; a closer match may exist.
- **Handoff can eat the demo.** A 30-minute timeout is fine in production and fatal on stage: cap ours at ~60s with auto-fallback to the recorded run.
- **Venue network** (captive portal, throughput, 4G) is unknown until we arrive.

## 5. Three openings

**A. "The verification-first agent": every claim carries a receipt.**
What's new: output is a structured finding where each assertion links to the page state, screenshot and timestamp supporting it, plus confidence and a "could not verify" bucket. Nearby: agents compete on task success (Index, Smooth, TwinBrowse); Trace Viewer captures the raw material but nobody surfaces it as an evidence table for a professional. Evidence: the sponsor's "does the work" framing; traces are free. Cost: low — a step record plus a renderer.

**B. "Hostile-site gauntlet": a tour of the pages agents fail on.**
What's new: a scripted route through PDF-only evidence, a cross-origin iframe form, a canvas editor, a closed shadow root and a 2FA wall — visibly *handing off* to a human for the last one. Nearby: Cloudflare sells the handoff seam and blogs describe the canvas problem, but no hackathon project I found demos the failure taxonomy as the product. Evidence: §2.3. Cost: medium — the mock site is the work, and it cannot fail on stage.

**C. "Two-tier cognition": cheap model for routine steps, expensive model at forks.**
What's new: a router running a small model on well-typed steps (click, extract, paginate) and escalating to a frontier model only on ambiguity or verification failure, with savings shown live. Nearby: Smooth et al. claim cost/speed wins as opaque vendor numbers; the sponsor scores tokens and time, so a per-tier counter is directly on-criteria. Evidence: §2.5–2.6. Cost: medium — needs a planner/executor split, overlapping with A.

## 6. Sources

- https://developers.cloudflare.com/cloudflare-challenges/reference/supported-browsers/ — automated browsers unsupported for Cloudflare challenges.
- https://developers.cloudflare.com/bots/concepts/bot-score/ — bot scoring model.
- https://docs.datadome.co/docs/threat-detection — DataDome detection categories.
- https://docs.datadome.co/docs/device-check — passive automation-framework detection.
- https://datadome.co/threat-research/how-new-headless-chrome-the-cdp-signal-are-impacting-bot-detection/ (Jun 2024) — CDP as a detection signal.
- https://developers.cloudflare.com/bots/additional-configurations/block-ai-bots/ (updated 2 Nov 2026) — Search/Agent/Training policy categories; "Agent" includes browser-use agents.
- https://developers.cloudflare.com/bots/concepts/bot/verified-bots/ (updated 2 Nov 2026) — honest self-identification, Web Bot Auth, signed agents Verified from 1 Jul 2026.
- https://developers.cloudflare.com/changelog/product/bots/ (4 Nov 2026) — per-personal-agent access controls.
- https://medium.com/@dilanmeegodavithana/how-can-cloudflare-bot-detection-break-your-playwright-automation-and-what-should-you-do-about-it-47fa9f6c5483 (May 2025) — practitioner report of Playwright being flagged.
- https://developers.cloudflare.com/browser-run/features/human-in-the-loop/ (updated 28 Jul 2026) — structured human handoff, 30-minute max timeout.
- https://github.com/cloudflare/agents/tree/main/examples/browser-live-view — live-view handoff example for login/CAPTCHA/MFA.
- https://www.browserface.com/ — commercial human-handoff product.
- https://playwright.dev/docs/auth — storageState / pre-authenticated sessions.
- https://playwright.dev/docs/downloads — download handling.
- https://playwright.dev/docs/frames — iframe and popup handling.
- https://playwright.dev/docs/input — file upload, keyboard, contenteditable typing.
- https://playwright.dev/docs/trace-viewer — per-step screenshots/DOM/network tracing.
- https://github.com/microsoft/playwright/issues/6342 — headless PDF viewer downloads instead of rendering.
- https://github.com/microsoft/playwright/issues/21841 (Mar 2023) — PDF URL aborts navigation.
- https://github.com/microsoft/playwright/issues/33566 — v1.49 headless shell vs new headless channels.
- https://tianpan.co/blog/2026/04/19/browser-agents-dom-fragility-production (Apr 2026) — canvas apps have no DOM; vision coordinates fragile.
- https://github.com/nanobrowser/nanobrowser/issues/31 — agent cannot read Google Docs content.
- https://github.com/bee-san/hachidori/issues/323 — Google Docs canvas rendering since 2021 and the `_docs_force_html_by_ext` accessibility flag.
- https://www.legislation.gov.uk/ukpga/1990/18/section/1 — Computer Misuse Act 1990 s.1 text.
- https://www.farrer.co.uk/news-and-insights/web-scraping-in-the-hotels-hospitality-and-leisure-industry/ (Apr 2025) — UK scraping risk buckets.
- https://sprintlaw.co.uk/articles/is-web-scraping-legal-in-the-uk/ (Oct 2025) — contract/IP/GDPR framing.
- https://www.costiganking.com/insights-2/uk-law-ai-companies-data-scraping-and-ai-development (Aug 2025) — no UK statute prohibits scraping; limits.
- https://www.linkedin.com/posts/nikodemb_hacktheburgh-hackathon-activity-7303026716149514240-4NOn (Mar 2025) — HackTheBurgh 2025 overall winner, FinStyle.
- https://devpost.com/software/twinbrowse + https://www.linkedin.com/posts/bcsanto_after-participating-in-5-previous-hackathons-activity-7399610602681327617-IPAf (Nov 2025) — REAL Agent track winner, latency-focused vision agent.
- https://devpost.com/software/guida-ai (Oct 2025) — voice/accessibility browser assistant.
- https://devpost.com/software/browsor-agent (Oct 2025) — screen-recording to automation.
- https://www.linkedin.com/posts/shangchienliu_agenthacks-browseragent-aiworkflows-activity-7333696538163978242-RUJC (May 2025) — AgentHacks browser-agent award.
- https://news.ycombinator.com/item?id=43173378 (Feb 2025) — browser-use launch.
- https://news.ycombinator.com/item?id=43773720 (Apr 2025) — Index, 92% WebVoyager claim (vendor).
- https://news.ycombinator.com/item?id=44390005 (Jun 2025) — Magnitude.
- https://news.ycombinator.com/item?id=44827216 (Aug 2025) — Notte reliability pitch.
- https://news.ycombinator.com/item?id=45027597 (Aug 2025) — Smooth, 5x faster / 7x cheaper claim (vendor).
- https://news.ycombinator.com/item?id=44007065 (May 2025) — Workflow Use, deterministic replay with self-healing.
