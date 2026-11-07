# Relevant open-source projects

Stars and dates from `gh repo view` on 7 Nov 2026. Format: "~N (7 Nov 2026)". Licences are the GitHub-reported SPDX identifier. Our rule (from `common.md`): permissive (MIT, Apache-2.0, BSD) means we can reuse code with attribution. Copyleft means ideas only, or isolated use. No licence means ideas only.

## Table

| Name | URL | Stars | Licence | Last push | What it is |
|---|---|---|---|---|---|
| Codex CLI | https://github.com/openai/codex | ~133,548 (7 Nov 2026) | Apache-2.0 | 2026-11-07 | Lightweight terminal coding agent. Good reference for approvals and sandbox modes. |
| Claude Code | https://github.com/anthropics/claude-code | ~154,864 (7 Nov 2026) | none in GitHub metadata | 2026-11-06 | Terminal agent. Has output styles (Explanatory, Learning). **Ideas only** until its licence is confirmed. |
| Aider | https://github.com/Aider-AI/aider | ~50,004 (7 Nov 2026) | Apache-2.0 | 2026-05-22 | Terminal pair programmer with edit formats (whole, diff, udiff). Reference for minimal diffs. Last push is older than the others. |
| OpenHands | https://github.com/OpenHands/OpenHands | ~92,868 (7 Nov 2026) | MIT | 2026-11-07 | Full AI software-development platform. Reference for a sandboxed agent loop and UI. |
| Cline | https://github.com/cline/cline | ~71,438 (7 Nov 2026) | Apache-2.0 | 2026-11-07 | Autonomous coding agent for the IDE. Plan and Act modes. Reference for mode split. |
| Continue | https://github.com/continuedev/continue | ~36,428 (7 Nov 2026) | Apache-2.0 | 2026-11-05 | Open-source coding agent for IDE and CLI. Reference for rules and config per project. |
| opencode | https://github.com/anomalyco/opencode | ~225,178 (7 Nov 2026) | MIT | 2026-11-07 | "The open source coding agent". Terminal agent. |
| SWE-agent | https://github.com/SWE-agent/SWE-agent | ~20,748 (7 Nov 2026) | MIT | 2026-11-02 | Takes a GitHub issue and tries to fix it (NeurIPS 2024). Reference for an agent-computer interface and evaluation loop. |
| SWE-bench | https://github.com/SWE-bench/SWE-bench | ~6,157 (7 Nov 2026) | MIT | 2026-09-18 | Benchmark and Docker-based evaluation harness for patches. Model for our hidden-test design. |
| browser-use | https://github.com/browser-use/browser-use | ~120,244 (7 Nov 2026) | MIT | 2026-11-07 | Python library for AI browser agents. Our baseline's obvious base. |
| Playwright MCP | https://github.com/microsoft/playwright-mcp | ~39,293 (7 Nov 2026) | Apache-2.0 | 2026-11-06 | MCP server that gives an agent a browser. Use to show a beginner a page or verify a web change. |
| MCP reference servers | https://github.com/modelcontextprotocol/servers | ~91,848 (7 Nov 2026) | "Other" (check each folder) | 2026-11-05 | Reference MCP servers (filesystem, git, fetch and more). Check each server's own licence before reuse. |
| Scratch Blocks | https://github.com/scratchfoundation/scratch-blocks | ~2,770 (7 Nov 2026) | Apache-2.0 | 2026-11-05 | Block-based editor library behind Scratch. Reference for a beginner UI. |
| InstaLILY edge-connector | https://github.com/Instalily/edge-connector | 0 (7 Nov 2026) | Apache-2.0 | 2026-11-06 | InstaLILY's outbound connector for customer networks. Shows how they reach client systems. Not needed for the track. |
| InstaLILY lily-pr-demo | https://github.com/Instalily/lily-pr-demo | 1 (7 Nov 2026) | none | 2026-10-05 | Demo of Lily opening real pull requests on a backlog board. Shows the target behaviour of an "engineer that opens PRs". Ideas only. |

Not checked by `gh`: CS50's duck (`cs50/cs50.ai` did not resolve), Aider's benchmark repo (did not resolve). No public repo was found for CodeHelp or the Stanford Tutor CoPilot work.

## Groups

### 1. Terminal and IDE coding agents (references for the engineer persona)

**Aider** (Apache-2.0, reuse allowed with attribution)
- Architecture: a `Coder` subclass per edit format. Each format pairs a prompt bundle with a parser and applier (per a third-party write-up). Whole-file is simplest for the model but costs more tokens. Diff and udiff formats are more efficient.
- Reuse: the diff applier and its error-retry loop (the parse error goes back to the model). Check the code before copying.
- Borrow: the idea of picking an edit format per model. For us, the minimal-diff rule.
- Gotchas: it is an edit tool, not a tutor. Its output is terse by default, which is what the engineer persona needs. Lightly maintained recently (last push May 2026): check the licence header in any file you copy.

