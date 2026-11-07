# JetBrains: company and AI products (research as of 7 Nov 2026)

Scope: who JetBrains is, their AI products as of late 2026, how students get licences, and what they care about. Every non-obvious claim has a source in [sources.md](sources.md). Items marked **(unverified)** could not be confirmed from a primary source.

## 1. Who they are

- **Founded:** February 2000 in Prague, Czech Republic, by three founders (names from one secondary source: Sergey Dmitriev, Valentin Kipiatkov, Eugene Belyaev) **(unverified)**. Source: [S-C1](sources.md#company).
- **Headquarters:** Prague is the registered HQ. One source says Amsterdam is the regional HQ **(unverified)**. Source: [S-C2](sources.md#company).
- **Size:** sources disagree. Figures seen: about 1,800 (2025), about 2,800 with 11M+ recurring users, and 2,209 from a job aggregator. Their own Prague contact page says the Prague office has 170 people. **Treat headcount as unverified (roughly 2,000 people).** Sources: [S-C1](sources.md#company), [S-C3](sources.md#company).
- **Offices:** one source says 12 offices worldwide **(unverified)**. Job listings show London among AI roles (AI for Code, Research Engineer for Agentic Models). Source: [S-C4](sources.md#company).
- **London office:** the talk called it "their new London office". I found **no public article confirming the opening date**. Treat as **(unverified)**; job listings do show London roles.

## 2. Their AI products (late 2026)

| Product | What it is | Status (as found) | Source |
|---|---|---|---|
| **AI Assistant** | AI chat, completion and actions inside all JetBrains IDEs. Also runs in Android Studio and VS Code. | Current. 2026.2 docs describe ACP agents running inside its AI Chat. | [S-A1](sources.md#ai-products), [S-A2](sources.md#ai-products) |
| **Junie** | JetBrains' coding agent. Left beta in June 2026 (one source). Now has a CLI, and IDE integration runs through AI Assistant via ACP. | Shipping. Pricing is credit-based. A $25/user/month tier with 35 credits per 30 days appears on one product page **(unverified)**. | [S-A3](sources.md#ai-products), [S-A4](sources.md#ai-products) |
| **Junie CLI** | Standalone terminal agent. `/plan` writes requirements, design, plan and test files before any code is edited. `/review` reviews a branch or commit. Also `/remote`, `/ide`, `/usage`, `/model`. | Launched alongside Air (2026). Commands listed in a Japanese blog post from August 2026. | [S-A4](sources.md#ai-products), [S-A5](sources.md#ai-products) |
| **Air** | "A system of products for agentic software development." Orchestrates several agents at once. Supports Claude Agent, Codex, Gemini CLI, Junie and any ACP agent. Tasks run locally, in Docker, or in Git worktrees. | Public preview 12 March 2026 (macOS). Blog post "Introducing JetBrains Air" is dated 22 Sep 2026 (from the blog's JSON date). macOS is free. Windows and Linux are "coming soon", with no date. macOS preview needs AI Pro or Ultimate, or your own keys. | [S-A6](sources.md#ai-products), [S-A7](sources.md#ai-products) |
| **Mellum / Mellum2** | JetBrains' own open model. Mellum was for code completion. **Mellum2 (June 2026)**: 12B Mixture-of-Experts, about 2.5B parameters active per token, aimed at routing, Q&A, sub-agents and private deployment. Apache-2.0. Benchmarks are self-reported. | Mellum2 on Hugging Face. A later **Mellum2.1** (Oct 2026) is reported by one source only **(unverified)**. | [S-A8](sources.md#ai-products), [S-A9](sources.md#ai-products) |
| **Koog** | Open-source Kotlin/JVM framework for AI agents (tools, workflows, persistence, memory, observability). Apache-2.0. | **1.0 stable, announced at KotlinConf 2026 (blog 27 May 2026).** No breaking changes promised for stable modules for one year. MCP (Streamable HTTP) and ACP support. Needs JDK 17+. | [S-A10](sources.md#ai-products), [S-A11](sources.md#ai-products) |
| **Kineto** | No-code AI app builder for non-developers. | Announced Aug 2025 as early access or private preview (sources differ). Not a developer tool. | [S-A12](sources.md#ai-products) |

Notes:
- **Air, Junie CLI and the ACP story are the newest.** They are the most likely places for hackathon judges to ask "how did you use AI?". Use them in the process log (see [02-track.md](02-track.md)).
- **Kineto** is not relevant to a developer-tools entry. Do not mention it as a product to build on.

## 3. Agent Client Protocol (ACP) and "bring your own agent"

- JetBrains joined Google and Zed in backing **ACP** in October 2025. Source: [S-A13](sources.md#ai-products).
- **Beta** arrived in 25.3 release candidates (Dec 2025). Source: [S-A14](sources.md#ai-products).
- **Now** (AI Assistant 2026.2 docs): ACP agents from a **curated registry** install with no setup. Custom agents are added by config (an `acp.json` file). **You can use ACP agents without a JetBrains AI subscription.** Enterprise admins can restrict the list. Source: [S-A1](sources.md#ai-products).
- **WebStorm** (August 2026) also has ACP. Third-party agents show up next to Junie and Quick Edit. Source: [S-A15](sources.md#ai-products).
- The ACP project itself lists agents including Claude Code (via Zed's adapter), Codex CLI, Augment, Gemini CLI, GitHub Copilot CLI and OpenCode. The registry needs authentication support. Source: [S-A16](sources.md#ai-products).

**Why it matters for us:** an ACP agent we build is usable in JetBrains IDEs and in Zed, and needs no JetBrains AI subscription. That is the cheapest integration route (see [02-track.md](02-track.md), section 3).

## 4. Built-in MCP server (IDEs)

- IntelliJ-based IDEs ship an MCP server as a bundled plugin. It is off until enabled at **Settings | Tools | MCP Server | Enable MCP Server**. Source: [S-A17](sources.md#ai-products).
- The IDE's MCP server gives external agents access to the open project, with the same permissions as the running IDE. Each tool can be switched on or off under **Exposed Tools**. Source: [S-A17](sources.md#ai-products).
- **Auto-Configure** writes the connection settings for detected clients into the project's config file. Other clients get a manual config. Source: [S-A17](sources.md#ai-products).
- The separate `JetBrains/mcp-jetbrains` proxy repo is described as **deprecated** by its own README in one search summary **(unverified)**. Use the built-in server. Source: [S-A18](sources.md#ai-products).

## 5. Student and free access

- **Free tier:** "AI Free" gives unlimited code completion and local models. It gives credit-based cloud AI and Junie, plus a 30-day AI Pro trial. Source: [S-B1](sources.md#access).
- **Students and teachers:** the AI Assistant 2026.1 licence table lists a **free educational licence**. The column mapping is unclear from the snippet, so **check your JetBrains Account page** (unverified). Source: [S-B2](sources.md#access).
- **Student Pack:** free licences for IntelliJ, PyCharm, WebStorm and others for students. Source: [S-B3](sources.md#access).
- **Junie availability:** not in mainland China, not on AI Enterprise. Source: [S-B1](sources.md#access).
- **Event offer:** the talk said their coding agent is **free until the end of the year** and gave out one **OpenAI API key per team** at the booth or on Discord. That is the event offer from the slides. Its exact terms are unverified; ask at the booth.

## 6. Engineering blog, hiring and internships

- **Engineering and AI blog:** `blog.jetbrains.com/ai` (AI posts) and `blog.jetbrains.com/blog`. Recent posts we used are listed in [sources.md](sources.md#ai-products). Source: [S-C5](sources.md#company).
- **Internships:** `internship.jetbrains.com`. Listings include AI Engineering Intern (Fall 2026). Internships run 3 to 6 months, full or part time. **The Summer/Fall 2026 deadline was 16 March 2026 (from a LinkedIn post), so check whether it's still open.** Questions go to internship@jetbrains.com. Source: [S-C6](sources.md#company).
- **London roles (full-time, not internships):** Staff/Senior AI Engineer (AI for Code, In-Office), and Research Engineer (Agentic Models, remote in the UK). Source: [S-C4](sources.md#company).
- **Hackathon contact:** judges named on the Cloud9 x JetBrains Devpost page include a JetBrains person. Their names are in the source, not here. Source: [S-D1](sources.md#hackathon).

## 7. What they care about (pitch to this)

From the talk, their blog and their products:

1. **Developer productivity without losing control.** Junie's `/plan` writes a plan document the developer reviews before any code changes. Air orchestrates agents with isolated worktrees. Pitch: agents that show their plan and their work.
2. **Open standards and "bring your own agent".** ACP plus the MCP server. Pitch: we are an ACP agent or an MCP tool, not a closed plugin.
3. **Open models and open frameworks.** Mellum2 (Apache-2.0) and Koog (Apache-2.0). Pitch: run on Mellum2 locally if we can, and say so. Fits the "private deployment" story.
4. **Education.** The brief says "tools for developer education". Their workshop and student offers point the same way.
5. **Quality of the agent loop**: tests, reviews, diffs, logs. Their own hackathon advice is to read the rules and know what judges look for (see [02-track.md](02-track.md)).

## 8. Gaps (still to check)

- Junie CLI and Air changelogs after August 2026. Check `junie.jetbrains.com/docs` and `blog.jetbrains.com/air`.
- Whether the free educational licence covers AI Pro for our team members. Check each member's JetBrains Account.
- London office opening and what is in it.
- The exact OpenAI key use inside the IDE (which setting). Test at the booth.
