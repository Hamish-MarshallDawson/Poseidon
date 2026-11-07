# Project angles for the Wordsmith track, ranked

Researched 7 Nov 2026. Each angle extends the baseline agentic browser (a browser agent that completes an end-to-end workflow). Ranking is our judgement, for the team to decide. Sources are in `sources.md`; repo facts are in `03-github-projects.md`.

**Ranking logic:** the Wordsmith track rewards an end-to-end browser task, a legal angle (bonus), and measured tokens and cost (tie-breaker). Angle 1 scores best on the legal bonus and matches their product. Angle 2 has the most browser work but no legal angle. Angle 3 has the strongest legal fit but the least browser work.

---

## 1. Counterparty due-diligence agent with a cited memo (recommended)

**Pitch.** An in-house lawyer gets a Slack request: "We want to onboard supplier X. Can you check them?" A browser agent gathers the facts a legal team needs before signing: the company's registered status and officers from Companies House, the supplier's own terms and privacy pages from their website, and whether those pages are reachable and allowed under their robots.txt. It writes a short memo where every fact has a source link and a timestamp. It stops at a human approval gate before posting the memo back to Slack. Nothing is submitted to any regulator or court. The output is a research memo for a lawyer to review, not legal advice.

This matches Wordsmith's product (intake, triage, "Record" step, Slack in and out, provenance on every fact) and their own list of intake tasks ("vendor questionnaire", "legal intake and triage").

**Demo flow (step by step, about 3 minutes live):**
1. A Slack-style request card appears: "Onboard supplier X, need a check by Friday." (The Receive step.)
2. The Route step tags it: company check plus terms review. The team can see which sources will be used before anything runs.
3. The agent calls the Companies House API for the company number, status, incorporation date and officers. (API, not browser.) Each fact goes into the facts table with its source URL and time.
4. The agent opens the supplier's website in a real browser. It finds the terms and privacy pages from the homepage links. A visible step shows the page being read. (Browser step 1.)
5. Before reading any page, the agent checks robots.txt for the site and records the result in the audit trail. If disallowed, it stops and says so. (Compliance step, visible in the timeline.)
6. A login-walled page or a cookie or bot challenge appears. The agent shows "Needs you" and offers a takeover button. The presenter completes it, then clicks Done. (Human takeover, also addresses the unsolved login problem openly.)
7. The Resolve step writes the memo. Every claim has a citation. Unknowns are marked "not found".
8. The approval card appears: "Post this memo (2 pages, 14 facts, 3 unverified) to #legal-intake?" with Approve, Edit, Stop.
9. On approval, the memo posts to Slack (a real webhook or a mock). The Record step shows the stored audit trail.
10. Token and cost counter on screen: total tokens, model used, cost per run, and tokens saved by the cache on a second run of the same supplier.

**Other tracks it also enters:**
- **Metaview (Best Overall Project):** any project is eligible, judged on creativity. Narrative: "agents that do the boring research before a human decides." Stretch.
- **Not a fit:** Bank of Scotland, HRT, G-Research, JetBrains, InstaLILY, Viridien. The legal memo is not cost-of-living, data-prediction, developer tooling or document-vision work.

**Stack and repos.**
- Agent loop: **Stagehand** (TypeScript, MIT, action caching) or **browser-use** (Python, MIT). Pick by team language. Aiden (TypeScript) suits Stagehand.
- Observation: **Playwright MCP**-style accessibility snapshots (Apache-2.0) to keep tokens down.
- UI: ideas from **Nanobrowser** (side panel, Ask/Auto, per-site rules; Apache-2.0) and **Browser Use** human takeover (MIT docs). Do not copy AGPL code from Skyvern or workflow-use.
- Data: Companies House public API (free key, rate limit per their developer guidelines). The register's bulk snapshot is a fallback for many companies, not needed here.
- Memo output: Markdown or DOCX. A Markdown memo is faster.

**The riskiest part.** Supplier websites hide terms behind menus, cookie banners or bot checks. The memo is worth little if the terms page is not found.

