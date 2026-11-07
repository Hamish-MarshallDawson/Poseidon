# InstaLILY research: README

> **Correction (7 Nov, 13:40): the official brief overrides parts of this folder.** Read `research/hamish+aiden/Insta Lily/Agentic_IDE_Challenge_Brief.md` and `Agent_Contract.md` (the technical contract) first.
> - **Minimum bar:** the agent runs headless with one command, `agent`, and must *cleanly fix every one of a set of simple bugs* on an unseen project. Teams that miss this aren't ranked. So the beginner persona **does fix the bug**, then explains and checks understanding (their slide example does exactly this). Where these notes say "don't fix for beginners", that is wrong.
> - The agent should **work out who it's helping without being told**. A manual persona switch alone falls short.
> - Judging: automated conversations with hidden simulated users and an AI judge, then four InstaLILY engineers at our table.
> - Kit: a starter agent, a Dockerfile, a manifest, and Gemini through their gateway with a US$50 key. Start from open source or our own code; they score what we add.


Entry point for the InstaLILY track ("build a coding agent that adapts to whoever is using it"). Researched 7 Nov 2026. The full brief behind the QR code has not been read, so re-check `02-track.md` once it is.

## TL;DR

1. InstaLILY is a New York company (offices in SF, London, Toronto) selling InstaWorkers and "Lily", an AI forward-deployed engineer for industrial distribution. Series B of $60M in July 2026, led by Energize Capital, after a $25M Series A in 2025.
2. They judge on three stages: same hidden tests for all, then "does what was asked, no more, and reports honestly", then live use by their engineers with our personas. Understanding the user weighs the most.
3. The beginner persona should ask, hint and guide, not fix. Evidence: CodeHelp (guardrails), Xiao et al. (hint levels: high-level hints alone can mislead; add a worked example), CS50 duck (no full answers).
4. The engineer persona should make a minimal diff, run the tests, and say what it verified. Aider and Claude Code show the pattern; Codex CLI shows approval modes.
5. Nobody found detects skill level automatically. Most tools use a manual mode or course context. That is our opening.
6. Persona must change tools and defaults, not just tone. Use Zed-style tool profiles and a visible persona switch.
7. Recommended entry: "Same bug, three answers" (idea 1), with the verified-only honesty layer (idea 2). Third persona: a teacher marking class code.
8. The baseline agentic browser fits weakly. Use it only as an optional beginner proof step (live docs, page render), behind a flag. It does not help hidden tests.
9. Stage 1 is a gate. Build the hidden-test pass rate first, then persona UI.
10. Read the QR brief and team kit in the first 30 minutes: they fix the harness interface, language and LLM.
11. Repos: Aider (Apache-2.0), Codex CLI (Apache-2.0), Cline (Apache-2.0), Claude Code (no licence: ideas only), SWE-bench (MIT). Full table in `03-github-projects.md`.

## Index

- [01-company.md](01-company.md): who InstaLILY is, product, funding, founders, stack signals, GitHub org, events, what they care about.
- [02-track.md](02-track.md): the brief and judging restated, what impresses, what loses, unknowns to check, baseline fit score.
- [03-github-projects.md](03-github-projects.md): 15 repos with stars, licence, last push; grouped notes on architecture, reuse, borrow, gotchas.
- [04-ui-design.md](04-ui-design.md): how existing tools switch persona and refuse; persona switcher, depth slider, timeline, diff and approval patterns; demo patterns.
- [05-ideas.md](05-ideas.md): five ranked project angles with pitch, demo flow, stack, riskiest part, 24-hour plan, and third-persona options.
- [sources.md](sources.md): every URL used, grouped by topic, with what each gave us and what was not checked.

## Method notes

- No WebFetch tool was available. Pages were read via WebSearch excerpts, `curl` and `gh`. Company site pages are JavaScript-only and did not render.
- No subagents were started.
- Figures marked "(unverified)" or from a single secondary source should be checked before a pitch.
