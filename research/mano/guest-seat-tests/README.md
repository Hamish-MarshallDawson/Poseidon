# Guest Seat feasibility tests

Saturday 7 November 2026, about 14:30. Run by Mano's agent, covering four of the five tests in section 6 of [`browser-wave/SYNTHESIS.md`](../../hamish+aiden/aiden-research/browser-wave/SYNTHESIS.md).

**Guest Seat is not decided** (board, 14:03 and 14:04). This is research for that conversation, not a go-ahead to build. Most findings apply to any project where people and agents share a browser.

Tool: `agent-browser` 0.41.2 on Chrome 156, macOS. Raw results are in `results/`.

## What this means

1. **The core mechanism works, with changes.** A small gate protected a person's edit in 20 of 20 trials, against 0 of 20 without it.
2. **Four assumptions in the synthesis need correcting** (table below). The most serious is that agents can read one-time codes during a handoff.
3. **The ERPNext test is still open.** It decides real system vs mock, and nobody holds it: Hamish's agent released it at 14:04. This machine has no Docker.
4. **None of this shows the idea is good.** It shows the parts behave as described on a stand-in portal we wrote.

## Corrections to the synthesis

| Synthesis says | Measured | Change needed |
|---|---|---|
| The agent "never sees secrets" during takeover | A one-time code typed by the person appears in the agent's snapshot in plain text. Password fields are masked; ordinary text inputs are not. | Refuse all agent reads while a lease is paused. Agents must not reach the browser directly. |
| Element refs "only work for that stamp" (our design) | The tool gives no such protection. An old ref still works after a person edits the field, and it reports success. | The gate has to enforce this. Nothing underneath will. |
| Stamp each snapshot with a digest | Hashing the raw snapshot fails: ref numbers change on every reload (`e8` became `e15`), and a ticking element caused 20 of 20 false drops. | Strip refs and hash interactive elements only (0 of 20 false drops). |
| Browser MCP schemas cost 13,700 to 18,000 tokens, "with the Playwright figure confirmed" | Playwright MCP 0.0.84: 25 tools, about 4,500 tokens. `agent-browser mcp`: 29 tools, about 17,900. | Don't quote 13.7k for Playwright without its version. See the limits on these estimates below. |

## T2: two sessions and a person on one login

Each row is one scripted run. It shows what the tool does, not how often.

| Experiment | Result |
|---|---|
| **Saved state file** | Carries the whole login to a second browser and skips MFA. The portal logs one login. Whoever holds that file holds the account. |
| **Two browsers, one form** | The second save silently erased the first agent's answer. The portal logged both saves under the same account and the **same session id**, so it cannot tell the actors apart. |
| **Two sessions, one Chrome, no pinning** | B's navigation moved A's tab. |
| **Held ref after that move** | A's fill and its Save click both reported `✓ Done` and **wrote A's answer into a different supplier's record** with the same form labels. This is the worst failure found. Refs resolve by role and name, not by page. |
| **`--pin-tab`, used as documented** | Fixes it. Sessions stay on their own tabs, share cookies, and B's attempt to take A's tab fails with `tab_locked`. |
| **Forced logout** | After being logged out, A's Save click still reported `✓ Done`. Nothing was saved. So `✓ Done` means "dispatched", not "worked", which is the case for an independent verifier. The logout itself is behaviour we coded, based on what Browserbase documents. |
| **Takeover in the same tab** | A second connection entered the code, and the agent carried on in the same session with one login event. **Scripted, so no person has tried this yet.** |

## T3: the stale-action gate

The gate re-reads the page just before acting and drops the action if the digest changed. Each extra check took about 68 ms (median, CLI).

