# JetBrains track: "Help the Developer" (Gold, €350 per member)

Source for the brief and rules: the team's induction summary ([SlideSummaryFromTranscription.MD](C:\Users\hamis\Documents\GitHub\Hacktheburgh\research\InductionPresentations\SlideSummaryFromTranscription.MD), section 3.4). Source list: [sources.md](sources.md).

## 1. The brief, restated

- **Challenge:** "Help the Developer". Deliberately vague. JetBrains' advice: **build something you would use yourself**. Scope they named: tools for developer education, AI that works alongside development, anything in software development.
- **Process requirement (hard):** the agentic development must happen **inside JetBrains IDEs, using AI**. Judges will ask how we used AI to code, and they prefer that we did it through their tools.
- **Judging:** five criteria, in a document behind a QR code at the JetBrains booth and posted on Discord. **Not read yet.** See section 4.
- **Prizes:** €350 per member for first, €150 per member for second.
- **Rules that apply to every track (summary file, section 2):** one codebase; only work built during the hackathon (start a fresh repo after 12:00 Saturday); open-source allowed if licences are followed; AI use must be disclosed and explained; keep a running log of AI use.
- **Timing:** JetBrains workshop 16:00 Saturday (Larch Lecture Theatre). Submission 12:00 Sunday. Demos from 12:30 Sunday.

## 2. Process requirement: setup checklist (do this first, in the first hour)

Goal: every team member can show an AI-assisted commit made from inside a JetBrains IDE, and we can show the log.

