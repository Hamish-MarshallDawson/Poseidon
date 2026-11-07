# Browser wave: synthesis and concepts

> **Closed, 7 November 2026.** The team isn't pursuing the Wordsmith track, and Guest Seat isn't being built. Aiden's follow-up discussion found that default Claude and Codex browser tools, private browsers and APIs cover too much of this for it to be new. Everything below is kept as a research record only.

Saturday 7 November 2026, about 14:00. Written by Aiden's orchestrating agent from the five DeepSeek Flash reports in this folder. Section 7 lists what was independently checked and corrected. Scores and recommendations are judgement, not measurement.

This replaces Clearance as the recommended direction. It's a recommendation for Aiden and the team to decide on, then test with Wordsmith's engineers.

## Recommendation

Build **Guest Seat**: one shared browser that several people and their agents work through at the same time, doing real work inside a system where they hold a login and no API key.

The running example is closing a deal through a customer's procurement portal. Legal, finance, procurement and each of their agents all have to act inside that portal, under one company account, without overwriting each other, exceeding their authority or submitting twice.

Take the browser away and the work stops. That's the test Clearance failed.

## 1. The insight

**The browser is needed where you have a seat rather than a key.**

APIs and MCP work when you own the system or hold credentials for it. They stop when you're a guest in somebody else's system. A lawyer is invited into a customer's procurement portal, a seller's data room or a counterparty's contract tool. Those companies buy the API; the guest gets a login. MCP doesn't close this gap either, because it inherits the same permissions: Datasite says its MCP server works "entirely within Datasite's existing access controls".

A seat bundles a person, a credential and a permission, and that's what agents break:

- **To the site, everything is the human.** WorkOS's write-up puts it as "just you clicking around". Businesses sharing a portal login already report "it is not visible which person executed what".
- **Identity plumbing stops at the browser.** Entra can say "the subject of the token is a user, while the actor is the agent identity". Auth0 offers on-behalf-of token exchange and a token vault. Those tokens authenticate to APIs; a click is authenticated by a cookie that says "human".
- **Today's fix for sharing is not sharing.** Browser vendors give each session its own browser. Browserbase's docs say "Avoid simultaneous logins... Sites may force a log out". That stops crashes but does nothing about two actors editing the same supplier record.

## 2. What the research found

1. **Multi-agent browser failures are real and well documented.** Playwright MCP's docs say a locked profile means "the server fails to start". In `agent-browser` #326, one agent's navigation replaced another's page. Several open issues remain around shared profiles and cookie isolation.
2. **Lower layers are improving, so we shouldn't compete there.** Playwright merged a change on 8 September letting several clients connect to one shared browser. The missing layer is above that: leases, identity, stale-view detection and evidence.
3. **Locks alone can't make this safe.** Kleppmann's fencing argument needs the resource to reject stale tokens, and a third-party website never will. So safety has to sit at the browser boundary: check the page hasn't changed before acting, read it back afterwards, and submit at most once.
4. **Approval has to be enforced outside the model.** Build the approval card from the actual pending form values and route it to someone other than the requester (first wave and `br-organisation`).
5. **Agents don't choose between tools well on their own.** Scale Labs found that "giving the model both interfaces doesn't automatically make it route between them". Spirit Room saw Codex miss an available MCP server in 8 of 80 runs and try a browser instead. So routing should follow written rules with typed failure reasons.
6. **Compiled routes are the efficiency story.** One author's runs of the same task cost $0.03 as a purpose-built Playwright script and $3.41 with a generic LLM browser agent. It's a single source but points the same way as the first wave's replay papers. Browsing a route once and replaying it for colleagues gives the workflow the repetition those savings need.
7. **In legal work, the multi-person risk is confidentiality.** One browser profile across two adverse matters is a serious problem. `br-legal` argues for making the matter the unit of isolation.

## 3. The shared browser

We adopt `agent-browser` and Playwright (both Apache-2.0) for low-level driving and write everything below ourselves. Nothing the team wrote before 12:00 Saturday can be reused, including Aiden's agent harness.

| Part | What it does | Priority |
|---|---|---|
| **Lease manager** | Claims on a page, a record or an account, each with a rising epoch number | Must |
| **Versioned observation** | Stamps each accessibility snapshot with a digest and epoch; element refs only work for that stamp | Must |
| **Action gate** (outside the model) | Checks epoch, digest and limits before dispatch; a stale action is dropped and the agent re-observes | Must |
| **Human takeover** | Pauses a lease so a person can log in, enter MFA or edit, then the agent resumes in the same session. The agent never sees secrets | Must |
| **Independent verifier** | Reads the system's own status as a fresh reader and never sees the agent's success claim | Must |
| **Live board and counter** | Shows who holds what, who's waiting, and tokens and time per step. Makes the shared browser legible to a judge | Must |
| **Mandate record** | Binds person, agent, scope, approver, limits and expiry to every action; refusals state a reason | Should |
| **Approval routing** | Sends a card built from pending values to an approver who isn't the requester, tied to that exact page state | Should |
| **Field-level merge** | Tracks which fields each actor changed so a human edit survives an agent's form fill | Should |
| **At-most-once submit** | On a timeout, reads the portal back and doesn't resubmit if it already went through; halts for a human if unclear | Should |
| **Compiled routes** | Promotes a working browser path to a guarded replay that a colleague's agent can reuse without page reasoning | Should |
| **Per-account scheduler** | Queues access per site account, so forced logouts and 429s become waiting | Stretch |
| **Tier router and gap register** | Tries API, then MCP, then compiled route, then browser, then human, using typed failure reasons | Stretch |
| **Matter-scoped profiles** | Separate profile, downloads and memory per matter | Stretch |

