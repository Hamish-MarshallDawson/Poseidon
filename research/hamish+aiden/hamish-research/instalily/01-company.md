# InstaLILY AI: company brief

Researched 7 Nov 2026. Sources are listed in `sources.md`. Claims marked **(unverified)** could not be confirmed from a primary source. The company's own pages (press kit, about, news) are JavaScript-heavy and did not render when fetched, so most facts come from press coverage and job boards.

## Summary

- InstaLILY AI is a New York company that sells vertical AI "teammates" (InstaWorkers) and an AI engineer called **Lily**, aimed at industrial distribution and similar operations.
- It raised a **$60M Series B in July 2026**, led by Energize Capital, after a **$25M Series A in August 2025** led by Insight Partners. Total funding is reported as nearly $100M.
- Its pitch is **forward-deployed engineering**: engineers embed in a client's business, redesign one high-value workflow, and ship a system with measurable results.
- The company runs hackathons with Google DeepMind (SF and Toronto, 2026). These are the only public hackathon signals found. No public brief for an InstaLILY coding-agent challenge was found.

## Who they are

| Item | Finding | Confidence |
|---|---|---|
| Name | InstaLILY AI (also "InstaLILY") | High |
| Headquarters | New York. Addresses conflict: 455 Broadway (one profile) vs 433 Broadway (CB Insights). | High for city |
| Other offices | San Francisco, London, Toronto | Medium (company announcement, via press) |
| Founded | 2022 or 2023. Sources disagree. | Low |
| Founders | Amit Shah (Founder & CEO), Sumantro Das (Co-Founder & COO) | Medium (one profile lists both) |
| Size | About 110 employees (one profile) | Low |
| Product names | InstaWorkers (vertical AI agents); Lily (AI Forward Deployed Engineer) | High |

