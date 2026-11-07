# UI design for agentic browser work

Researched 7 Nov 2026. Most product UIs were read from search snippets and product pages, not screenshots. Where we describe a layout we could not see, it is marked **(from text, not seen)**. Screenshots and videos to check are listed in section 5.

## 1. How Wordsmith presents its own work

Wordsmith's product is not a browser. Its UI is a legal-request flow plus a Word add-in. Still, these patterns are what their buyers see, so a judge will expect a demo to fit them.

### 1a. The four-step flow (homepage)
Their homepage shows one clean path: **Receive → Route → Resolve → Record**. Each step has its own card, and the example is a Slack message on the left, then the triage result, then the drafted output.
- **Receive:** a request card with the sender, the time ("1 minute ago") and the raw message.
- **Route:** tags for priority ("High Priority"), risk ("Revenue Critical", "Multi-jurisdiction") and the assignee ("Routed to Senior Commercial Counsel").
- **Resolve:** a list of context sources pulled in (Salesforce, Slack, Ironclad) and the actions taken ("Redline drafted against your playbook", "Termination notice flagged").
- **Record:** the output sent back to where the work lives ("Alice gets the redline in Slack").

Source: [wordsmith.ai index.md](https://www.wordsmith.ai/index.md). This is text from the page. We did not view the step images.

**Why it matters:** the four steps are a ready-made structure for a demo. Our browser agent can use the same four labels.

### 1b. Word add-in (sidebar review)
Per product pages (via search snippets):
- Playbook review runs on the open document. Issues are flagged inline.
- Redlines appear as tracked changes.
- A sidebar lets the reviewer accept, reject or improve each redline without leaving the document.
- Each suggestion shows its reasoning, with citations.
- Clauses can be inserted from an approved library.

Sources: [Word integration page](https://www.wordsmith.ai/integrations/word), [playbooks product page](https://www.wordsmith.ai/product/playbooks) (both via search snippets; not viewed as screenshots).

### 1c. Slack-native
Requests, questions and approvals happen inside Slack. The Slack customer story says Wordsmith responds in the same place. [Slack customer story](https://slack.com/intl/en-gb/customer-stories/wordsmith-story)

### 1d. What is not visible
We found no public screenshot of an agent "run" view (live browser, step timeline or token counter) from Wordsmith. Their product is not browser-based, so this is expected.

## 2. How competing and adjacent products present browser agents

### 2a. Browser Use Cloud: live view and human takeover
- A live view URL shows the remote browser. A person can open it, complete a step the agent cannot (a login, a CAPTCHA, a choice), and then hand back. The agent resumes in the same session.
- Their doc says human-in-the-loop is "useful whenever a person should handle a sensitive or complex step, not only after failures."
- Source: [human takeover docs](https://docs.cloud.browser-use.com/tips/live-view/human-takeover) (read through search snippet).

**Pattern:** "take over" button on the live view, and a resume button. Keep the session alive while the human acts.

### 2b. Cloudflare Browser Run: Human in the Loop
- The operator opens the Live View URL, completes the action, then selects **"Done"** or **"Failed"**. The script is notified when the handoff ends, or when it times out.
- Source: [Cloudflare developer docs](https://developers.cloudflare.com/browser-run/features/human-in-the-loop/index.md) (search snippet).

**Pattern:** explicit "Done / Failed" outcome buttons after a takeover. Clear outcome, not just "continue".

### 2c. Nanobrowser: Chrome side panel
- A persistent side panel in Chrome holds the chat. The panel shows live status and step-by-step progress.
- Modes: **Ask** (asks before acting) or **Auto**. Per-site rules decide which sites are allowed to act automatically.
- Several tasks run at once, each in its own tab group.
- Asks before it submits, sends or posts. Source: [Nanobrowser README](https://github.com/nanobrowser/nanobrowser) (fetched via gh API, part of the README).
- Chrome Web Store listing describes the side panel as giving real-time status updates. [listing](https://chromewebstore.google.com/detail/nanobrowser/imbddededgmcgfhfpcjmijokokekbkal)

**Pattern:** side panel for chat, per-site permission, Ask/Auto switch, progress in the panel, export at the end.

### 2d. Claude for Chrome: side panel with site permissions
- Side panel in Chrome. Users can grant or revoke a site's access at any time in settings.
- Admins on team and enterprise plans set org-wide allowlists and blocklists.
- Anthropic advises **not** using the extension on sites with financial, legal or medical information. Relevant for us because our demo is legal.
- Sources: [Anthropic: Claude for Chrome](https://www.anthropic.com/news/claude-for-chrome), [Piloting Claude in Chrome](https://claude.com/resources/articles/claude-for-chrome) (search snippets).

**Pattern:** site allowlist per domain, and an admin view. Say on screen which domains the agent can act on.

### 2e. Perplexity Comet, Gemini in Chrome (Auto Browse), Dia
- **Comet:** described as the most agentic of the group in one comparison; sources disagree on whether it is free (search summaries). **(unverified)**
- **Gemini in Chrome, Auto Browse:** described as a limited US-preview feature; launch date and tier are reported differently across sources. **(unverified)**
- **Dia:** described as supervised, leaning toward assisted browsing rather than autonomous action. **(unverified)**
- Sources: [TechRepublic best AI browsers 2026](https://www.techrepublic.com/article/news-best-ai-browsers-2026/), [Dev.to landscape piece](https://dev.to/docdavkitty/the-agentic-browser-landscape-in-2026-comet-atlas-dia-and-the-war-for-the-ai-native-browser-flm) (search snippets).

We did not see the UIs of these products. Their layouts are not described in enough detail here to copy.

### 2f. Skyvern: visual workflow builder
- Skyvern has a visual, no-code builder for multi-step workflows, per search snippet. **(from text, not seen)**
- Source: [Skyvern docs and repo](https://github.com/Skyvern-AI/skyvern) (AGPL, look but do not copy).

**Pattern:** a node-and-edge workflow view. Useful for showing the "end-to-end" structure of our agent.

### 2g. workflow-use: record and replay
- Record a human run, turn it into a workflow, replay with variables. [repo](https://github.com/browser-use/workflow-use) (AGPL).

**Pattern:** "record once, replay many" with a visible replay count and a token figure per run.

## 3. Patterns, by what each one solves

| Need | Pattern | Seen in |
|---|---|---|
| See what the agent is doing | Live browser view next to chat | Browser Use Cloud, Cloudflare Browser Run |
| Let a person take over | Live view URL with "take over" and "Done / Failed" buttons | Browser Use Cloud, Cloudflare |
| Ask before acting | Ask/Auto mode; approval before submit or send | Nanobrowser, Claude for Chrome (per-site) |
| Control where it can go | Per-site allowlist and blocklist, admin view | Claude for Chrome, Nanobrowser |
| Show progress | Step list in side panel with status per step | Nanobrowser, Browser Use Cloud |
| Show provenance | Each suggestion carries its reasoning and citations | Wordsmith Word add-in |
| Show the flow end to end | Four-step card flow (Receive, Route, Resolve, Record) | Wordsmith homepage |
| Reuse a successful run | Record once, replay many; caching | workflow-use, Stagehand |
| Show cost | Tokens and cost per run, per step | Not seen in any product we checked. An opportunity. |

## 4. Patterns we should use for a 24-hour hackathon demo

Our target is a judge who knows Wordsmith's four-step flow and wants to see an agent finish a legal task in a real browser, with proof of where every fact came from and a human gate before anything is sent. The judges also score tokens and cost.

Recommended screen layout (desktop, one screen, projected):

1. **Left column (about 25%): request and steps.** The request (Receive) at the top. Below it, a vertical step timeline using Wordsmith's own labels: Receive, Route, Resolve, Record. Each step shows a status icon (running, done, waiting for approval, failed), the duration, and tokens used.
2. **Centre (about 45%): live browser view.** A screenshot stream of the browser the agent is driving, updated per step. Highlight the element being acted on. Show the current URL in a bar above it.
3. **Right column (about 30%): evidence and approval.**
   - Top: a running **token and cost meter** (tokens in, tokens out, model name, cost so far). This is the tie-breaker, so make it always visible.
   - Middle: the **facts list**. Each fact has a value, a source URL, a timestamp and the step that found it. Clicking one jumps to the step.
   - Bottom: the **approval card**, shown when the agent reaches an action that changes something. It states the exact action in plain words (for example "Send this 2-page due-diligence memo to #legal-intake in Slack. Contains 14 facts, 3 flagged as unverified."), with **Approve**, **Edit** and **Stop** buttons.
4. **Footer:** "Stop", "Take over" (hand the live browser to a person, then "Done" or "Failed"), and a switch for Ask or Auto mode.

**Patterns to include, with a reason:**
- **Human takeover with explicit "Done / Failed".** Shows the agent is not a black box, and covers the unsolved login or CAPTCHA problem live.
- **Approval card with the exact action.** Avoids a generic "Continue?", which tells the approver nothing. Our notes and search guidance both say approval prompts must be specific.
- **Per-domain allowlist shown on screen.** Matches Claude for Chrome and Nanobrowser, and answers privacy questions in one glance.
- **Provenance on each fact.** Matches Wordsmith's "trust" and "record" messaging.
- **Live token and cost counter.** Nobody else in the research does this clearly. It scores the tie-breaker.

**Patterns to avoid:**
- A dashboard with no action. Our notes say "no dashboards, no wrapper plus a dashboard." The demo must be the agent doing the work.
- Animated spinners with no step names. Show the step name.
- Long, unlabelled logs. Show a summary; keep the raw log behind a "details" toggle.
- A chat-only UI. A judge cannot see the browser working.

**Error states to design for (demo insurance):**
- **Blocked by a site (CAPTCHA, bot check, login):** show "Needs you" with a takeover button, not a red error.
- **Element not found:** show the retry count and the fallback taken.
- **Source down or rate-limited:** show which source failed and that the fact is marked "not checked", not silently dropped.
- **Approval timed out:** the action does not run. State it.

**Onboarding (for judges, one screen):** one sentence of what the agent does, one example request to load, and a "what runs where" note (which data leaves the machine, which model, which domains).

## 5. Links to check (screenshots, videos, galleries)

Not all of these were viewed. Check them before the build.

- Browser Use Cloud docs, live view and human takeover: https://docs.cloud.browser-use.com/tips/live-view/human-takeover
- Cloudflare Browser Run, Human in the Loop: https://developers.cloudflare.com/browser-run/features/human-in-the-loop/index.md
- Nanobrowser Chrome Web Store page (screenshots): https://chromewebstore.google.com/detail/nanobrowser/imbddededgmcgfhfpcjmijokokekbkal
- Claude for Chrome: https://www.anthropic.com/news/claude-for-chrome
- Wordsmith homepage (flow images): https://www.wordsmith.ai/
- Wordsmith Word integration: https://www.wordsmith.ai/integrations/word
- Magentic-UI repo (screenshots in README, not read): https://github.com/microsoft/magentic-ui
- Skyvern repo (workflow builder screenshots, AGPL): https://github.com/Skyvern-AI/skyvern
- Figma community: not searched. (unverified: any browser-agent UI kit)

## 6. Notes

- Most "product" evidence here comes from marketing copy or search snippets. We did not capture screenshots this session. Treat the layouts in section 4 as our recommendation, not as a copy of any one product.
- We did not verify any competitor's UI against its current release. Claims that a feature exists are as stated by the vendor or a secondary source.