**How to check it in under 30 minutes.**
1. Get a Companies House API key (free registration) and call the company search and company profile for three real companies. Confirm the fields you need come back.
2. Run a Stagehand or browser-use script on three supplier sites (for example a SaaS vendor, a retailer and a small firm). Ask it to find the terms and privacy pages. Count how many succeed on the first try.
3. Read robots.txt for the three sites. Record what it says. Do not fetch any page disallowed by it.
If (2) fails for two of three sites, change the target to suppliers you control (your own test site) for the demo and say so.

**Rough 24-hour build plan** (hacking starts 12:00 Saturday; feature freeze 09:00 Sunday, which is the 21-hour mark; submission 12:00 Sunday).
- **0:00–1:30:** Fresh repo. Draw the four-step flow and the approval card on paper. Show the sponsor the flow on paper before coding (team rule).
- **1:30–5:00:** Companies House API client, facts table with sources. Hardcode one supplier.
- **5:00–9:00:** Browser step on one supplier site. Find terms and privacy pages. robots.txt check. Audit trail.
- **9:00–12:00:** Memo generator with citations and "not found" handling.
- **12:00–15:00:** Approval card, Slack post (webhook or mock), takeover button with Done and Failed.
- **15:00–18:00:** Token and cost meter. Caching of the second run. Log model and tokens per step.
- **18:00–21:00:** Second and third supplier sites. Error states. Clean UI.
- **21:00 (09:00 Sunday):** Feature freeze.
- **21:00–23:00:** Rehearse twice. Record the backup video. Write the AI-use log and the efficiency table.
- **23:00–24:00:** Submit before 12:00.

---

## 2. Basket agent with a legal and terms layer (the team's option B)

**Pitch.** A user gives a shopping list and a priority (cheapest, greenest, fewest shops, diet). A browser agent visits two or three UK supermarket websites, builds the best basket for each priority, and explains each swap. Sustainability data comes from the Open Food Facts API (ODbL). For the legal bonus, the agent checks each site's terms and robots.txt before acting, and shows that check on screen. Sponsor for this track: Wordsmith; Bank of Scotland is a strong second fit (cost of living).

**Demo flow (about 3 minutes live):**
1. A list is typed in: "milk, 2 loaves, eggs, pasta, 3 apples." Priority selected: "cheapest, fewest shops."
2. The agent shows the sites it will use and the terms check for each: robots.txt allowed or not, terms found or not.
3. Browser steps: search each item on site A, then site B. Snapshot per step. Token count rises on screen.
4. Swaps: the agent picks the cheapest per item and explains each swap in one line.
5. Approval gate: "Add these 9 items to your basket on Site A? Total £X. Approve / Edit / Stop." Nothing is bought.
6. Final basket table, source for every price with time, and the token and cost counter.

**Other tracks:** Bank of Scotland (Smart Cost of Living), Metaview (Best Overall), Wordsmith (with the legal layer).

**Stack and repos.** Stagehand or browser-use for the browser; Open Food Facts API (ODbL, attribution and share-alike; use a custom User-Agent as their support page requires). Playwright MCP-style snapshots.

**Riskiest part.** Supermarket bot blocking and login walls. Browser-agent demos on live retail sites are slow and fragile.

**How to check it in under 30 minutes.** Our notes already list this check: spend 20 minutes testing Tesco, Asda and Sainsbury's with Playwright, and check Open Food Facts UK coverage. Also check each site's robots.txt and whether search results load without login. If two of three sites block automated access, switch to a mock store for the demo.

**Rough 24-hour plan.** Similar to angle 1. The browser work is more of the build, and the legal layer is a smaller add-on (robots and terms check, about 2 hours).

**Why ranked second.** The browser work is the most visible, and judges like "watch it shop". But it has no real legal angle, so it only gets the bonus through the terms check. Its demo risk is higher than angle 1, because retailers are more likely to block bots than company registers and supplier sites.

---

## 3. Citation checker for legal text (legislation and case law)

**Pitch.** A lawyer pastes a draft clause or memo that cites UK legislation and cases. The agent checks each citation. For legislation, it uses the legislation.gov.uk API (not browsing) to confirm the section exists and reads its text. For cases, it opens the judgment on the National Archives' Find Case Law service (browser step) and confirms the case name, court and date. It outputs a table: citation, status (found, not found, or cannot check), the quoted text, and the link. It never says whether the clause is legally correct. It only says whether the cited source exists and says what it says.

