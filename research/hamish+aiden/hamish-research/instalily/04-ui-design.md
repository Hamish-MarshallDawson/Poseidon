# UI design: persona-aware coding tools

Researched 7 Nov 2026. Most product pages were read from search excerpts, not full pages. Screenshots and videos were not checked. Items marked **(unverified)** need a visual check before we copy them.

## 1. How existing tools switch behaviour per user

| Tool | How it changes behaviour | Visible switch in the UI | Refuses / holds back | Source |
|---|---|---|---|---|
| Claude Code output styles | Built-in styles: Default, Proactive, Concise, Explanatory, Learning. Explanatory adds "Insight" notes. Learning adds `TODO(human)` markers for the user to write code. | `/config` then Output style (VS Code: `/` menu). The standalone `/output-style` command was reportedly removed (sources conflict on version). | Learning asks the user to write some code; Claude does routine work | [docs](https://code.claude.com/docs/en/output-styles) |
| Zed agent profiles | Profiles are tool sets: Write (all tools), Ask (read-only), Minimal (no project tools). Set in `agent.profiles`. | Profile selector in the Agent Panel | Ask cannot edit or run commands | [Zed docs](https://zed.dev/docs/ai/agent-profiles.html) |
| Cursor modes | Agent (default), Plan, Ask (read-only), Debug. Custom modes can be built in the editor. | Shift+Tab cycles modes; mode picker in Agent panel. Each mode starts a fresh context. | Ask and Plan make no edits | [Cursor CLI docs](https://cursor.com/docs/cli/using), [Cursor help](https://cursor.com/help/ai-features/agent.md) |
| GitHub Copilot custom instructions | Repo file `.github/copilot-instructions.md`, path-specific `.github/instructions/*.instructions.md`, and a user-level file. Also reads `AGENTS.md` and `CLAUDE.md` in the CLI. | Not a persona switch: one set of rules per repo or user | Whatever the instructions say | [GitHub docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions) |
| Replit Agent Plan mode | Plan mode makes no file edits. The user reviews the plan, then selects Start building to switch to Build. Checkpoints for rollback. | Toggle in the input area (location differs between doc versions) | No edits while in Plan | [Replit docs](https://docs.replit.com/tutorials/plan-vs-build-mode) |
| Lovable Plan mode | Read-only planning. The agent asks about target user, features and design in plain language before building. | Mode switch; Build starts after approval | No changes until approval | [Lovable guide](https://lovable.dev/guides/bolt-vs-replit-vs-lovable) (vendor page; treat as marketing) |
| Bolt.new plan mode | Plan first, then user approves. Visual inspector for picking elements (about 5% of users know it, per a COO interview). | Plan toggle | Not documented | [Medium interview summary](https://hn.jakechampion.name/reader/https://angelina-yang.medium.com/bolt-news-coo-on-why-vibe-coding-is-the-wrong-word-and-what-non-technical-founders-should-d9e20ca1be7d) |
| Codecademy AI Learning Assistant | Reads the course, instructions and solution code, then gives feedback. "AI Unique Project Hints" are meant not to give away answers. Free tier: 5 prompts a day. Can be turned off from the Tools menu. | Tools menu, top right of the Learning Environment | Hints avoid the answer (engineers tuned it with example chats) | [Codecademy help](https://help.codecademy.com/hc/en-us/articles/23400751016859-AI-Features-available-on-Codecademy) |
| CS50 duck (CS50.ai) | Built on GPT-4o via Azure, with retrieval over course materials. Answers only course questions. Told not to give full answers to problem sets. | The duck chat in the course | Off-topic questions; full homework answers. Malan says it still gives code up to a quarter of the time (Gazette, 2026). | [Harvard Gazette, Sept 2026](https://news.harvard.edu/gazette/story/2026/09/taming-the-duck-for-starters/), [Harvard CS paper](https://cs.harvard.edu/malan/publications/V1fp0567-liu.pdf) |
| Khanmigo | Socratic: questions and hints, not direct answers. Coding help described in some reviews, contradicted in others. | In-exercise help | States answers only through questions (per one review) | [third-party review](https://www.kunalganglani.com/blog/khanmigo-ai-tutor-developer-education.md) (unverified; check Khan Academy's help pages) |
| Scratch / ScratchJr | Block-based: syntax errors are hard to make. Friendly design themes ("conviviality"). | Whole UI is blocks | Cannot type a syntax error | [ScratchJr design paper](https://sites.bc.edu/devtech/wp-content/uploads/sites/181/2023/07/ScratchJr-design-in-practice-Low-fl_2023_International-Journal-of-Child-Com.pdf) |

**How do they detect skill level?** Almost none do it automatically. Most rely on a mode the user picks (Zed, Cursor, Claude Code styles) or on the course the user is in (CS50, Codecademy, Khanmigo). No product found infers a beginner from the code they write. This is an opening: the agent can ask one calibration question, or read signals like error text and the code itself.

## 2. What each one refuses to do for a learner

- **CS50 duck:** will not give homework answers or off-topic help.
- **Codecademy:** hints avoid the answer.
- **Khanmigo:** questions before answers.
- **Learning style (Claude Code):** asks the learner to write some code.
- **Plan modes (Replit, Lovable, Cursor, Zed Ask):** make no edits until approved.

Nobody found refuses to write code for an engineer. The engineer persona is mostly "fewer words, more action".

## 3. Patterns for our UI

### A persona switcher

Keep it visible at all times, in the chat header, not buried in settings.

```
┌──────────────────────────────────────────────┐
│ Persona:  [ Beginner ] [ Engineer ] [ Mine ] │   ← segmented control, always visible
│ Explain depth: ●──────○──────○  (short)      │   ← slider, changes default verbosity
├──────────────────────────────────────────────┤
│ Agent: I see the loop runs 10 times, not 9.  │
│ Which number should i stop at? Tell me.      │
└──────────────────────────────────────────────┘
```

- The switch changes **tools and defaults**, not only tone: beginner gets read-only first, engineer gets full write.
- Show a line under the switcher: "Beginner: I will ask before I change your code."

### Adaptive explanation depth

- Three levels: one line, a short paragraph, a worked example.
- Start at the level of the persona. Let the user step up with one button ("show me more").
- Use the hint ladder from `05-ideas.md` and the Xiao et al. levels: orientation, next step, worked example, exact code.

### Step timeline (live view)

- Show each step as a row: read, plan, edit, test, report. Each row can open the diff.
- For the engineer, collapse rows into one line per step.
- For the beginner, expand the row and show the reason in one sentence.

### Diffs

- Always show a diff before the agent writes a file, for the beginner. For the engineer, show it after, with a one-line summary.
- Highlight the one changed line, not the whole file.

### Approvals and human in the loop

- A single approve button for each write. "Approve all" for the engineer.
- For the beginner, the agent asks for the one line they should change, as Learning style does with `TODO(human)`.

### Progress and errors

- Errors in plain words first, then the raw message in a collapsed box.
- Show what was verified: "Ran `npm test`: 4 passed, 1 failed." Never a bare "Done".

### Onboarding

- One question at start: "Are you learning, or do you want things fast?" with a skip.
- Remember the answer per project, not per person (privacy).

## 4. Patterns we should use for a 24-hour demo

1. **Persona switch on screen.** Run the same broken `for` loop three ways, side by side or in sequence.
2. **Plan gate for the beginner.** Show the agent asking the one question before it touches code (Cline and Replit pattern).
3. **`TODO(human)` line.** The beginner types the fix; the agent checks it (Claude Code Learning pattern).
4. **Minimal diff for the engineer.** One-line change shown with a test run.
5. **Honest report panel.** A box at the end: "Verified: tests run. Not verified: X." This targets stage 2.
6. **Step timeline.** Five rows, one per step.
7. **No dashboard.** The team's own rule: the main feature must carry the demo.

## Gaps

- Code.org's own error-message UI was not found. The Scratch and ScratchJr research is the nearest evidence.
- No public screenshots of Khanmigo's coding mode were checked.
- The InstaLILY product UI was not seen. Their pages did not render.