1. **Pick the IDE for the stack.**
   - TypeScript or JavaScript (Aiden's stack): **WebStorm**.
   - Python: **PyCharm**.
   - Anything else or mixed: **IntelliJ IDEA**.
   - Install from the JetBrains Toolbox. Confirm the licence on the JetBrains Account page (free educational licence for students, see [01-company.md](01-company.md), section 5).
2. **Sign in** to the JetBrains Account inside the IDE (Settings | Tools | AI Assistant, or the account icon). Confirm the AI Free tier or AI Pro is active.
3. **Enable AI Assistant** and **install Junie** from the Marketplace (Settings | Plugins). Junie is also a standalone CLI (`junie`), useful for `/plan` and `/review`.
4. **Connect an ACP agent** (optional, but strong for the "bring your own agent" angle): open AI Chat, choose an agent from the registry (no JetBrains subscription needed, per the 2026.2 docs). Source: [S-A1](sources.md#ai-products).
5. **Turn on the MCP server** if we want the IDE's tools for an external agent: Settings | Tools | MCP Server | Enable MCP Server, then Auto-Configure. Source: [S-A17](sources.md#ai-products).
6. **OpenAI API key (one per team, from the booth or Discord):**
   - Store it only in an environment variable or the IDE's password store. **Never commit it.** The slides say GitHub blocks committed keys.
   - Add `.env` to `.gitignore` before the first commit.
   - Check which setting takes a custom OpenAI key in Junie or AI Assistant (bring-your-own-key option). **(unverified: exact menu path; test at the booth.)**
7. **Create the process log** at `AI_LOG.md` in the repo root on the first commit (see section 5).
8. **Make one test commit** from an AI session inside the IDE, so we know the whole loop works before the build starts.

## 3. Building for JetBrains IDEs: effort and cheapest route

Three routes. Recommendation at the end.

| Route | What we build | Effort for a 24 h team | Works in | Notes |
|---|---|---|---|---|
| **A. IntelliJ plugin** | A Kotlin plugin with a tool window and actions. Uses the IntelliJ Platform plugin template (Gradle, Apache-2.0). | High. Kotlin plus Gradle, plus learning the IntelliJ Platform SDK. Our team has no Kotlin on record. Estimate: most of the day lost to setup and UI plumbing **(estimate, not sourced)**. | JetBrains IDEs only. | Tool windows register through the `com.intellij.toolWindow` extension point in `plugin.xml`, and a `ToolWindowFactory` builds the UI. Source: [S-E1](sources.md#jetbrains-build). Plugins must support the Islands theme, which is the default since 2025.3. Source: [S-E2](sources.md#jetbrains-build). |
| **B. ACP agent** | A TypeScript (or Python) program that speaks ACP over stdio. The IDE's AI Chat launches it. | Low to medium. We already know TypeScript. ACP is a small JSON-RPC protocol. Official Zed and ACP libraries exist. | Any ACP host: JetBrains AI Chat (2026.2+), Zed, others. | No JetBrains subscription needed to use ACP agents. Config goes in `acp.json`. Source: [S-A1](sources.md#ai-products), [S-E3](sources.md#jetbrains-build). Risk: ACP details could change; pin a version. |
| **C. MCP server** | A small MCP server (TypeScript, Python or Kotlin SDK) with our tools (for example "open this URL and run this step", "run this test"). | Low. Many examples. | Any MCP host, including the IDE's built-in MCP server and Junie. | The IDE's built-in MCP server exposes IDE actions to external agents, and our server adds browser tools. Source: [S-A17](sources.md#ai-products). Playwright MCP is a ready-made option. Source: [S-F1](sources.md#dev-tools). |
| **D. Standalone CLI** | A CLI our agent runs in the IDE terminal. | Lowest. | Any terminal, including the IDE terminal. | Does not count as "inside the IDE" unless the judges see it used from the IDE. Keep it as a fallback. |

**Recommendation: B plus C.** Build the agent as an **ACP agent** in TypeScript, and give it our browser tools over **MCP** (Playwright MCP or our own). Then the demo shows the agent running inside the JetBrains AI Chat, which is the process requirement, without writing any Kotlin. Keep the plugin route only if the team has a Kotlin dev with time. Use route D as the fallback if ACP fails on the day.

Other useful facts:
- **Koog** is JetBrains' Kotlin agent framework (Apache-2.0, 1.0 stable). It only helps if we are writing Kotlin. For TypeScript it adds nothing. Source: [S-A10](sources.md#ai-products).
- **Air** orchestrates several agents in isolated worktrees. It is macOS-only for now, and the preview needs AI Pro or Ultimate or our own keys. It is a good demo of "agents at scale", not a build target. Source: [S-A6](sources.md#ai-products).
- The **Claude Code JetBrains plugin** wraps the CLI in the IDE terminal and opens diffs in the IDE's viewer. It is beta, and there is a known Windows issue (native terminal and Git Bash). Source: [S-E4](sources.md#jetbrains-build). Do not build on it; use it only as a reference.

## 4. Judging: what we know and what we don't

- **We have not read the JetBrains judging criteria.** The five criteria are behind the booth QR code and on Discord. **Action: read them at the workshop (16:00) or before, and paste the five criteria into section 4.1.**
- **Public search:** I looked for a public version of JetBrains' 2025 to 2026 judging criteria. **Nothing matched "Help the Developer".** The closest public material is from **other events**:
  - The Cloud9 x JetBrains "Sky's the Limit" hackathon (late 2025 to 2026, Devpost). Its judging section starts with **"Technological Implementation"** and the rest was cut off in search. Judges included JetBrains staff and two Cloud9 staff. **From other events. Not JetBrains HackTheBurgh criteria.** Source: [S-D2](sources.md#hackathon).
  - JetBrains' own blog post "How to Win a Hackathon: Notes From the Judging Table" (June 2026). I could not read its body, but its headline suggests judging advice. **From JetBrains, not from this event.** Source: [S-D3](sources.md#hackathon).
- **Assumption, not sourced:** a reasonable working guess is that the five criteria cover technical quality, the "help the developer" fit, a working demo, AI-use transparency, and originality. Confirm before relying on it.

### 4.1 Criteria (to fill from the booth document)

| # | Criterion (from booth/Discord doc) | Weight | How our project scores on it |
|---|---|---|---|
| 1 | _to fill_ | _to fill_ | _to fill_ |
| 2 | _to fill_ | _to fill_ | _to fill_ |
| 3 | _to fill_ | _to fill_ | _to fill_ |
| 4 | _to fill_ | _to fill_ | _to fill_ |
| 5 | _to fill_ | _to fill_ | _to fill_ |

## 5. "How we used AI" log (judges will ask)

Keep `AI_LOG.md` in the repo root, one entry per AI session, and commit it with the code.

Each entry:
- **When:** date and time.
- **Who:** team member (use role or first name, not a login).
- **Tool:** AI Assistant, Junie, Junie CLI, ACP agent name, or outside tool (say which).
- **Model:** as shown in the tool.
- **Task:** one line.
- **What it did:** files touched, commands run, tests run (paste the summary line).
- **What we changed by hand:** one line. This matters most. Judges want to see human judgement.
- **Commit hashes** that came out of the session.

Also keep 2 to 3 screenshots of the IDE with the AI panel open, for the write-up.

## 6. What will impress these judges

- A **working demo inside the IDE**, with the AI panel visible. Not a slide.
- The agent **shows its plan** before changing code (Junie's `/plan` model: plan as a document the developer reviews). This is the clearest "help the developer" story.
- **Honest scope.** A tool that says what it could not check. Matches the JetBrains "build for yourself" framing.
- **Open standards** (ACP, MCP) and **open models** (Mellum2 under Apache-2.0, if we can run it). Shows we use the ecosystem they are building.
- A **developer-education** angle that is real, for example: the agent explains the failing test and asks the developer a question before it fixes it.
- Clear **AI log** with hand edits shown.

## 7. What will lose

- Writing a plugin from scratch with no Kotlin and no time to test it. Risk of a demo that does not run.
- A **wrapper around a chat box**. The brief says "build something you would use yourself", so a plain chat UI will look thin.
- A tool that works only outside the IDE, with no clear process log. Fails the process requirement.
- Hiding AI use. The brief asks us to disclose it.
- Using a key or a model we did not get legitimately (the key must come from the booth).
- Scope so big the demo is partial. Keep to one main feature (team rule: the main feature carries the demo alone).

## 8. How the baseline agentic browser scores on this track

The baseline is a **Wordsmith-track agentic browser**: an agent that completes a complex end-to-end task in a real browser.

- **Fit with "Help the Developer":** good, if the browser agent serves **developers**, not shoppers. Examples: reproduce a bug report in a browser and write a failing test; audit a deployed preview end to end; check a docs page against the code. See [05-ideas.md](05-ideas.md).
- **Fit with the process requirement:** good, if the browser agent runs as an **ACP agent or MCP tool** used from the JetBrains AI Chat, and the demo shows it in the IDE.
- **Score estimate (our judgement, not sourced):** strong on "AI that works alongside development" and "tools for developer education" if it is built as a bug-repro or test-writing helper. Weak if it is a generic browser agent with no developer hook.
- **Overlap:** the same codebase can enter Wordsmith (complex browser workflow) and JetBrains (developer tool), as long as the JetBrains entry is the IDE-facing layer on top.

## 9. Unknowns still to check

- [ ] Read the five JetBrains criteria (booth QR or Discord). Fill section 4.1.
- [ ] Confirm the JetBrains judging slot time and who attends. The whole team must attend.
- [ ] Check which setting takes the OpenAI key in Junie or AI Assistant. Test it at the booth.
- [ ] Confirm each member's free educational licence on the JetBrains Account page.
- [ ] Test ACP with one agent in AI Chat before 12:00 Sunday. Check the `acp.json` format on the day.
- [ ] Decide between route B+C (recommended) and A (plugin), by 13:00 Saturday.
- [ ] Read the "How to Win a Hackathon" blog body, which we could not fetch.
