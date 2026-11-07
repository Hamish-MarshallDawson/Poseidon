# JetBrains research: README (entry point)

**TL;DR (as of 7 Nov 2026)**

1. **Track:** "Help the Developer", Gold, €350 per member. Deliberately vague. Hard rule: the agentic development must run **inside JetBrains IDEs, using AI**, and judges ask how we used AI.
2. **Judging criteria are unknown.** The five criteria are behind the booth QR code and on Discord. No public 2025 to 2026 JetBrains version matched "Help the Developer". A Cloud9 x JetBrains event (other event) starts its criteria with "Technological Implementation".
3. **Cheapest route that passes the process rule:** build an **ACP agent** (TypeScript) that runs in the JetBrains AI Chat, and give it browser tools over **MCP** (Playwright MCP). No Kotlin, no plugin. ACP agents work without a JetBrains AI subscription.
4. **JetBrains AI stack now:** AI Assistant (all IDEs, ACP agents), Junie (agent, CLI with `/plan` and `/review`), Air (multi-agent, macOS preview), Mellum2 (12B open model, Apache-2.0), Koog (Kotlin agent framework, 1.0 stable, Apache-2.0), and the IDE built-in MCP server.
5. **Free access:** AI Free tier (credit-based Junie), student licences, and the event's free coding-agent offer and one OpenAI key per team (get it at the booth; never commit it).
6. **Best-fit idea (rank 1):** **Repro Pilot**. A bug report pasted into the IDE becomes a live browser reproduction and a failing Playwright test. It is the baseline agentic browser, aimed at developers.
7. **Strongest repos to reuse:** Playwright MCP (Apache-2.0), ACP SDK (Apache-2.0), Stagehand (MIT), webqa-agent (Apache-2.0, to evaluate). Copy no code from repos with no licence (qa-use, qa-agent) or AGPL (jimmytoan/qa-agent). Zed's licence is mixed: check before reuse.
8. **UI patterns that win:** a plan gate (approve before edits), a step timeline with a live snapshot, visual proof attached to the output, per-hunk diff review, and an Islands-theme look.
9. **Before 13:00 Saturday:** do the IDE setup checklist in [02-track.md](02-track.md), section 2; scan the JetBrains judging QR code; confirm each member's free licence.
10. **Biggest unknowns:** the five judging criteria, whether the key goes into Junie or AI Assistant as expected, the London office (no public confirmation found), and whether Air's Windows build arrives in time (not needed for us).

## Index

- [01-company.md](01-company.md): who JetBrains is, their AI products as of late 2026 (AI Assistant, Junie, Air, Mellum2, Koog, ACP, MCP), student access, internships and what they care about.
- [02-track.md](02-track.md): the brief restated, the IDE setup checklist for the process rule, how to build for JetBrains IDEs (plugin vs ACP vs MCP, recommendation B+C), judging unknowns, the "how we used AI" log, and what wins or loses.
- [03-github-projects.md](03-github-projects.md): 22 relevant open-source projects in a table (stars, licence, last push), with architecture, reuse and gotchas for the important ones.
- [04-ui-design.md](04-ui-design.md): JetBrains' agent UI and IDE chrome, competitor patterns (Cline, Roo, Windsurf, Copilot, Cursor, Diffzu), and the patterns to use in a 24-hour demo.
- [05-ideas.md](05-ideas.md): four ranked project angles on the baseline agentic browser (Repro Pilot, Preview Auditor, Test Freezer, Adaptive Coding Agent with browser check), each with demo flow, stack, riskiest part, 30-minute check and a 24-hour plan.
- [sources.md](sources.md): every URL used, grouped by topic, with what each gave us. Lists what could not be read in this pass.