Sources: [Modern Distribution Management, Series B](https://www.mdm.com/news/technology/ai/instalily-raises-60m-launches-ai-engineer-for-enterprise-operations/), [CB Insights](https://www.cbinsights.com/company/instalily), [Pulse 2.0, Series B](https://pulse2.com/instalily-raises-60-million-series-b-and-launches-lily-as-an-ai-forward-deployed-engineer/), [Pulse 2.0, Series A](https://pulse2.com/instalily-25-million-series-a-secured-for-deploying-domain-trained-agents/amp/), [company profile aggregator](https://www.vcbacked.co/company/instalily-ai).

## Product

- **InstaWorkers:** AI "teammates" that work inside a client's existing software, so they do not need a system overhaul. Press describes them handling quoting, ticket triage, claims review and exception handling, with human-in-the-loop review. Source: [Insight Partners](https://www.insightpartners.com/ideas/instalily-raises-25m-to-bring-ai-teammates-to-the-frontlines-of-distribution/), [MDM Series A](https://mdm.com/news/technology/ai/ai-powered-distributor-automation-platform-instalily-raises-25m-in-funding/).
- **Lily:** the company calls it "the world's first AI Forward Deployed Engineer". It learns how a business works, builds the software it needs, and goes live in days. The company says it "adapts the software without losing the outcome". Source: [Lily product page](https://www.instalily.ai/lily), [Lily intro](https://instalily.ai/fde) (page content only partly rendered).
- **Target sectors:** distribution is the focus (industrial distribution, MRO). Press also lists manufacturing, insurance, healthcare and construction (unverified).
- **Use cases from the brief:** sales enablement, lead generation, quote-to-order, email and master-data management (from the summary file).
- **Architecture:** one report describes a data layer, composable layer, learning layer and customer layer (unverified, single source).
- **Distribution:** InstaWorkers listed on Google Cloud Marketplace, October 2025 (press).

## Customers

No named paying customers were confirmed. Home Depot Ventures and United Rentals invested in the Series B, which is not the same as being customers (unverified as customers). The company says its agents are "purpose-built for distribution, supply chain and industrial operators".

## Funding

| Round | Date | Amount | Lead | Notes |
|---|---|---|---|---|
| Series A | Aug 2025 | $25M | Insight Partners | With Perceptive Ventures and Marvin Ventures |
| Series B | Jul 2026 | $60M | Energize Capital | Insight Partners, Home Depot Ventures and United Rentals also in. Total about $100M (MDM). |

Sources: [Insight Partners](https://www.insightpartners.com/ideas/instalily-raises-25m-to-bring-ai-teammates-to-the-frontlines-of-distribution/), [SiliconANGLE, Series B](https://siliconangle.com/2026/07/14/instalily-developer-ai-teammates-can-automate-complex-business-specific-work-raises-60m/), [raising.fi](https://raising.fi/news/instalily-ai-series-b-july-2026), [Wilson Sonsini notice via search](https://www.mdm.com/?p=407098).

## Engineering and stack signals

- **Engineering blog:** not found. The company blog post for the Series B was referenced by a law-firm notice but no URL was located **(unverified)**.
- **Job-ad stack** (from Greenhouse listings, via aggregators): TypeScript and Python. Frontend React and Next.js. Backend FastAPI and SQLAlchemy. PostgreSQL with Alembic. Nice to have: Temporal, Docker. Source: [Greenhouse board](https://job-boards.greenhouse.io/instalilyai/jobs/4261595009), [Software Engineer I](https://www.instalily.ai/careers/software-engineer-i-general-4271757009), [Full Stack ad](https://agentic-engineering-jobs.com/jobs/instalily-software-engineer-full-stack-okp74F).
- **Roles:** Software Engineer I and II, Full Stack, Engineering Manager (London). "Forward deployed engineer" is the product's marketing name, not a job title (per an interview-prep guide).
- **GitHub org `Instalily`** (checked with `gh`, 7 Nov 2026):

| Repo | Stars | Licence | Last push | What it is |
|---|---|---|---|---|
| `Instalily/edge-connector` | 0 | Apache-2.0 | 2026-11-06 | Outbound-only connector appliance and per-customer hub for reaching allow-listed resources in customer networks. Shows how they reach client systems. |
| `Instalily/lily-pr-demo` | 1 | none | 2026-10-05 | Demo app showing Lily opening real pull requests on a backlog board. Shows the "AI engineer opens PRs" pattern. |
| `Instalily/fastembed-brain-compat` | not checked | not checked | not checked | Embedding library compatibility. Not relevant to the track. |

## Events and hackathons

- **Google DeepMind x InstaLILY SF office opening + hackathon** (ship26): builders ship "edge-native, agentic systems that push AI beyond the limits of the cloud". Registration closed. [ship26.instalily.ai](https://ship26.instalily.ai/), [Luma listing](https://luma.com/lw45p5sw).
- **Toronto hackathon with Google DeepMind** on agent swarms, winner decided by highest verified score. [toronto26.instalily.ai](https://toronto26.instalily.ai/).
- No public challenge brief, kit or evaluator for the HackTheBurgh track was found. The full brief sits behind the QR code (not read).

## What they care about (for the pitch)

1. **Measurable results in a real workflow**, not demos. Their own words: "measurable results".
2. **Working inside legacy software** with no rebuild.
3. **Human in the loop** for exceptions and approvals.
4. **Speed to live deployment** ("live in days").
5. **Forward-deployed judgement**: engineers who sit with the customer and adapt.
6. **Edge and secure connectivity** (edge-connector, edge-native hackathon).

## Implications for us

- Lean into "an engineer that works like a forward-deployed engineer": it reads the person's level, does what was asked, and reports exactly what it did and did not verify. That matches their own language.
- Show one clear workflow end to end. They want real output from a real task.
- Their GitHub activity uses Apache-2.0 for their infrastructure repos, so the hackathon kit is likely to be shared as code. Confirm the licence in the kit before reusing it.