**Codex CLI** (Apache-2.0)
- Architecture: a terminal agent with a sandbox and approval modes. Sources disagree on mode names (read-only, auto, full access vs read-only, workspace-write, danger-full-access). Check the current docs before design.
- Reuse: the approval and sandbox model is worth copying as a concept. Code reuse is allowed (Apache-2.0).
- Borrow: `AGENTS.md`-style project instructions loaded in order from the repo root and the working directory. Closer files win.
- Gotchas: large project. Read only the parts you need.

**Claude Code** (no licence in GitHub metadata)
- Architecture: terminal agent with output styles. Explanatory adds "Insight" notes. Learning adds `TODO(human)` markers that the user fills in.
- Reuse: none. Ideas only.
- Borrow: the `TODO(human)` pattern. The beginner writes the key line; the agent checks it. This is a strong persona mechanic.
- Gotchas: output styles make responses longer, which costs tokens (per the docs).

**Cline** (Apache-2.0)
- Architecture: Plan and Act modes in the IDE. The agent plans first and waits before changing files.
- Reuse: allowed with attribution.
- Borrow: a plan-then-act gate for the beginner persona: the agent proposes, the user says go.

**Continue** (Apache-2.0)
- Architecture: open-source agent for IDE and CLI, configured per project with rules.
- Borrow: per-project rules files as the way to set a persona or a skill level.

**opencode** (MIT)
- Architecture: open terminal agent. Read it for how its tool calls and sessions are structured.
- Reuse: allowed with attribution.

**OpenHands** (MIT)
- Architecture: sandboxed agent platform with a web UI. Good reference for showing a live step timeline.
- Gotchas: large. Use only as a UI reference.

### 2. Evaluation and hidden-test harnesses

**SWE-bench** (MIT)
- Architecture: Docker containers per instance. Apply the candidate patch, run tests, record pass or fail. Images come from DockerHub by default. A local build flag exists for ARM machines.
- Resources: the repo recommends at least 120 GB free disk, 16 GB RAM, 8 CPU cores. Too heavy for a 24-hour laptop run. Use a small subset.
- Reuse: the harness pattern. Build a small version: a task folder, a test command, a pass or fail summary.
- Gotchas: caching by run ID means a rerun returns old results. Use a new run ID each time.

**SWE-agent** (MIT)
- Architecture: takes a GitHub issue, runs an agent in a container. Its "agent-computer interface" limits what the agent can see and do per step.
- Borrow: limit the tool surface per persona. A beginner gets fewer tools (no shell writes); an engineer gets all.

### 3. Browser and tool layer (for the baseline fit)

**browser-use** (MIT)
- Architecture: Python library that drives a browser from an LLM. Plugs into the baseline agentic browser.
- Reuse: allowed. Good for the optional browser proof step.
- Gotchas: browser agents are slow and brittle live. Keep it behind a flag.

**Playwright MCP** (Apache-2.0)
- Architecture: an MCP server exposing browser actions as tools (click, type, snapshot).
- Reuse: allowed. Use it to open a page and capture a screenshot for the beginner, or to verify a web change for the engineer.
- Gotchas: each action returns a page snapshot. Watch the context size.

**MCP reference servers** (Other)
- Architecture: reference MCP servers. Check each folder's licence.
- Borrow: the idea of exposing repo and docs tools as MCP tools that a persona can switch on or off.

### 4. Beginner UI

**Scratch Blocks** (Apache-2.0)
- Architecture: block-based editor library. Reuse is allowed with attribution.
- Borrow: the cue style and friendly feedback. Not useful for a text IDE unless we add a block view for the loop example.
- Gotchas: heavy dependency. Probably not worth it in 24 hours.

### 5. InstaLILY's own repos (context only)

**lily-pr-demo** (no licence, 1 star)
- Architecture: a backlog board showing Lily's open pull requests.
- Use: a picture of the target "agent that opens PRs" flow. Do not copy code (no licence).

**edge-connector** (Apache-2.0, 0 stars)
- Architecture: outbound-only connector and hub. Not relevant to the track.
- Use: confirms they care about secure, outbound-only access to client systems. Mention in the pitch if asked.

## Recommended shortlist for a 24-hour build

1. **Aider** (edit formats, minimal diffs) for the engineer persona.
2. **Claude Code** learning pattern (`TODO(human)`) as an idea for the beginner persona.
3. **Cline** plan-then-act gate as an idea for the beginner persona.
4. **SWE-bench** harness pattern to build a tiny local hidden-test runner.
5. **Playwright MCP** only if the browser proof step is kept.
