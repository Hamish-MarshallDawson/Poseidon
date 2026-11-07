# ws-legal: legal workflows and Wordsmith

*Research agent ws-legal, 7 Nov 2026. Every claim is sourced in §6; anything unconfirmed is marked **(unverified)**.*

## 1. Bottom line

1. **Wordsmith already covers the document.** Contract review and redlining, drafting Blueprints (18 distinct live templates: Companies House AP01/TM01/AD01/AA01/PSC01/PSC02/MR01, ET3/COT3/settlement agreements/statutory pay forms, DPIA/TRA/LIA), intake, and "Research" with live integrations to Companies House, SEC EDGAR and OpenCorporates.
2. **It does not act on the outside world.** Their integrations are Slack, Teams, email, SharePoint, Google Drive, Word and contract-management systems. Nothing in their published product set files, submits, serves, registers or monitors a third-party website. That gap is the honest pitch: **Wordsmith drafts the filing; the browser files it and then proves the register changed.**
3. **Most UK legal sources have APIs — and two of the obvious ones are actively hostile.** Companies House (free key, 600 req/5 min), Find Case Law, legislation.gov.uk, UK Sanctions List (full XML), The Gazette and SEC EDGAR all have machine interfaces; I checked each today. A domain judge will discount "we browsed Companies House". Browser work is justified only where the API is gated, paid or absent: **Companies House WebFiling, the ICO fee-payer register, the FCA Register UI, offshore registries, vendor terms pages.** Meanwhile **BAILII** runs an **Anubis proof-of-work challenge against AI scrapers** (v1.25.0) and **`ipo.gov.uk` / `trademarks.ipo.gov.uk`** return a **Cloudflare managed challenge** to any scripted request. Both are off the table: not demo dependencies, and defeating them is exactly what a legal-track judge would mark down.
4. **The strongest legal workflows end in a state change with a public receipt** — a filing accepted, a register updated, a notice published. A judge can confirm that in one click, which is the hardest part of demoing a browser agent.
5. **Filing is browser-only for us, and the handoff is a feature.** Companies House has a REST "API Filing" service, but it is for enrolled software providers with test accounts and limited forms; WebFiling itself needs GOV.UK One Login, 2FA and a per-company authentication code. So: agent does everything up to the confirmation screen, **human enters the credential, agent resumes and verifies**. That is how legal teams would want it anyway.

## 2. Findings

### 2.1 What Wordsmith ships (product view only — another track covers background)

| Capability | Detail |
|---|---|
| Review | Playbook-aligned review, redlines, fallback positions, contextual review per deal; Word add-in |
| Drafting | 18 live Blueprints — corporate (AP01, TM01, AD01, AA01, PSC01, PSC02, MR01), employment (ET3, COT3, SMP1/SPP1/SSP1), data protection (DPIA, TRA, LIA) |
| Agents | Sales Contract, NDA, Procurement, Privacy, HR, Matter Triage; run from Slack/Teams/email; scheduled |
| Research | 130+ jurisdictions, "smart web search" over curated government/regulator sources; live Companies House / EDGAR / OpenCorporates |
| Audit | "Record every step… logged with timestamp and source" |
| Integrations | Slack, Teams, email, SharePoint, Google Drive, Word, CMS |

**The gap, precisely.** Wordsmith *verifies* against registries (check a director, check a filing) but stops at drafting and messaging. Not stated anywhere in its public material: submitting a filing, e-filing to a court, applying for a trade mark, searching a register with no API, monitoring a counterparty's website, handling a 2FA portal login. It also appears not to reconcile *what was drafted* against *what the register now says* — the step where this work actually goes wrong (wrong effective date, wrong officer name, rejected filing).

### 2.2 Where the competition sits

Harvey ships 500+ prebuilt agents and parallel execution with Word/PowerPoint/Excel output (May 2026). Legora, Spellbook/LegalOn and Luminance are conventionally placed alongside it on playbook review and negotiation, but **I did not verify their current product pages this wave (unverified)**. Nothing in the primary material I read sells "agent operates a government portal end to end". Adjacent but read-only: Scout (thesiad.ai/scout, £199/user/month, UK company due-diligence reports), Glasshouse (ownership tracing, property, regulatory, sanctions checks), Fasrad ("browses the pages that matter"). **Read-only evidence products. Nobody closes the loop to filing.** That is the space.

### 2.3 Nine candidate workflows

Each: user and pain → systems crossed → browser vs API → free/no-login → site rules → how a judge confirms it.

**W1. File a director change and prove it landed.** Company secretary at a 30-entity group; Wordsmith drafts the TM01, someone retypes it into WebFiling, nobody checks afterwards. Systems: instructions → drafted form → WebFiling → public register (officers, filing history) → The Gazette. **Browser** for filing (One Login + 2FA + auth code; API Filing is provider-enrolled only); **API** for verification (free key). Free; verification needs no login. No robots.txt on the public register (404) — use the API for reads. Judge: open the register, see the officer with the right date and the accepted filing. Caveat: needs a consented company or a mock.

