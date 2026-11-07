# Open-source projects for the JetBrains track

Stars and push dates from `gh repo view` / `gh api` on 7 Nov 2026. Licences from the GitHub API (`spdx_id`). Stars are "~N (7 Nov 2026)". Licence meanings for us:
- **Permissive** (MIT, Apache-2.0, BSD): we can reuse code with attribution.
- **Copyleft** (GPL, AGPL, MPL): caution. Prefer ideas, or isolated use.
- **No licence:** ideas only. Do not copy code.

Source links are in [sources.md](sources.md#projects).

## 1. Table (22 projects, grouped)

### 1a. Frameworks, protocols and SDKs (the building blocks)

| Name | URL | Stars | Licence | Last push | What it is |
|---|---|---|---|---|---|
| JetBrains/koog | https://github.com/JetBrains/koog | ~4,653 (7 Nov 2026) | Apache-2.0 | 2026-11-07 | Kotlin/JVM agent framework. 1.0 stable (May 2026). MCP and ACP support. |
| agentclientprotocol/agent-client-protocol | https://github.com/agentclientprotocol/agent-client-protocol | ~4,592 (7 Nov 2026) | Apache-2.0 | 2026-11-07 | The ACP spec and SDKs. "A protocol for connecting any editor to any agent." |
| JetBrains/intellij-platform-plugin-template | https://github.com/JetBrains/intellij-platform-plugin-template | ~3,768 (7 Nov 2026) | Apache-2.0 | 2026-10-17 | Template for IntelliJ Platform plugins (Gradle). Use only if we build a plugin. |
| JetBrains/mcp-jetbrains | https://github.com/JetBrains/mcp-jetbrains | ~963 (7 Nov 2026) | Apache-2.0 | 2026-01-07 | MCP server for JetBrains IDEs. Its own README says the built-in server replaces it **(unverified)**. |
| JetBrains/Mellum | https://github.com/JetBrains/Mellum | ~16 (7 Nov 2026) | Apache-2.0 | 2025-07-29 | Release materials for Mellum (the earlier completion model). Mellum2 weights are on Hugging Face. |
| browserbase/stagehand | https://github.com/browserbase/stagehand | ~25,978 (7 Nov 2026) | MIT | 2026-11-07 | Browser automation SDK for agents (act, extract, observe). Self-healing steps. |
| browser-use/browser-use | https://github.com/browser-use/browser-use | ~120,243 (7 Nov 2026) | MIT | 2026-11-07 | Python library for AI browser agents, plus a hosted cloud. |

### 1b. Full developer-facing coding agents (for ideas and UI)

| Name | URL | Stars | Licence | Last push | What it is |
|---|---|---|---|---|---|
| cline/cline | https://github.com/cline/cline | ~71,438 (7 Nov 2026) | Apache-2.0 | 2026-11-07 | Autonomous coding agent: IDE extension, CLI, SDK. Plan & Act modes. |
| continuedev/continue | https://github.com/continuedev/continue | ~36,428 (7 Nov 2026) | Apache-2.0 | 2026-11-05 | Open-source coding agent and IDE extension. |
| Aider-AI/aider | https://github.com/Aider-AI/aider | ~50,004 (7 Nov 2026) | Apache-2.0 | 2026-05-22 | Terminal pair-programming agent. Git-first. |
| OpenHands/OpenHands | https://github.com/OpenHands/OpenHands | ~92,868 (7 Nov 2026) | MIT | 2026-11-07 | AI-driven development platform with sandboxed runtime. |
| RooCodeInc/Roo-Code | https://github.com/RooCodeInc/Roo-Code | ~24,241 (7 Nov 2026) | Apache-2.0 | 2026-05-15 | Editor agent with modes (Ask, Architect, Code, Orchestrator). |
| zed-industries/zed | https://github.com/zed-industries/zed | ~94,053 (7 Nov 2026) | **NOASSERTION** (mixed; verify) | 2026-11-07 | Fast editor with an agent panel. Hosts ACP registry work. Check the LICENSE files before reusing code. |
| anomalyco/opencode | https://github.com/anomalyco/opencode | ~225,178 (7 Nov 2026) | MIT | 2026-11-07 | Open-source coding agent (terminal). Large community. |

### 1c. Browser tools for developers (MCP)

| Name | URL | Stars | Licence | Last push | What it is |
|---|---|---|---|---|---|
| microsoft/playwright-mcp | https://github.com/microsoft/playwright-mcp | ~39,293 (7 Nov 2026) | Apache-2.0 | 2026-11-06 | Playwright as an MCP server. Accessibility-snapshot mode by default; `--vision` for screenshots. |
| ChromeDevTools/chrome-devtools-mcp | https://github.com/ChromeDevTools/chrome-devtools-mcp | ~54,919 (7 Nov 2026) | Apache-2.0 | 2026-11-06 | Chrome DevTools for coding agents: console, network, performance traces. Public preview since Sept 2025. |

### 1d. Agentic QA and "test the web app" projects

| Name | URL | Stars | Licence | Last push | What it is |
|---|---|---|---|---|---|
| MigoXLab/webqa-agent | https://github.com/MigoXLab/webqa-agent | ~240 (7 Nov 2026) | Apache-2.0 | 2026-07-02 | Autonomous browser agent that audits performance, functionality and UX of a web app. **Closest match to "audit a web app end to end".** |
| magnitudedev/browser-agent | https://github.com/magnitudedev/browser-agent | ~4,139 (7 Nov 2026) | Apache-2.0 | 2026-02-08 | Open-source, vision-first browser agent (per its description). Not checked for test features. |
| desplega-ai/qa-use | https://github.com/desplega-ai/qa-use | ~29 (7 Nov 2026) | MIT | 2026-09-29 | "Agent-first E2E testing CLI." One scanner rated its skill HIGH risk **(unverified)**; review before running. |
| MyNameIsEdi/open-qa | https://github.com/MyNameIsEdi/open-qa | ~6 (7 Nov 2026) | MIT | 2026-10-15 | Multi-agent Playwright framework: writes, runs and debugs tests. Small and young. |
| jimmytoan/qa-agent | https://github.com/jimmytoan/qa-agent | ~8 (7 Nov 2026) | **AGPL-3.0** (copyleft) | 2026-03-10 | QA platform for browser tests from plain-English descriptions. Ideas only. |
| browser-use/qa-use | https://github.com/browser-use/qa-use | ~607 (7 Nov 2026) | **None** | 2025-08-08 | Browser Use's open-source QA reference project. Ideas only. Not updated since Aug 2025. |
| anna-pearson/qa-agent | https://github.com/anna-pearson/qa-agent | ~1 (7 Nov 2026) | **None** | 2026-05-15 | Claude API CLI: drafts repro steps, generates and fixes Playwright tests. Ideas only. |

Not listed (no repo found): Metabase's "Repro-Bot" GitHub issue triage agent. Blog only. Source: [S-F5](sources.md#dev-tools).

## 2. Important repos, one section each

Architecture notes are from the README or docs we read. "Not researched in this pass" means we did not open the repo, so check it before building on it.

### 2.1 JetBrains/koog (Apache-2.0)
- **Architecture:** Kotlin agents built from tools, workflows (graphs of nodes), persistence, memory and observability. Targets JVM, JS, WasmJS and iOS. Needs JDK 17+. MCP client and server (Streamable HTTP), and an ACP integration for building ACP-compliant agents.
- **Reuse:** code, under Apache-2.0 with attribution. Use only if we write Kotlin.
- **Borrow:** the workflow-graph pattern for an agent that must stop and ask (the "ask only when needed" rule in the InstaLILY brief).
- **Gotchas:** we do not know the team's Kotlin level. Plus, the framework is for Kotlin and Java, not TypeScript. Source: [S-F6](sources.md#projects).

### 2.2 agentclientprotocol/agent-client-protocol (Apache-2.0)
- **Architecture:** a JSON-RPC protocol between an **editor (client)** and an **agent** over stdio. The editor starts the agent as a subprocess. Schema versioned in the repo; SDKs exist.
- **Reuse:** the spec and SDK code (Apache-2.0). The registry lists curated agents. Source: [S-A16](sources.md#ai-products).
- **Borrow:** the session/prompt/tool-call message flow for our demo UI, if we build one.
- **Gotchas:** the protocol is young and versioned. Pin the version in `package.json`. Schema changes can break us between now and Sunday.

### 2.3 JetBrains/intellij-platform-plugin-template (Apache-2.0)
- **Architecture:** a Gradle project using the IntelliJ Platform Gradle plugin. Kotlin in `src/main/kotlin`, `plugin.xml` in `src/main/resources`. Tool windows register through the `com.intellij.toolWindow` extension point. Source: [S-E1](sources.md#jetbrains-build).
- **Reuse:** the template as a starting point (Apache-2.0).
- **Borrow:** the tool-window pattern for a plan/steps panel.
- **Gotchas:** Kotlin plus Gradle first-run setup can eat hours. The Islands theme is the default since 2025.3, so plugin UI must follow it. Source: [S-E2](sources.md#jetbrains-build). Only use this if we need a real plugin.

### 2.4 JetBrains/mcp-jetbrains (Apache-2.0)
- **Architecture:** an MCP server that talks to a running JetBrains IDE. Its README (per a search summary) says the IDE's built-in server replaces it **(unverified)**.
- **Reuse:** code if we need an MCP-to-IDE bridge. Otherwise use the built-in server (Settings | Tools | MCP Server). Source: [S-A17](sources.md#ai-products).
- **Gotchas:** last pushed Jan 2026. Check it still runs before trusting it.

### 2.5 microsoft/playwright-mcp (Apache-2.0)
- **Architecture:** an MCP server that wraps Playwright. Default mode gives the model an **accessibility snapshot** of the page. Interaction tools take an element `ref` from that snapshot. `--vision` switches to screenshots. Source: [S-F1](sources.md#dev-tools) (a mirror of the README; the official repo was not read directly).
- **Reuse:** run it as-is with `npx @playwright/mcp@latest`. Code reuse not needed.
- **Borrow:** snapshot-first design. It is cheaper and more reliable than screenshots for "what can I click".
- **Gotchas:** element refs change when the page changes. Re-snapshot after each navigation.

### 2.6 ChromeDevTools/chrome-devtools-mcp (Apache-2.0)
- **Architecture:** an MCP server exposing Chrome DevTools: console messages with source-mapped stacks, network requests (for CORS issues), and performance traces (`performance_start_trace`). Announced Sept 2025 as public preview. Source: [S-F2](sources.md#dev-tools).
- **Reuse:** run as-is. Good for a "check the deployed preview for errors" feature.
- **Gotchas:** the version and status come from third-party posts **(unverified)**. Check the release page.

### 2.7 browserbase/stagehand (MIT)
- **Architecture:** a TypeScript (also Python and Go) SDK with three primitives: `act`, `extract`, `observe`. You can mix AI steps with plain Playwright-style calls. Self-healing: when an element changes, a fallback agent re-plans. Drives the browser over CDP, per the official docs. Source: [S-F3](sources.md#dev-tools).
- **Reuse:** code (MIT). Works with local Chrome too, but the docs recommend Browserbase's hosted browsers for caching.
- **Borrow:** the "deterministic steps plus AI steps" split. Freeze stable steps into plain code.
- **Gotchas:** one source says Stagehand is "fully Playwright compatible", the docs say it is not. Trust the docs. Hosted features need a Browserbase account and API key (do not put it in the repo).

### 2.8 browser-use/browser-use (MIT)
- **Architecture:** a Python library for LLM-driven browser agents, with a hosted cloud (stealth browsers, agent API). Source: repo description.
- **Reuse:** code (MIT). Python only.
- **Borrow:** the agent loop and element-index approach. Not researched in detail in this pass.
- **Gotchas:** cloud features cost money. Keep to the open-source library for a hackathon.

### 2.9 MigoXLab/webqa-agent (Apache-2.0) — closest to our idea
- **Architecture:** an autonomous browser agent that audits **performance, functionality and UX** of a web app, aimed at engineers and vibe-coders. Not researched in detail in this pass.
- **Reuse:** code (Apache-2.0). Could be the core of "audit a deployed preview end to end".
- **Borrow:** its report format, if it has one.
- **Gotchas:** small (about 240 stars). Check that it runs before we commit to it. Source: [S-F4](sources.md#dev-tools).

### 2.10 cline/cline (Apache-2.0)
- **Architecture:** an IDE extension, CLI and SDK. **Plan & Act** modes: Plan explores without changing files, Act carries out the plan. Separate models can be set per mode. Its CLI lists browser actions as auto-approvable in Act mode. Sources: [S-G1](sources.md#dev-tools).
- **Reuse:** code, Apache-2.0.
- **Borrow:** the Plan/Act split as a **visible plan gate**. This is the "plan before code" pattern the JetBrains judges will look for.
- **Gotchas:** computer-use support is claimed by a third-party guide only **(unverified)**.

### 2.11 RooCodeInc/Roo-Code (Apache-2.0)
- **Architecture:** modes with per-mode tool access. Ask (read, browser, MCP; no edits), Architect (planning; read and restricted Markdown edits, per the current docs), Code (full), Orchestrator (splits work with `new_task`, edits only mode config files). `browser_action` is in the Browser tool group. Sources: [S-G2](sources.md#dev-tools).
- **Reuse:** code, Apache-2.0.
- **Borrow:** the **mode-restricted tool access** idea. A "read-only reviewer" mode for the adaptive agent. Also the Orchestrator for splitting a bug report into sub-tasks.
- **Gotchas:** the docs disagree on Architect's edit rights. Check the code, not the docs.

### 2.12 zed-industries/zed (licence: check)
- **Architecture:** a fast editor with an agent panel. External agents run as separate processes that talk to Zed over ACP. The ACP Registry is the main install path. "Claude Agent" runs from the Agent Panel. Source: [S-G3](sources.md#dev-tools).
- **Reuse:** do **not** copy code until we read the LICENSE files. GitHub reports NOASSERTION, so the licence is mixed **(unverified)**.
- **Borrow:** the external-agent flow and "acp logs" debugging command. `dev: open acp logs` shows messages between Zed and an agent. Very useful for our own ACP agent.
- **Gotchas:** older docs describe Claude Code differently. Use the current docs page.

### 2.13 playwright / deterministic test pattern (from guides, not a repo)
- A 2026 guide recommends: **agent explores a journey once, then freeze the stable steps into plain Playwright code**. Agent runs can vary, so plain tests are the regression net. Source: [S-F7](sources.md#dev-tools). Use this pattern in our build.

### 2.14 Not researched in this pass
- **Continue (continuedev/continue)**, **Aider (Aider-AI/aider)**, **OpenHands**, **OpenCode**: named in the brief. Architecture not read. Check READMEs before any borrowing. OpenHands has a sandboxed runtime, which may be worth a look for safe browser runs.

## 3. Reuse decisions (short)

| Project | Decision |
|---|---|
| Playwright MCP | **Use as-is** for the browser tool. |
| ACP spec and SDK | **Use** to make our agent ACP-compatible. |
| Stagehand | **Borrow** the act/observe split; **use** if we need AI steps in TypeScript. |
| webqa-agent | **Evaluate in 30 min** as the core audit engine. Reuse if it runs. |
| Cline Plan & Act, Roo modes | **Borrow the idea.** Write our own. |
| Koog | **Skip** unless we write Kotlin. |
| IntelliJ plugin template | **Skip** unless we commit to a plugin. |
| qa-use, qa-agent (no licence), jimmytoan/qa-agent (AGPL) | **Ideas only.** |
| Zed | **Read the ACP docs and logs**; no code reuse until the licence is clear. |
