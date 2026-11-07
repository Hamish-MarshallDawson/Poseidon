# Wordsmith AI track: challenge, judging and fit

Researched 7 Nov 2026. Brief and judging come from our notes file `InductionPresentations\SlideSummaryFromTranscription.MD` (section 3.6), which was compiled from the opening ceremony and the Wordsmith slide. Their full slide was not photographed in full, so some detail is missing (see section 5).

## 1. The challenge, restated

- **Track name:** Wordsmith AI (Silver). Edinburgh legal AI company, recent Series B, hiring fast.
- **Headline brief:** "the most complicated end-to-end agentic AI browser-use workflow".
- **Their words:** "make something really, really cool with browsers and agents." Open-ended. Find a niche inside the unsolved problem of agents using browsers.
- **Complexity:** judged on a complex task end to end. Not complex internals for their own sake.
- **Bonus:** a few extra points if the project is **legal-focused**. Not required.
- **Tie-breaker:** **tokens used, model used and compute efficiency.** (Stated as a tie-breaker, so it can decide between close entries.)
- **Prize:** AirPods Max for every member of the winning team. Second and third: goodie bags.
- **Company context on their slide:** contact emails were on the slide (not captured in our notes; ask the booth or check the photo).

Shared rules that apply to every track (from `SlideSummaryFromTranscription.MD`, section 2):
- One project, one codebase. A project may enter several tracks.
- Only work built during the hackathon counts. Start a fresh repo after 12:00 Saturday.
- Open-source code and libraries allowed, following their licences.
- Disclose all generative AI use and explain what it did. Keep a running log of AI tool use.
- Submission deadline 12:00 Sunday 8 Nov. Demos from 12:30 Sunday.

## 2. What the judges are likely to reward

Read literally, the brief scores four things. Ranked by how much the words suggest they matter:

1. **End-to-end completeness.** One real task from start to finish, with a visible outcome. "End to end" is the main word in the title. A demo that stops at "extracted data" will look incomplete.
2. **Browser-use difficulty, handled well.** The judges say "browser-use", so they expect real browsing: logins or forms, multi-page flows, dynamic sites, and handling of failure. A static scrape will not impress.
3. **Efficiency, measured and shown.** Tokens per task, model choice, runtime, cost per successful task. This is the tie-breaker, so a team that shows these numbers on screen has an edge. Most teams will not measure it.
4. **Legal fit (bonus).** A legal workflow that uses real UK public legal data, with citations and an approval step, earns bonus points and matches their product.

Our own read of what impresses this company specifically, from their product (see `01-company.md` section 10):
- Provenance: every fact has a source URL and a timestamp.
- A human approval gate before any action that changes something.
- A clear data-handling answer (what leaves the machine, what the model sees).
- A workflow that starts from a request, the way their intake works (Slack or email in, memo out).

## 3. What is likely to lose

- **A demo that depends on a live third-party site.** Bot blocks, CAPTCHAs, login walls, slow pages and changed layouts are the most common failure. The brief says "unsolved problem" so judges will expect failures, but a failure during the demo is still a loss. Record a backup run.
- **Scraping a site that has an API.** Companies House, Find Case Law and legislation.gov.uk all have APIs or bulk data. A judge will ask "why a browser?" Use the browser where it earns its place, and say so.
- **Legal output without legal care.** Wordsmith's own guidance excludes legal advice to individuals and "standalone case-law citation lookup". A project that gives confident legal conclusions without sources, or that files something with a regulator, will look careless. Frame outputs as "research memo for a lawyer to review".
- **Efficiency claims with no numbers.** "We were efficient" with no tokens and no cost will not score on the tie-breaker. Show a table.
- **Unclear scope.** The brief is open. A team that cannot say in one sentence what the agent does will lose to one that can.
- **Overbuilding the agent.** "Most complicated" can be read as "most agents". Ten sub-agents that all stall in the demo are worse than three that work. Our notes say: the main feature must carry the demo on its own.

## 4. How the baseline agentic-browser idea scores against this track

The baseline idea (from `SlideSummaryFromTranscription.MD` and the team's notes): a browser agent that completes a complex end-to-end workflow in a real browser.

| Criterion | Baseline as stated | With our proposed additions |
|---|---|---|
| End-to-end | Strong, if the workflow is named and finishes | Strong |
| Browser-use difficulty | Strong if it logs in or navigates multi-step pages | Strong |
| Efficiency (tie-breaker) | Weak unless measured | Strong if we log tokens per step, cache repeated steps, and report cost per run |
| Legal bonus | None by default | Add UK public legal data sources with citations and an approval gate |
| Demo risk | Depends on third-party sites | Reduce by using APIs for the data and the browser for the one step that needs it |

**Verdict:** the baseline is a fair fit, but it needs two additions to score well here: a legal data angle (for the bonus) and measured efficiency (for the tie-breaker). See `05-ideas.md` for angles that add both.

## 5. Unknowns still to check

- **Full Wordsmith slide.** Our notes do not record the contact emails, judging detail beyond the summary, or any submission format note from their slide. Photograph or re-read the slide.
- **Whether Wordsmith gives a key for their API** to hackathon teams. Worth asking at their stand (our notes do not confirm a Wordsmith stall; their contacts are on the slide).
- **How "model used" is scored.** Is a smaller or local model preferred, or is it just recorded? Ask.
- **How tokens are counted.** Per run, per team total, or including development? Ask.
- **Whether a browser run must be live in the demo.** The brief says "browser-use workflow" but not whether a recording is acceptable. Plan for live plus a recording.
- **Whether a legal bonus needs a lawyer on the team.** Not stated. We should not claim legal advice regardless.
- **Their judging panel.** Not recorded in our notes.
- **Whether projects can enter both Wordsmith and Metaview (Best Overall).** Our notes say Metaview's Best Overall is open to any project, so yes in principle. Confirm the rule for "for several tracks".

## 6. Track-specific rules we must respect

- **Legal data licences.** Find Case Law's Open Justice Licence excludes computational analysis and search-index building. Bulk programmatic use needs a separate licence application. See `03-github-projects.md` and `05-ideas.md`.
- **robots.txt and terms.** legislation.gov.uk's own policy requires robots.txt compliance and a clear user-agent. Our browser agent must identify itself and respect crawl rates.
- **No regulatory filings.** Do not build a demo that files something with a regulator or court. It is outside what the sponsor does and a judge will flag it.
- **AI disclosure.** Keep a log of every AI tool and model used, and what it did. Needed for the write-up and for the tie-breaker.
- **Keys.** Keep any API key out of the repo. JetBrains warns that keys get blocked on GitHub; apply the same habit to everything.

## 7. Score sheet (our own guess, for planning only)

Not a sponsor document. Use it to decide where to spend the 24 hours.

| Criterion | Weight (our guess) | Plan |
|---|---|---|
| End-to-end task completes live | High | One workflow, rehearsed, with a recorded backup |
| Browser-use is real and visible | High | Live browser view, real logins or forms, one hard step |
| Legal fit with citations | Medium (bonus) | Provenance on every fact; approval gate |
| Tokens, model, cost measured | Medium (tie-breaker) | A live counter, and a table in the write-up |
| Polish and story | Medium | One clear sentence of what it does |
