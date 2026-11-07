# UI design: JetBrains agents and the competition

**Method and limits:** we could not fetch JetBrains' product pages as HTML or the blog bodies in this pass (the blog returned only CSS to our tools). So JetBrains UI facts below come from docs text, search summaries and third-party reviews. **No screenshots were captured.** Before the build, open each product in the IDE and screenshot it. Source list: [sources.md](sources.md#ui).

## 1. JetBrains: how their agents look and flow

### 1.1 IDE chrome (the "native" look a plugin must match)
- **Islands theme** is the default look from IDE version 2025.3. The redesign separates the editor and tool windows more clearly, makes navigation more prominent, and improves tab visibility. Source: [S-U1](sources.md#ui).
- **Tool windows** are the panels. A plugin registers one with the `com.intellij.toolWindow` extension point, with an icon and an anchor side. Source: [S-E1](sources.md#jetbrains-build).
- **Islands plugin rules:** build custom themes from the Islands Dark or Light parent. Keep a minimum contrast ratio of 1.20:1 between tool windows or editor backgrounds and the main window. Use the Islands keys (border radius, gap between islands, island border colour). Source: [S-U2](sources.md#ui).

### 1.2 AI Assistant and Junie (inside the IDE)
- **AI Chat** is one panel. Agents from the ACP registry appear as choices next to Junie and Quick Edit. Source: [S-A15](sources.md#ai-products).
- **Junie plan mode** (`/plan` in the CLI) makes **files** the plan: requirements, design, plan and test docs. You review and edit them before Junie runs. The plan is a document, not chat text. Source: [S-A4](sources.md#ai-products).
- **Junie `/review`** reviews the current branch, the last commit, or unstaged changes. Source: [S-A4](sources.md#ai-products).
- **Junie CLI extras:** `/model` (with reasoning effort), `/remote` (browser session), `/ide` (connect to IDE), `/usage` (tokens and cost). Source: [S-A4](sources.md#ai-products).
- **Air** (multi-agent orchestrator): runs tasks in local, Docker or worktree sandboxes. The UI is not described in our sources. **(unverified)**. Source: [S-A6](sources.md#ai-products).

### 1.3 Claude Code in JetBrains (for contrast, third-party view)
- The JetBrains plugin opens changes in the **IDE diff viewer**. The VS Code version has per-change accept and reject. A diff with more than 100 changes opens without per-change buttons. Source: [S-U3](sources.md#ui). Third-party, **unverified** against an official Anthropic doc.
- The plugin is still labelled **beta** in Oct 2026. Users asked for a native GUI instead of a terminal wrapper (July 2026 feature request). Source: [S-U3](sources.md#ui).

## 2. Competitors and adjacent products

| Product | How it presents agent work | Pattern worth copying | Source |
|---|---|---|---|
| **Cline** | **Plan & Act** modes: Plan explores without editing; Act carries out the plan. The planning session context carries over. | A visible **plan gate** before edits. Separate models for plan and act. | [S-G1](sources.md#dev-tools) |
| **Roo Code** | Mode switcher (Ask, Architect, Code, Orchestrator). Each mode has a tool allow-list. Orchestrator hands sub-tasks to other modes. | **Mode-restricted tools** (a reviewer can read, not write). Sub-task breakdown. | [S-G2](sources.md#dev-tools) |
| **Windsurf / Devin Desktop** | Agent Command Center: a **Kanban board** of agent sessions, columns like Running, Waiting for Review, Done. Diff review accept or reject per file or per hunk. Secondary sources; the rebrand and Cascade's retirement are **unverified**. | A **status board** for several agents. Per-hunk accept or reject. | [S-U4](sources.md#ui) |
| **GitHub Copilot (cloud agent and VS Code)** | Session logs show each step and when Copilot hands work to a sub-agent (March 2026). VS Code plan review: approve without running, implement with Autopilot, or reject. | **Step-by-step log** with start and finish. **Approve, run, or reject** the plan. | [S-U5](sources.md#ui) |
| **Cursor (cloud agents and browser tool)** | Agents run in their own VM with a browser and produce **screenshots, videos and logs** attached to the PR. The browser tool shows its actions in the chat. Known issue: artifacts not always posted; a limit of about 100 images in long threads. | **Visual proof** attached to the output. Browser actions shown as a log. | [S-U6](sources.md#ui) |
| **Diffzu** (third-party JetBrains plugin) | Groups an AI diff into **conceptual change-sets** with risk levels and review notes. | Grouping a diff by intent, not by file. Good for "Diff Risk" ideas. | [S-U7](sources.md#ui) |
| **Explyt** (third-party) | Adds a review stage that combines an agent with JetBrains inspections on the final diff. | Reviewing **after** the agent is done, with IDE inspections. | [S-U7](sources.md#ui) |
| **Playwright MCP / Chrome DevTools MCP** | Not a UI. The agent reads an **accessibility snapshot** (Playwright) or a DevTools trace (Chrome). | For our demo, show the snapshot or the console error next to the step that used it. | [S-F1](sources.md#dev-tools), [S-F2](sources.md#dev-tools) |
| **Zed (agent panel)** | Agents run as separate processes over ACP. The Agent Panel and Threads Sidebar list agent threads. `acp logs` shows protocol messages. | A **threads sidebar** per agent. Protocol log for debugging. | [S-G3](sources.md#dev-tools) |

## 3. Patterns to cover (with where we saw them)

| Pattern | Seen in | What it looks like |
|---|---|---|
| **Layout** | Islands (JetBrains), Cursor, Windsurf | Editor centre; agent panel on one side; tool window at the bottom or side. |
| **Step timeline** | Copilot session logs, Junie plan | Vertical list of steps with status (running, done, failed) and a time for each. |
| **Live view** | Cursor cloud agent (VM), Playwright MCP | A live screenshot or snapshot of the page, updated on each step. |
| **Approvals and human-in-the-loop** | Cline Plan & Act, Copilot plan review, Junie `/plan` | Plan shown as a document; buttons: approve, edit, reject. Ask only when blocked. |
| **Diffs** | JetBrains diff viewer, Windsurf, Claude Code plugin | Side-by-side diff; per-hunk or per-file accept or reject. Group large diffs. |
| **Progress** | Copilot logs, Cursor | Counts of steps done, tokens and time used. |
| **Error states** | Cursor forum reports, Claude Code Windows bug | Show the exact step that failed and the raw error. Offer "retry this step" rather than restarting. |
| **Onboarding** | InstaLILY brief (persona choice), JetBrains plugin | One screen to pick the persona or the mode, then go. Under 60 seconds. |

## 4. Patterns we should use for a 24-hour demo

Ranked by how much they help a judge in five minutes:

1. **A plan gate.** The agent writes its plan as a short list or a file, the user approves it, then the agent runs. This is the "help the developer" story in one screen. (Cline Plan & Act, Junie `/plan`.)
2. **A step timeline with a live snapshot.** Each step shows what the browser saw (accessibility snapshot or a screenshot) and what it did. Playwright MCP's snapshot is cheap to show.
3. **Visual proof attached to the output.** The final report includes the screenshot or the video of the failing step, and the failing test. (Cursor's pattern, in a simpler form.)
4. **Per-hunk diff review** for any code the agent changes. Use the IDE's diff viewer if we build a plugin; otherwise a simple side-by-side.
5. **An error state that says what to do next.** "The login step failed on this selector. Retry, or tell the agent the expected page."
6. **Theme match.** Use Islands-like colours: a neutral grey panel, one accent colour, no heavy shadows. Keep the look native to JetBrains if we show the IDE.

Avoid: a dashboard with no action (the team rule says no dashboards), a chat box with no steps, and a live view that only shows a spinner.

## 5. Figma and design files

- No public JetBrains Figma community file was found in this pass. **Not searched in depth**. Check the Figma community for "JetBrains Islands" before the build.