This is the strongest legal-bonus fit of the three. It also matches Wordsmith's "trust and citations" message.

**Demo flow (about 3 minutes live):**
1. Paste a clause with four citations (two Acts, two judgments). One is deliberately wrong.
2. The agent parses the citations into a list. The timeline shows four checks.
3. Legislation checks run through the API. Each shows the section text and a source link.
4. Case checks open Find Case Law in the browser, one at a time. A visible page read for each. (The browser step.)
5. The wrong citation is marked "not found". It is not guessed or silently corrected.
6. A table, with source links, is produced. Approval gate before the table is shared.
7. Cost counter: calls made, tokens per check. Show the cache on a second paste.

**Other tracks:** Wordsmith (legal bonus, citations). Metaview (Best Overall) is a stretch.

**Stack and repos.**
- Legislation: legislation.gov.uk API (free for reuse under data.gov.uk licence per a 2010 blog post; **(dated)**). Respect robots.txt, identify your user-agent, and stay under their crawl rate. Their data reuse documentation suggests a conservative rate, for example 10 requests per 5 to 10 seconds, where no crawl-delay is set.
- Case law: Find Case Law. **Licence check first.** Its Open Justice Licence v1.0 allows reuse including commercial, but excludes computational analysis and building a search index. Bulk programmatic searching needs a separate licence application (the transactional licence, or contact caselawlicence@nationalarchives.gov.uk). Reading a few named judgments one at a time for a demo is a different question. Confirm with the National Archives before relying on it, and say the licence position on screen.
- Browser: Stagehand or browser-use, or a plain Playwright script (the browser step is small).
- Docs to read: [National Archives Find Case Law docs](https://github.com/nationalarchives/ds-find-caselaw-docs) (MIT, read only), legislation.gov.uk fair-use policy.

**The riskiest part.** The Find Case Law licence. A judge who knows UK law will ask, and "we scraped it" is the wrong answer. Second risk: finding the right judgment page from a citation string.

**How to check it in under 30 minutes.**
1. Call legislation.gov.uk for one Act section (the API returns XML). Check you get the section text.
2. Open three judgments on Find Case Law by citation. Check you can find each from its neutral citation, and note the page layout.
3. Read the Find Case Law licence and the legislation.gov.uk fair-use policy. Write one paragraph on what the demo does and does not do under them.
If step 2 fails (no reliable way to find a judgment from its citation), limit the demo to legislation and say why.

**Rough 24-hour plan.** Citation parser (regex plus a small LLM step) 0–4h. Legislation API client 4–7h. Find Case Law browser step 7–12h. Table output and approval 12–16h. Cost meter and cache 16–19h. Two test documents plus one with a deliberate error, freeze at hour 21, backup video.

**Why ranked third.** The legal fit is strongest, but the browser work is the smallest of the three. The judges' "most complicated browser workflow" criterion will score it lower unless it adds a second browser step. It also has the licence question. It is a good second project to add if angle 1 is working by hour 12.

---

## Options considered and not ranked

- **Adaptive coding agent (InstaLILY) and Scam Call Shield** are not Wordsmith-track ideas. Only the Wordsmith judges' rules matter here.
- **Land Registry and Registers of Scotland lookups.** HM Land Registry's Business Gateway API (England and Wales) needs a Business Gateway account and an SSL certificate. ScotLIS (Scotland) needs a Registers of Scotland business account, a FAS account and Direct Debit billing. Neither can be set up in 24 hours for a demo. Mention as future work only.
- **Court and tribunal portals, gov.uk forms.** Not researched in this session (**unverified**). Also, Wordsmith's own guidance excludes court and regulatory filings, so any demo that files something with a court or regulator is off-brief.

## Shared gotchas for all three

- **Keys.** Keep the Companies House key, any OpenAI key and any other API key out of the repo.
- **AI-use log.** Keep a running log of tools, models and what they did. The brief requires disclosure.
- **Efficiency table.** For every demo, report tokens per step, total tokens, model name, cost per run and cost per successful run. This is the tie-breaker.
- **Backup video.** Record a full run by feature freeze, as the team agreed.
