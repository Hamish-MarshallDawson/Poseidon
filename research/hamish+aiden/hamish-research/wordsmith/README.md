# Wordsmith AI track: research entry point

Researched 7 Nov 2026 for HackTheBurgh XIII. Start here, then read the files in the order below.

## TL;DR

- **Who they are:** Edinburgh legal AI company selling an AI platform built for **in-house legal teams** (intake, contract review, drafting, research). Series B of $70M (3 June 2026, Highland Europe and Index Ventures), plus a $14M extension. About $100M raised in total. Over 500 in-house customers (their claim).
- **The brief:** "the most complicated end-to-end agentic AI browser-use workflow". Judged on end-to-end complexity. Legal focus gives bonus points. **Tie-breaker: tokens used, model used, compute efficiency.**
- **Our angle:** a legal browser agent that completes one real task end to end, shows a source and timestamp for every fact, stops at a human approval gate, and reports tokens and cost live.
- **Recommended idea (ranked first):** counterparty due-diligence agent. Companies House API plus a supplier-site browser step, robots.txt check, human takeover for blocked pages, cited memo, approval before posting to Slack.
- **Best open-source starting points:** Stagehand (MIT, ~25,978 stars, action caching) or browser-use (MIT, ~120,243 stars). Avoid copying code from Skyvern or workflow-use (AGPL-3.0).
- **Efficiency tools to borrow:** accessibility snapshots instead of screenshots (Playwright MCP, Apache-2.0), cached replay of successful steps (Stagehand, workflow-use ideas), and small models for easy steps.
- **UI to borrow:** Nanobrowser-style side panel (Ask/Auto, per-site rules), Browser Use and Cloudflare-style live view with "take over" and "Done / Failed", Wordsmith's Receive, Route, Resolve, Record flow.
- **Legal data, with licence limits:** Companies House API (free key) and legislation.gov.uk are usable for a demo. Find Case Law's Open Justice Licence excludes computational analysis, so a bulk-search demo needs a separate licence.
- **Biggest unknowns:** Wordsmith's founding year (2020 on their own site vs 2023 in press), the exact headcount, whether hackathon teams can get an API key, and how efficiency is scored.
- **Risks to plan for:** login walls, CAPTCHAs and bot blocks on live sites; a demo that depends on one fragile site; legal claims without citations.

## Index

- `01-company.md`: Wordsmith's product, customers, funding (with conflicts), founders, office, GitHub org, hiring, and what they care about.
- `02-track.md`: the Wordsmith challenge restated, what judges will reward, what will lose, unknowns, and how the baseline idea scores.
- `03-github-projects.md`: 14 relevant repos with stars, licence and last push, grouped as frameworks, benchmarks and legal docs; licence rules applied.
- `04-ui-design.md`: how Wordsmith and competing agent products present their work; patterns to use and avoid for a 24-hour demo.
- `05-ideas.md`: three ranked project angles with pitch, demo flow, stack, riskiest part, 30-minute check and 24-hour plan.
- `sources.md`: every URL used, grouped by topic, with what each gave us.
- `README.md`: this file.

## Notes

- Star counts are as of 7 Nov 2026 (`gh`). Vendor figures (prices, benchmark scores) are marked as claims.
- Most product UI evidence came from text and search snippets, not screenshots. Layouts in `04-ui-design.md` are our recommendation.
- Items marked **(unverified)** could not be confirmed. Do not present them as fact in a pitch.