**W2. New-supplier due diligence pack.** In-house counsel clearing a SaaS vendor; 45–90 minutes of tab-hopping, then a stale memo. Systems: Companies House (profile, PSC, charges, filings) → UK Sanctions List → ICO fee-payer register → FCA Register → the vendor's own subprocessor/security/terms pages → cited memo. **API** for CH, UKSL, Find Case Law; **browser** for the ICO form search, the FCA Register UI (its API is free but needs a developer key) and vendor pages (no API at all). Free. ico.org.uk allows all with `Crawl-delay: 6`; register.fca.org.uk `Allow: /`. Judge: pick any citation and open it.

**W3. Counterparty watch: litigation, insolvency, enforcement.** Commercial counsel tracking 20 key counterparties; you hear about a liquidation from a colleague. Systems: Find Case Law (Atom search confirmed working) → The Gazette (insolvency data feed confirmed) → FCA/ICO/CMA enforcement pages → cause lists. **API/feed** for the first two; **browser** for regulator press pages. Free. Find Case Law robots.txt **names GPTBot, ClaudeBot, PerplexityBot, anthropic-ai etc. as disallowed while allowing `User-agent: *`** — use the documented API and identify honestly. Gazette allows all, `Crawl-delay: 10`, disallows `/sign-in`. **BAILII excluded** (Anubis challenge). Judge: opens the judgment or notice.

**W4. Trade-mark clearance — demoted after testing.** Product counsel facing a £200-per-class decision on a hurried search. Systems: IPO search → Trade Marks Journal → EUIPO/USPTO → memo. **IPO has no public search API and blocks scripted clients at the edge:** `trademarks.ipo.gov.uk` and `www.ipo.gov.uk` both returned **HTTP 403, `cf-mitigated: challenge`, `server: cloudflare`** today even with a desktop UA. A headed browser may pass the managed challenge **(unverified — deliberately not tested)**, but do not stake a demo on it. Fallback: the Journal's official weekly XML data file. Judge: citations resolve. **Keep out of the demo spine**; it is a "we checked, here is why not" slide.

**W5. "Did the law under our contract change?"** Counsel in a regulated business doing quarterly manual statute and guidance review. Systems: legislation.gov.uk (REST, content negotiation, changes-to-legislation) → EUR-Lex → regulator policy pages. **Almost entirely API**; `Crawl-delay: 5` and `10` respectively. Free. Judge: point at the amending instrument. This is the **negative control** — it shows the team knows when not to use a browser.

**W6. Vendor terms and privacy-policy drift watch.** Privacy counsel; AI vendors silently rewrite subprocessor lists and training-data clauses, so contract reps stop being true. Systems: each vendor's `/terms`, `/privacy`, `/subprocessors`, trust centre, changelog. **Browser, uniquely** — no APIs, JS rendering, cookie banners, PDFs. Free, no login. Rules: per-site — a handful of pages at human pace is fine; check robots.txt before each domain and skip any that challenge. Judge: side-by-side clause diff with timestamps and archived snapshots. Most obviously *agentic* (many sites, unpredictable layouts, real recovery) with the lowest legal-risk exposure.

**W7. DSAR sweep across processors.** A DPO finding one person's data across a dozen processor portals, each with its own login and form. Systems: ICO register (is the processor registered?) → each DSAR portal → internal systems. Browser; **accounts required**, so human-handoff-heavy. Rules: portals are private services governed by their own terms — automate only with the account holder's consent, never with borrowed credentials. Judge: the response letter's citations. Weakest for a live demo (logins), useful as a "we know where the hard part is" line.