Agents get a small tool surface rather than dozens of verbs. Browser MCP schemas alone cost 13,700 to 18,000 tokens (`br-edges`, with the Playwright figure confirmed), which matters on the judged criteria.

## 4. Concepts

Scores are 1 to 5, higher is better.

| Concept | Browser central | Many actors | End to end | Buildable by 09:00 | Legal | Original | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Guest Seat** | 5 | 5 | 5 | 3 | 5 | 4 | **27** |
| Fix, Prove, Review | 5 | 4 | 4 | 4 | 1 | 3 | **21** |
| Escape Hatch | 4 | 3 | 3 | 3 | 1 | 4 | **18** |
| Clearance (first wave) | 2 | 1 | 4 | 3 | 5 | 3 | **18** |

- **Fix, Prove, Review:** the same shared browser used for coding. Three agents and two developers reproduce a bug on staging, fix it and prove it, under separate identities and without colliding. It's the best second workflow and could also enter JetBrains, whose first criterion is a working proof of concept. Its fourth criterion expects development in JetBrains Air, which we'd have to adopt early.
- **Escape Hatch:** a browser steps in for settings that APIs don't reach, then promotes each fix to a compiled tool. The idea is strong, but it would run against a mock of a cloud console. Its router and promotion ideas are folded into Guest Seat.
- **Clearance:** dropped as the main project. Its checks on the DPF list, the ICO and FCA registers and supplier pages are real browser work, so they become the diligence agent's job inside Guest Seat. Hamish's Slack and data-transfer additions carry over.
- **File and Prove (first wave):** dropped. We have nothing legitimate to file, and Hamish's notes record Wordsmith's own guidance excluding regulatory filings.

## 5. Guest Seat: the end-to-end workflow

**Scenario:** we're selling to a buyer who insists on onboarding through their portal. Actors: a legal agent, a finance agent, a human procurement lead, a human counsel, and the buyer's own agent on the other side.

1. **Receive:** a request arrives in Slack with the buyer's onboarding email. The legal agent extracts the portal link, PO number and required documents.
2. **Route:** mandates are issued before anything runs, stating who may do what. Work items go on the board, and agents claim sections of one record.
3. **Handoff:** the portal asks for MFA. The lease pauses, counsel enters the code, and the agent continues in the same session without seeing it.
4. **Real browsing:** the diligence agent goes to live public sites for evidence needed in the buyer's questionnaire, such as the DPF list and the ICO register, with sources recorded.
5. **Collision:** the human lead edits a questionnaire answer while an agent is working. The agent's next action is dropped as stale, it re-reads, and it fills only the fields it still owns. **This is the main demo moment.**
6. **Attack:** a document contains injected text asking to change the bank details. The gate refuses because no mandate covers that action, and gives the reason.
7. **Approval:** a legitimate binding action sends an approval card built from the pending values to someone other than the requester.
8. **Conflict with the other side:** the buyer's agent changes the PO reference mid-run. The change is detected instead of silently overwritten.
9. **Failure:** a forced timeout hits the submit. The gate reads back, finds it was submitted and doesn't resubmit.
10. **Reuse:** a second supplier record runs through the compiled route under a colleague's agent. The counter visibly drops. Where that colleague has no mandate, the agent refuses and says why.
11. **Record:** the verifier re-opens the portal as a fresh reader and produces a bundle with who acted for whom, approvals, hashes and a "could not verify" list.

**How a judge confirms it without trusting us:** the portal's own record shows one submission and the right values; the human's edit is still there; the dropped action and refusals appear in the audit export with reasons; the counter shows the difference between first and repeat runs.

### Run against a real system where possible

A hand-built mock portal is the concept's biggest weakness, because judges may see us beating our own toy. **Our suggestion, untested:** self-host a real open-source system as the "buyer's portal", as TheAgentCompany does with GitLab and ownCloud. We own that instance, so terms of service and seat licences stop being a problem, and it has its own UI, permissions and records.

ERPNext is the first candidate: it's GPL-3.0, actively maintained, and its documentation lists a supplier quotation flow through a supplier portal. We'd run it unmodified as a target, without shipping its code. The first test below checks whether it suits us. If it doesn't, we fall back to a labelled mock with an event log.

