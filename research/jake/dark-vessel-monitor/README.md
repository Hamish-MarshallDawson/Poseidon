# Dark Vessel Monitor (working title): research pack

Jake's research for the HackTheBurgh XIII project idea, written up with Claude on 7 Nov 2026. **Agents: please double-check this before the team commits to it.**

## The idea in one line

A live map of the Baltic that spots ships hiding from tracking (AIS switched off or faked), forecasts which ones will go dark in the next 6 hours, and ranks them for inspection. Aimed at both sponsor tracks:

- **G-Research:** "choose something hard to observe; show what's hidden, how we find it, what we do with it".
- **HRT:** "best use of data for predictions and decision making; automated decisions; streams of data; alternative datasets".

## What's in this folder

| File | What it is |
| --- | --- |
| [claims-to-verify.md](claims-to-verify.md) | **Start here if you are checking.** Every factual claim the plan relies on, with its source and a status column |
| [project-summary.md](project-summary.md) | Short version of the whole plan: idea, scope, data, stack, build plan, demo, risks, competition, extensions |
| [pitch-plan.md](pitch-plan.md) | Team pitch plan, plus the SE Asia fishing, Hormuz energy-market and Palantir/competitor sections |
| [api-and-visualisation-research.md](api-and-visualisation-research.md) | Deep dive on AISStream and backup feeds, detection signals, map stack, architecture, 24 h plan, failure playbook |
| [mockups/](mockups/) | Three dashboard mockups (Baltic live map, Natuna illegal fishing, Hormuz energy flows) as PNG, plus standalone HTML you can open in a browser. All ships, numbers and names in them are illustrative |

The two long write-ups are exports of Claude docs owned by Jake, taken on 7 Nov 2026. If they differ from the docs, the docs are newer.

## What we'd like the agents to check

1. **Every row in [claims-to-verify.md](claims-to-verify.md).** Open the source, confirm the claim, and set the status to `confirmed`, `wrong` (with the correct value) or `unverifiable`. Several sources are secondary (news summaries, aggregator pages); prefer a primary source where one exists.
2. **The open questions** at the bottom of claims-to-verify.md. Some need a live test (for example, does AISStream actually stream Baltic data right now, and at what message rate).
3. **Feasibility of the 24-hour plan** in project-summary.md: is anything on the critical path likely to take longer than budgeted?
4. **Anything we missed:** a better free data source, a competitor we haven't listed, or a reason this won't work.

Please report findings on the board, tagging `@JakeCallcut`, and put corrections in a PR against this folder rather than editing it silently.

## Status

Idea chosen by Jake; not yet agreed by the whole team. No code written yet. Nothing in `agent/`, `web/`, `api/` or `data/` has been touched.
