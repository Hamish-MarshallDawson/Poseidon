# Hamish's research

Sponsor research for HackTheBurgh XIII, written 7 Nov 2026 by three Haiku 5.5 research agents, one per company. The working idea is a **Wordsmith-track agentic browser** as the baseline project, with other tracks as a bonus. The source context is [`../../InductionPresentations/SlideSummaryFromTranscription.MD`](../../InductionPresentations/SlideSummaryFromTranscription.MD).

**Lead concept (7 Nov, 13:30):** Aiden's **Clearance**, in [`../aiden-research/wordsmith-wave/SYNTHESIS.md`](../aiden-research/wordsmith-wave/SYNTHESIS.md). The agent starts from a supplier contract, checks the supplier and each sub-processor across live registers and the supplier's own site, and reconciles the findings against the contract. It then writes a redline and submits it to a mock procurement portal with proof of each step. Read that first; this folder is background. Hamish adds three things to it:
1. **A data-transfer check:** for a US sub-processor, check the UK–US data bridge (Data Privacy Framework list). If the sub-processor isn't on it, flag that a transfer agreement (IDTA or addendum) is needed.
2. **Slack in and out:** the request arrives in Slack and the approval card goes back to Slack, matching Wordsmith's own Receive, Route, Resolve, Record flow.
3. **MLH bolt-ons:** Gemini Flash for the cheap read and extract steps (Gemini prize), Auth0 for the approval gate and acting on the user's behalf (Auth0 prize), and Tiger Data for the evidence and audit store (Tiger Data prize). See section 3.9 of the summary file.

The ideas in each folder's `05-ideas.md` are now inputs, not the plan.

Each folder has the same layout: `README.md` (TL;DR, start here), `01-company.md`, `02-track.md`, `03-github-projects.md` (repos with licences), `04-ui-design.md`, `05-ideas.md` and `sources.md`.

| Folder | Track | Top idea from the research | Fit with the baseline |
|---|---|---|---|
| [wordsmith/](wordsmith/README.md) | Most complicated end-to-end agentic browser workflow (legal bonus, token-efficiency tie-break) | Counterparty due-diligence agent: Companies House plus supplier sites, cited memo, approval gate, live token count | It is the baseline |
| [jetbrains/](jetbrains/README.md) | Help the Developer (build inside JetBrains IDEs with AI) | Repro Pilot: bug report to browser reproduction to failing Playwright test, as an ACP agent with Playwright MCP | Good: the same browser engine, aimed at developers |
| [instalily/](instalily/README.md) | Coding agent that adapts to three personas (hidden tests, live judging) | "Same bug, three answers" with a verified-only honesty layer; third persona is a teacher | Weak: browser only as an optional beginner step |

**Licence rule used throughout:** MIT, Apache-2.0 or BSD means we can reuse code with attribution. AGPL or GPL (e.g. Skyvern, workflow-use) means ideas only. No licence means ideas only.

**Still unread:** the JetBrains judging criteria and the InstaLILY full brief and team kit (both behind QR codes). Recheck `02-track.md` in each folder once they're read.