**W8. Contractor onboarding: right to work, sanctions, disqualification.** HR legal doing three checks on three websites by email. Systems: GOV.UK "prove your right to work" share-code service (browser, no employer login, needs the worker's code and DOB) → Companies House officer/disqualification search → UKSL. **Browser required** for the share-code service (no API, by design); APIs elsewhere. Free. gov.uk robots allows all but `/search/all*`. Judge: the statutory excuse *is* a dated, retained check — the evidence bundle is the legal artefact. Use synthetic identities.

**W9. Group and beneficial-ownership tracing.** KYC on a counterparty group; the UK layer is easy, Jersey/Guernsey/IoM/Delaware/Luxembourg are not. Systems: Companies House PSC API → Charity Commission register (robots allows all) → offshore registers. **Browser for the offshore layers**, which is why it is hard and unproductised. Partly paid. Rules: several offshore registers license access per document and forbid bulk extraction — read the terms per jurisdiction before touching them. Judge: walk the chain, confirm each entity exists. **Per-jurisdiction feasibility unverified.**

**Rejected on purpose.** Land Registry title checks (£3 per title — a paid step in a live demo) and court e-filing (CE-File account, court-specific permissions) are browser-justified but not demo-feasible tonight. The law-firm "review 400 contracts" workflow is out: Wordsmith already does it and it isn't browser work.

## 3. Comparison table

| # | Workflow | Browser forced? | Login / payment | Judge-verifiable | Legal bonus | Build risk |
|---|---|---|---|---|---|---|
| W1 | File director change + verify | **Yes** (WebFiling) | Login + 2FA + auth code | **Very high** — public register | High | Medium (handoff) |
| W2 | Supplier due diligence | Partly (ICO, FCA, vendor site) | None on demo path | High — citations resolve | High | Low |
| W3 | Litigation/insolvency watch | Partly (regulator pages) | None | High | High | Low–medium |
| W4 | Trade-mark clearance | Would be, but **blocked** | None to search | High | High | **Not viable** |
| W5 | Legislative change monitor | No — APIs | None | Very high | Medium | Very low |
| W6 | Vendor terms drift | **Yes, entirely** | None | Very high — visible diff | Medium | Low |
| W7 | DSAR sweep | Yes | Many logins | Medium | High | Very high |
| W8 | Contractor onboarding | **Yes** (share code) | None (worker's code) | Very high | High | Medium (personal data) |
| W9 | Ownership tracing | **Yes** (offshore) | Sometimes paid | High | Medium | High |

## 4. Risks and unknowns

- **Unverified:** which offshore registries offer free entity search versus pay-per-document — decides whether W9 is feasible.
- **Unverified:** whether Wordsmith already has a browser agent in private beta. Their public pages show none, but absence of marketing is not absence of product. One question to their engineers changes the pitch — ask it early.
- **Licence and terms risk.** Find Case Law's robots.txt names AI crawlers as disallowed and the Open Justice Licence governs reuse of judgment text; prefer the documented API and attribute. legislation.gov.uk is OGL; UKSL is published for reuse. Do not crawl what is disallowed, and say so in the write-up — a legal-track judge will check.
- **Bot filtering is aimed at us.** IPO: Cloudflare managed challenge on every scripted request. BAILII: Anubis proof-of-work against AI scrapers. Treat both as unavailable, not as obstacles to route around. For ws-feasibility, this is the biggest constraint on a "real UK legal sources" demo. I did not test a headed browser against them, because circumventing a challenge is not something we should build.
- **Filing needs a real credential.** A Companies House auth code is the equivalent of a director's signature: use a consented company or a mock, and never imply the agent can obtain credentials.
- **Personal data.** Officer, PSC and sanctions data are UK GDPR personal data; use synthetic or already-public figures and say so. The team's "real answer on privacy" requirement lands here.
- **Accuracy framing.** "Not found on the sanctions list" ≠ "not designated". Any output must state the search boundary and date, or it is a false negative with a lawyer's fingerprints on it.

## 5. Three openings

**O1 — The last mile: file it, then prove it changed.**
*New:* a closed loop from drafted legal document to accepted public filing to verified register state, with a signed evidence bundle (pre-state, submission receipt, post-state, timestamp). Nothing I found does the loop; Wordsmith drafts the form and its agents "send" email, but the portal step is human.
*Nearby:* Wordsmith Blueprints (drafting), WebFiling (the human's tab), Scout/Glasshouse (read-only reports), Harvey's 500 agents (document output).
*Evidence:* Wordsmith's Blueprint article lists Companies House forms as *drafting* only; Companies House's own specs show filing-by-API is for enrolled providers, so browser + handoff is the only general route.

**O2 — Contract obligations become scheduled browser checks.**
*New:* invert the direction. Extract *executable* obligations from the contract (notify within 5 business days, register the charge within 21 days, maintain insurance, sanctions reps, subprocessor notice) and turn each into a recurring check against the exact public source that would reveal a breach, with an evidence log.
*Nearby:* Wordsmith's scheduled agents and repositories; bank-focused compliance-monitoring vendors at bank prices; nothing aimed at the in-house team's own contract stack.
*Evidence:* Wordsmith markets scheduled agents and per-step audit logging but no external verification; the MR01 21-day deadline in their own Blueprint library is exactly the kind of deadline a monitor polices.

**O3 — Legal standard of proof as the browser-agent differentiator.**
*New:* the product is not the crawl, it is the *admissibility*. Every step emits URL, timestamp, content hash, extracted span, screenshot and a "what I could not verify" ledger; the agent refuses conclusions without a resolvable citation. Generalises well beyond law.
*Nearby:* Wordsmith claims this standard for its own outputs ("logged with timestamp and source… built to hold up to procurement, auditors and regulators"); general browser agents emit free-text traces, not evidence bundles.
*Evidence:* that products/agents claim, plus the sharp differences in what sources permit — Find Case Law bans named AI crawlers while offering a public API, BAILII runs proof-of-work, IPO blocks scripted clients, Gazette and legislation.gov.uk ask for crawl delays. Permission and provenance are a compliance requirement, not a nicety.

**If the team builds one thing:** W1+O1 as the demo spine (one visibly filed change, verified on the public register), with W6 or O3 as the breadth layer proving many-site robustness. W5 belongs in the pitch deck only, as evidence of judgement.

## 6. Sources

| URL | Recency | Supported |
|---|---|---|
| https://www.wordsmith.ai/products/agents | current 2026 | Agent types, channels, scheduled runs, audit-log claim, integration list |
| https://www.wordsmith.ai/products/research | current 2026 | Live Companies House / EDGAR / OpenCorporates; "smart web search"; 130+ jurisdictions |
| https://www.wordsmith.ai/articles/the-complete-wordsmith-blueprint-library-every-workflow-you-can-automate-today | 2 Dec 2025 | The 18 Blueprints, incl. AP01/TM01/MR01 — drafting only |
| https://www.wordsmith.ai/products/review | 2026 | Playbook review, redlines, contextual review |
| https://www.wordsmith.ai/blog/contextual-contract-review-ai | 14 Apr 2026 | Contextual review launch |
| https://www.wordsmith.ai/blog/wordsmith-ai-raises-70-million-series-b | 3 Jun 2026 | Series B; in-house-only positioning |
| https://legaltechnology.com/the-front-door-that-does-the-work-wordsmith-ai-raises-70m-series-b/ | 3 Jun 2026 | Independent confirmation of $70m Series B and positioning |
| https://www.harvey.ai/blog/agentic-platform-updates | 5 May 2026 | 500+ prebuilt agents, Agent Builder, document output |
| https://developer.company-information.service.gov.uk/developer-guidelines/ | current | 600 requests / 5 min |
| https://developer.company-information.service.gov.uk/authentication/ | current | Free API key, HTTP basic auth |
| https://developer-specs.company-information.service.gov.uk/manipulate-company-data-api-filing/guides/overview | current | API Filing is a separate service with limited forms |
| https://www.gov.uk/government/publications/technical-interface-specifications-for-companies-house-software/important-information-for-software-developers-read-first | current | Software filing needs a test account and supplier enrolment |
| https://www.gov.uk/guidance/company-authentication-codes-for-online-filing | current | Auth code is the equivalent of a signature |
| https://ewf.companieshouse.gov.uk/help/en/stdwf/faqHelp.html | current | WebFiling: One Login + 2FA + auth code |
| https://nationalarchives.github.io/ds-find-caselaw-docs/public | current | Find Case Law public API, Open Justice Licence |
| https://www.data.gov.uk/dataset/a2416481-271a-42b2-ace8-fc247dd251be/legislation-api | 24 Jun 2026 | legislation.gov.uk REST API, OGL |
| https://www.gov.uk/government/publications/the-uk-sanctions-list | 3 Nov 2026 | UKSL search service plus ODT/XML downloads |
| https://www.gov.uk/guidance/format-guide-for-the-uk-sanctions-list | 22 Dec 2025 | UKSL fields; OFSI consolidated list closed 28 Jan 2026 |
| https://trademarks.ipo.gov.uk/ipo-tmtext | current | IPO search is a form; no public API |
| https://www.ipo.gov.uk/tm3-servicesfees | current | £200 first class, £50 additional, £30 online discount |
| https://www.ipo.gov.uk/t-tmj.htm | current | Weekly Trade Marks Journal plus a large XML data file |
| https://thesiad.ai/scout | current | Read-only UK due-diligence product, £199/user/month |
| https://www.glasshouse.sh/platform/ai-agent | current | Read-only investigation agent |
| https://fasrad.com/agents/due-diligence-agent | current | "Browses the pages that matter" — read-only |
| https://www.complianceweek.com/wp-content/uploads/2026/01/gansurveyreport_478258.pdf | Jan 2026 | Due-diligence timelines remain long (vendor-sponsored survey) |
| Live HTTP/robots checks, 7 Nov 2026 | fetched 7 Nov 2026 | CH public register robots.txt 404; CH officers API 401 without key; Find Case Law robots.txt names AI crawlers, allows `*`; Find Case Law atom search 200; UKSL XML 200; Gazette insolvency data feed 200 and robots (crawl-delay 10, no `/sign-in`); legislation.gov.uk crawl-delay 5; EUR-Lex crawl-delay 10; register.fca.org.uk `Allow: /`; ico.org.uk crawl-delay 6; Charity Commission register robots allows all; gov.uk robots allows all but `/search/all*`; **BAILII Anubis v1.25.0 proof-of-work**; **IPO Cloudflare 403 `cf-mitigated: challenge`** |