### Framing

Don't pitch this as sharing one licence among many people. `br-multiagent` is right that as a seat workaround it's a licensing dodge, and a legal judge would notice. The pitch is that named people's agents act on their authority, one at a time per account, with a record the site can't provide. Anyone without a seat or mandate gets refused.

## 6. Next steps

### Test first (about 90 minutes, before committing)

- [ ] Run ERPNext in Docker. Can a supplier user complete a quotation in the portal, and does it record who changed what? Is the UI usable through `agent-browser`? **This decides real system vs mock.**
- [ ] Run two `agent-browser` sessions plus a person against one portal login. What actually breaks, and can a person take over cleanly?
- [ ] Build the smallest stale-action demo: a human edit invalidates an agent's snapshot, and the gate drops its next action.
- [ ] Drive the DPF list and the ICO and FCA searches in a real browser on venue Wi-Fi.
- [ ] Measure tokens per step with a small tool surface. No controller publishes a reliable figure.

### Ask Wordsmith's engineers

1. Is a shared browser for several people and agents a problem your customers have, or does one person with one agent cover it?
2. Which portals do in-house teams really get pulled into as guests? Are procurement portals the right example?
3. Would a self-hosted real system or a labelled mock count for the final write step?
4. How do you measure complexity? Does coordination across actors count, or would you see it as complex internals?
5. Do tokens, model and time count throughout, or only to break ties?
6. Do you already have a browser agent, in beta or planned?

Question 4 matters most. The main risk is that judges read this as infrastructure, so the demo must lead with the task being done and show the machinery only when it saves the day.

### Suggested split, for Hamish to decide

| Person | Area |
|---|---|
| Hamish | Agent loop, gate and mandates, because of his Playwright and multi-agent work |
| Aiden | Shared browser, leases, integration and the board, plus edge cases |
| Jake | Verifier, token and time measurement, and honest metrics |
| Mano | Failure scenarios and stress tests, pitch and backup video |

### Limits

- Every mock or self-hosted target is labelled as such on screen. No real portal is automated with a borrowed or shared login.
- Treat a bot challenge as a stop or a human handoff, never something to get around.
- Demo with public or synthetic contracts, because the Gemini free tier may be used to improve Google's products and human reviewers may read inputs.
- Output is evidence for a lawyer to review. It doesn't conclude on legal matters or file with a court or regulator.
- A shared browser holding several people's sessions is a valuable target, so it needs a real privacy and security answer, not just a feature list.
- Keep a recorded run ready. Log AI tool use for the write-up.

## 7. Verification

**Confirmed against sources (7 Nov):** Playwright's profile lock wording; `agent-browser` #326 and open #896, #1068 and #1211; Browserbase's "avoid simultaneous logins"; Kleppmann's fencing tokens; Entra's subject and actor wording; Agent 365 licensing per user; Datasite's MCP access-controls claim (a vendor claim); Coupa's portal being free for suppliers; the $0.03 vs $3.41 figures and the 13,678-token figure; Scale Labs' routing finding; Codex's 8 of 80 runs; the Power Platform attribution thread; Claude Code's Chrome behaviour; Cloudflare's agent controls; Edge's handoff for authentication and final submit.

**Corrections to the reports:**

| Report | Claim | Correction |
|---|---|---|
| br-multiagent | `agent-browser` #1272 is still open | It's closed. #896, #1068 and #1211 are open |
| br-multiagent | MCP #1215 shows a single-client limit | Now closed, as the report warned. Don't quote it as current |
| br-multiagent | "About a day of work" for the demo | An unmeasured estimate. The tests above should replace it |
| br-engineering | Merge status of two Playwright PRs unverified | #42622 (several clients, one shared browser) merged on 8 September; #39703 (`tabId`) closed unmerged. Sharing is further along than the report implies, and the coordination gap is what remains |
| br-edges | "Cost is decided by the interface, not the model" | Too strong. The same Scale Labs study says interface choice matters much less for the latest frontier models. The 45× figure is a vendor benchmark reported second-hand |
| br-legal | UiPath report of a page "navigating away" | More specifically, it redirected to the login page, so it may be a session problem rather than a layout one |

**Not confirmed:** the r/procurement post about 100+ portals, SAP's pricing page and Firmex's Q&A roles all returned 403 to my checks, so they rest on the agent's reading. ERPNext's supplier portal is confirmed only as a documentation heading.

**Is this already a product?** Not that we found, but a few searches can't prove that. The nearest things are Samesurf, a vendor describing one human taking over from one agent in a shared cloud browser; OpenMAIC, whose session leases are reportedly client-side; agent-coordination-substrate, a general coordination spec; and a practitioner write-up describing a browser-agent control plane. Practitioners mostly advise isolating agents instead. Isolation is the standard answer, so expect "why not just give each agent a browser?". The answer is that the login and the record are shared even if the browsers aren't.

**What this can't tell us:** no agent ran anything, so everything about feasibility is unproven until the tests above run.
