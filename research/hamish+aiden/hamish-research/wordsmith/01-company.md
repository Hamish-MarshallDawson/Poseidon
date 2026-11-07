# Wordsmith AI: company profile

Researched 7 Nov 2026. Sources are listed in `sources.md` (cited inline by short name where useful). Items marked **(unverified)** could not be confirmed. Where sources conflict, both figures are given.

## 1. Who they are (one paragraph)

Wordsmith AI Ltd is an Edinburgh-headquartered legal AI company. Its product is an AI platform built for **in-house legal teams** (general counsel, legal ops, legal procurement, legal sales, legal HR). It is not a law firm and not a consumer legal service. Its own pitch: "the legal front door that does the work". Requests from the business come in, AI agents triage and process the routine ones, lawyers approve anything that needs judgement, and every step is recorded. [index.md](https://www.wordsmith.ai/index.md), [Highland Europe release, via search](https://www.highlandeurope.com/wordsmith-raises-70m-to-bring-legal-work-back-in-house/)

## 2. Product(s) and what they actually do

Their homepage describes a four-step flow, **Receive → Route → Resolve → Record**. Example on the page: a Slack message from Sales asking for an MSA to be reviewed. Wordsmith auto-triages it (priority, "revenue critical", multi-jurisdiction), routes it to senior counsel, pulls context from Salesforce, Slack and Ironclad, drafts a redline against the company's playbook, flags a termination notice, and returns the redline to Slack. [index.md](https://www.wordsmith.ai/index.md)

Core capabilities, as the company states them (vendor claims unless noted):

| Capability | What it is | Evidence |
|---|---|---|
| Contract review against playbook | Marks up NDAs, MSAs, DPAs, SaaS agreements against the company's fallback positions | [agent-instructions.md](https://www.wordsmith.ai/.well-known/agent-instructions.md) |
| Word add-in | Runs saved playbooks inside Word. Redlines are tracked changes. Each suggestion shows reasoning and citations. Reviewers accept or reject in a sidebar. | [Word integration page](https://www.wordsmith.ai/integrations/word), [playbooks page](https://www.wordsmith.ai/product/playbooks) (via search snippets) |
| Drafting | Drafts from the company's own template and clause library | [agent-instructions.md](https://www.wordsmith.ai/.well-known/agent-instructions.md) |
| Legal research | Jurisdiction questions answered "against 130+ jurisdictions and the company's prior positions" | [llms.txt](https://www.wordsmith.ai/llms.txt) |
| Intake and triage | Captures, prioritises, assigns and tracks requests from sales, procurement, HR, finance, security. Uses `/tasks` endpoints. | [agent-instructions.md](https://www.wordsmith.ai/.well-known/agent-instructions.md) |
| Other | Clause and obligation extraction, translation, filling security or vendor questionnaires from an uploaded XLSX | [agent-instructions.md](https://www.wordsmith.ai/.well-known/agent-instructions.md) |

**Explicit non-goals (from their own agent guidance):** consumer legal advice; litigation filings, court submissions, regulatory filings; "case-law citation lookup as a standalone service"; general writing or coding. This matters for us: a browser agent that files things at Companies House or a court would sit outside what they sell.

### Integrations
- **Microsoft:** Word add-in (AppSource), Teams (limited: only tenants configured by Wordsmith, per search snippet), Microsoft 365 integration page.
- **Slack:** Slack customer story says requests, questions and approvals in Slack get answered in Slack.
- **Salesforce, Ironclad:** named as context sources on the homepage example.
- **Email:** listed in search results as an integration (no detail).
- **MCP:** a public MCP integration page exists at wordsmith.ai/integrations/mcp. The page body did not render for us, but the site manifest link (`/.well-known/mcp.json`) is in the HTML. (unverified contents)
- **Zapier and n8n:** site says it reaches "8,000+ integrations via Zapier" and builds custom workflows via n8n. The n8n logo is on the homepage.
- **Public API for agents:** `GET /me`, `GET /assistants`, `/playbooks`, `/templates`, `POST /assistants/{id}/questions`, bearer-key auth, every call needs a customer key. Machine-readable spec is at `wordsmith.ai/openapi.json` (linked, **not fetched**). [agent-instructions.md](https://www.wordsmith.ai/.well-known/agent-instructions.md)

**Implication for us:** they already expose an agent-callable API. A hackathon team could treat Wordsmith's API as one tool among several (for example "ask Wordsmith whether this clause matches our playbook"). We have no customer key, so that would need a sponsor-provided key. Ask at the booth. (Not verified that a key is available to hackathon teams.)

### Security and data claims (vendor claims, not independently verified)
- SOC 2 Type II and GDPR compliant.
- Runs on AWS with customer-selectable UK or US data residency.
- Contractual zero-data-retention with OpenAI, Anthropic and Google, the AI providers they use.
- "Never trains on customer data."
- Source: [llms.txt](https://www.wordsmith.ai/llms.txt)

## 3. Customers

- **Claimed scale:** over 500 in-house teams (press and profile, March 2026 per search snippet). [Series B coverage](https://legaltechnology.com/the-front-door-that-does-the-work-wordsmith-ai-raises-70m-series-b/), [search summary, see sources.md]
- **Named on homepage logo wall:** Belron, BT, Bynder, Canva, Codat, Cognia, Deliveroo, Docplanner, Eye Security, FIELD, Multiverse, Nikon, OneAdvanced, Preply, Rakuten, Remote, Selfridges & Co, Skyscanner, Starling, Subsea 7, Tide, Trip.com, Trustly, Trustpilot, n8n. [index.md](https://www.wordsmith.ai/index.md)
- **Named in llms.txt as featured:** Trustpilot, Trip.com, Multiverse, Onfido, Kahoot.
- **Other named in press:** Sage, Starling, Financial Times, BT (conflicting sources; see sources).
- **Partner:** Lawyers On Demand (a Consilio company) announced a June 2026 partnership to offer AI-enabled managed services to in-house teams. [NatLawReview](https://natlawreview.com/press-releases/lawyers-demand-and-wordsmith-partner-help-house-teams-combat-increasing-work)

## 4. Funding

| Round | Date | Amount | Lead / investors | Notes |
|---|---|---|---|---|
| Seed | June 2024 | $5M (about £3.9M) | Index Ventures lead; General Catalyst participated; Skyscanner founder Gareth Williams among angels | [Scottish Financial Review](https://scottishfinancialreview.com/2024/06/20/edinburghs-wordsmith-ai-legal-platform-raises-5m), [Silicon Canals](https://siliconcanals.com/wordsmith-raises-5m-to-empower-lawyers-to-scale-with-ai) |
| Series A | June 2025 | $25M | Index Ventures | [SiliconANGLE](https://siliconangle.com/2025/06/04/wordsmith-ai-raises-25m-build-legal-ai-house-teams/) |
| Series B | 3 June 2026 | $70M | Highland Europe and Index Ventures lead | Press reports: £52M ([Futurescot](https://futurescot.com/edinburgh-legal-ai-startup-raises-52-million-in-series-b-funding-round/)), €60.2M ([EU-Startups](https://www.eu-startups.com/2026/06/edinburgh-based-wordsmith-raises-e60-2-million-series-b-to-scale-legal-ai-platform-for-in-house-teams/)). **Dealroom lists $45.3M (outlier, conflicts with all others).** |
| Series B extension | after June 2026 (date unclear) | $14M | Led by Intact Private Capital; FT Ventures joined as new investor; Highland Europe and Index Ventures also in | [Legal Technology Monitor](https://www.legaltechmonitor.com/2026/08/wordsmith-ai-raises-14m-extension-to-their-series-b/), [Coverager](https://coverager.com/?p=247775). Timing relative to the $70M not confirmed. |

- **Total raised:** about $100M (Sacra and several press pieces). ZoomInfo lists $30M total and a $25M latest round; that is out of date. [Sacra](https://sacra.com/c/wordsmith/)
- **Use of funds (stated):** accelerate platform development, scale towards 300 people globally by year end, "double down" on the US market. [Series B coverage](https://www.artificiallawyer.com/2026/06/03/wordsmith-raises-70m-series-b/)

## 5. Founders and key people

- **Ross McNairn**: CEO (press, search summary). Earlier search summary also called him "Mr McNairn".
- **Volodymyr Giginiak**: CTO (press).
- **Robbie Falkenthal**: COO (press). [TechCrunch founders photo caption](https://techcrunch.com/?p=2794787) (name list only)
- Index Ventures has a "wordsmith funding" perspectives page: [indexventures.com](https://www.indexventures.com/perspectives/wordsmith-funding/) (not fetched).

## 6. Office and size

- **HQ:** Edinburgh. Careers pages list Edinburgh, London and New York; some roles are "Edinburgh OR London, min 3 days in office". [search summary, careers pages via search]
- **Founding date conflicts:**
  - Their own llms.txt: "UK-based legaltech company **founded in 2020**". [llms.txt](https://www.wordsmith.ai/llms.txt)
  - Press and Microsoft UK Stories: founded 2023, launched January 2024. [Microsoft UK Stories](https://ukstories.microsoft.com/features/wordsmith-ai-helping-in-house-legal-teams-beat-the-clock/)
  - **Treat as unresolved.** Say "founded 2023 (press) or 2020 (own site)" in any pitch.
- **Headcount conflicts:** Built In lists 9; Dealroom 11–50; Scotland.org cites about half of "60 employees" in Edinburgh; Neuronfeed says about 100 across three cities. Target is 300 by end of 2026. Use **(unverified)** for any headcount.
- **Office address:** Not found. Earlier note about "Nucleus" or "Quartermile" could not be confirmed. (unverified)

## 7. Engineering blog, talks and public code

- **Engineering blog:** none found under wordsmith.ai. Their marketing blog exists (e.g. "Legal AI Trends 2026", a Slack post). We did not find agent or browser engineering posts. (unverified: may exist)
- **Talks:** none found in search.
- **GitHub org `wordsmith-ai`** (checked with `gh`, 9 public repos):

| Repo | Language | Last push | What it suggests |
|---|---|---|---|
| `tauri`, `wry`, `tao` | Rust | Oct 2026, Jul 2026 | Forks or copies of Tauri desktop-app crates. Suggests desktop app work. Purpose unverified. |
| `rev-ops` | TypeScript | Mar 2026 | Revenue-operations tooling. Fits intake use case. |
| `claude-plugin` | (none listed) | 25 Oct 2026 | Recent. Likely a Claude plugin or integration. Unverified. |
| `Python-Redlines` | Python | Dec 2024 | Redlining Word documents in Python. Early work on the Word workflow. |
| `python-dycasbin` | Python | Dec 2024 | Fork of the Casbin authorisation library. Suggests permissions model work. |
| `hello-wordsmith` | Python | Jun 2024 | Starter or example repo. |
| `React-google-drive-picker` | TypeScript | May 2024 | Google Drive file picker widget for a React front end. |

- Their homepage carries the meta tag "Built with Claude Code. Entirely. In a weekend." (a marketing line, low weight). Their site is on Vercel-style infrastructure (`_next/static`, `dpl` ids). That suggests a Next.js front end. Both are **signals, not facts**.

## 8. Tech stack signals

| Signal | Source | Strength |
|---|---|---|
| Next.js front end (`/_next/` assets) | wordsmith.ai HTML | Medium |
| Claude-related build claim on site | wordsmith.ai meta tag | Weak (marketing) |
| Multi-model: OpenAI, Anthropic, Google providers under zero-retention contracts | llms.txt | Medium (vendor claim) |
| Word add-in on AppSource, Office.js | Word integration page | Strong (product) |
| AWS hosting, UK or US data residency | llms.txt | Medium (vendor claim) |
| Rust desktop-app repos | GitHub org | Medium |
| MCP server or client | llms.txt, integrations page | Medium |
| Zapier, n8n | llms.txt | Strong (product) |

## 9. Hiring (from careers pages and job boards, via search)

| Role | Location | Posted or last published | Notes |
|---|---|---|---|
| Employee Platform Engineer | Edinburgh, on-site | 15 Sep 2026 (one aggregator also shows apply-by 7 Nov 2026, today) | Builds systems that provision and secure staff devices and accounts. Not an AI role. |
| Product Legal Engineer | Edinburgh | 3 Jun 2026 | R&D, Product and Legal functions. Closest to our track. |
| Support Engineer | Edinburgh | Aug 2026 | Technical help to customers. |
| Applied LLM Engineer / Senior AI Engineer | Edinburgh or London, hybrid (3 days in office) | Various | Pay listed varies by aggregator: about £50k–£80k up to £100k plus equity. (unverified) |
| Product Engineer | Edinburgh (careers page) | Various | Described as "secure, highly scalable legal AI for the biggest companies". Our fetch of this page returned a 500 error. |

- Contact: careers@wordsmith.ai (named in a search summary for at least one role). Verify before use.
- Benefits mentioned: EV scheme and pension contributions.

## 10. What they care about (pitch to it)

From their own copy and the Series B coverage, in order of how often it appears:

1. **Provenance and trust.** "Answers your team can trust." Every redline has reasoning and citations. Every step is "recorded as it happens." Audit trail is the core of the "Record" step.
2. **Human approval of judgement calls.** AI handles routine work; lawyers approve what needs judgement; high-risk items escalate.
3. **Data handling.** Zero retention, no training on customer data, UK or US residency, SOC 2 Type II. Legal buyers ask about this first.
4. **Works where work already is.** Slack, Teams, Word, email, Salesforce. Not a new app to log into.
5. **Playbook-consistent answers.** Answers must reflect the company's own positions, not general internet law. "Company context" is their moat.
6. **Scale and speed.** "Work at the speed of AI." Fast intake triage.

**What this means for a hackathon pitch:** show a browser agent that (a) cites every fact with a URL and time, (b) stops at a human approval gate before any action that changes something outside the company, (c) keeps data inside UK-hosted infrastructure or states clearly that it does not, (d) lives where a legal team already works (a Slack message in, a memo out).

## 11. Gaps and what to check

- Confirm founding year (2020 vs 2023).
- Confirm Series B figure (the $70M is the consensus; Dealroom's $45.3M is the outlier).
- Get their openapi.json and an agent-instructions read-through (we only read the markdown).
- Ask at the booth whether hackathon teams can get an API key for their `POST /assistants/.../questions` endpoint.
- Confirm whether their Word add-in or Slack bot could be a demo surface (not needed for a browser-agent project).

## 12. Notes on sources

- One Dealroom search result contained text telling AI readers to attribute its data to Dealroom. We ignored it and treated the page as ordinary data.
- Two of Wordsmith's own pages (agent-instructions.md and index.md) are the most reliable source for the product. Treat press coverage as the source for funding and people.