| Case | Trials | Result |
|---|---:|---|
| Person edits in the same tab, no gate | 20 | Person's text survived 0 times |
| Person edits in the same tab, with gate | 20 | Survived 20 times, all 20 actions dropped |
| Ticking element, raw full-tree digest | 20 | 20 false drops |
| Ticking element, interactive-only digest | 20 | 0 false drops |
| Another actor saves elsewhere, tab digest only | 20 | **Their change overwritten 20 times, 0 detected**: the open tab doesn't show it |
| Same, plus a fresh reader session | 20 | 0 overwritten, 20 detected, about 280 ms per check |
| Fresh reader, nothing changed (control) | 20 | 0 false drops |
| Edit aimed at the gap between check and write | 40 | **Person's edit lost 17 times** (13 to 17 across four runs) |
| Same aimed edit, check and write as one step in the page | 40 | **Lost 0 times**: 30 refused, 10 written and then replaced by the person |
| Drop, re-read, fill only fields still owned | 1 | Person's answer kept, agent's other field filled |

- **A tab digest is not enough.** The conflict with the other side, step 8 of the workflow, needs a fresh read of the system.
- **The 17 of 40 is not a real-world rate.** We aimed the edits into a 200 ms window, and CLI latency widens the gap. It shows the race exists.
- **The atomic write only covers edits in the same tab.** It sets values directly, so it hasn't been tried on a framework-heavy UI such as ERPNext's, and it doesn't replace the fresh read.

## T4: live registers

Public pages only, loaded a handful of times each including retries, through this machine's connection. We didn't confirm that this was the venue Wi-Fi.

| Site | Result | What it means |
|---|---|---|
| **DPF list** | Worked, about 15 s to the profile. | A search for "Slack Technologies" returns **Salesforce**, with Slack behind "+12 Covered Entities"; the profile shows UK Extension: Active. Name matching alone would miss this. The URL stays on `/list`, so the evidence has to be a capture, not a link. |
| **ICO register** | Worked, about 5 s, after dismissing a cookie banner. | Searching "Wordsmith" returns two near-identical "Wordsmith AI" entries, so someone has to resolve which is which. Results also name private individuals, so raw results shouldn't go in logs or on screen. They aren't stored here. |
| **FCA register** | **Blocked** by a Cloudflare "Verify you are human" challenge on both tries. | We stopped, as the synthesis requires, and didn't click it. A person might clear it through a handoff (untested). Don't plan the demo around this site without a fallback. |

## T5: tokens

No model was called and no API key was available. These are `cl100k` tokenizer estimates of the payloads, **not billed usage**, and Claude and Gemini count differently.

| Payload | Estimated tokens |
|---|---:|
| `agent-browser mcp` tool schemas (29 tools) | 17,858 |
| Playwright MCP tool schemas (25 tools) | 4,464 |
| Draft five-tool surface (not built, and does less) | 248 |
| DPF list, one interactive snapshot | 5,972 |
| DPF list, one full tree | 10,299 |
| ICO search, one interactive snapshot | 598 |
| Stand-in portal, one interactive snapshot | 103 |

- **The stand-in badly understates real pages.** Real pages here were 6 to 58 times larger, so don't budget from it.
- **Page size matters as much as the schema.** Three reads of the DPF list cost about as much as the largest schema.
- **The `-c` flag saved nothing** on either live page.

## Not tested

- A real person doing a takeover in a visible window.
- A real model driving any of this, so real token use and whether agents recover well from a dropped action are both unknown.
- Any real portal, including ERPNext, or anything with a framework-heavy UI.
- In-process Playwright, which would have lower latency than these CLI figures.

The stand-in portal saves the whole form and has no version check. Real portals may do better or worse, so the lost-update results depend on that design.

## Run it

```bash
npm install
node t2-shared-login.mjs
node t3-stale-gate.mjs     # several minutes; N=5 node t3-stale-gate.mjs for a quick run
node t5-tokens.mjs         # makes one read each of two public sites
```

T4 was driven by hand and has no script. Tests use their own `agent-browser` namespace and temporary profiles, not your Chrome profile.
