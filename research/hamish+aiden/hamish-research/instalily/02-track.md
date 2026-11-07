# InstaLILY track: build a coding agent that adapts to whoever is using it

Researched 7 Nov 2026. Brief restated from the team's summary file (`SlideSummaryFromTranscription.MD`, section 3.7). The full brief behind the QR code has **not been read**, so the judging details below may change.

## The brief, as given

**Task:** build an agentic IDE: a coding agent. It must be designed for three personas.

1. **A beginner.** "If you were twelve and sat down to code, how would you want this product to teach you?"
2. **An engineer who wants things done fast.**
3. **A persona of your own design.**

**Example scenario:** a beginner has a simple `for` loop that goes wrong. How does the agent respond, how does it know to respond that way, and what context and tools does it get?

**Judging (three stages):**

1. **Clear the bar.** Same hidden tests for every team. Pass or fail.
2. **Adapt to the user.** Does what was asked, no more, and reports honestly.
3. **Win over real people.** InstaLILY engineers use it live with your personas.

**Slide hints:**
- "Understanding your user" weighs the most.
- Do what is asked. Respect limits. Ask only when needed.
- User value is scored, not difficulty.
- Each persona is scored separately and equally.

**Evaluation:** partly automatic, partly subjective. The team kit includes an **evaluator harness** that plugs into your solution, plus an **LLM**.

**Prize:** fast-track interview with InstaLILY plus Sony WH-1000XM5 for the winning team. Second: Logitech MX Master 3S. Every team gets expert feedback from four InstaLILY engineers. Aimed at final-year students, but open to everyone.

## What will impress these judges

Read from the brief and from the company's own language (see `01-company.md`):

1. **Visible adaptation.** A judge should see the agent change behaviour between personas in the first minute. Show the persona switch, then the same bug answered three ways.
2. **Honest reporting.** "I ran the tests; 2 of 5 fail; here is why" beats a confident "done". This matches "reports honestly" in stage 2.
3. **Restraint.** The engineer persona gets a minimal diff. The beginner gets a question, not the fix. Judges will check for both.
4. **Hidden-test discipline.** Clear the bar first. A solid core that passes the hidden tests beats a flashy UI that does not.
5. **A real live flow.** Their engineers will type into it. Make the first five minutes robust: no network calls that can fail on stage.
6. **A story they can say back.** Forward-deployed engineering framing: "it learns who it is talking to, then gets out of the way".

## What is likely to lose

1. **Failing the hidden tests.** Stage 1 is a gate. Teams that skip the core task to polish personas lose here.
2. **Personas that are only a system prompt.** Three prompts that differ in tone and nothing else will be spotted. Persona must change tools, defaults and checks.
3. **Over-asking.** The brief says "ask only when needed". An agent that asks five questions before it touches code will score badly on stage 2.
4. **Doing too much.** Refactoring the beginner's whole file, or adding features nobody asked for. The brief rewards "no more".
5. **Patronising the beginner.** Long lectures and jargon-free but empty encouragement.
6. **Unverified claims.** Saying "tests pass" with no run behind it.
7. **Fighting the team kit.** Building your own harness and ignoring the provided LLM and evaluator.
8. **Strong competition.** Experienced coding-agent teams will ship a solid engineer persona quickly.

## Unknowns still to check

| Unknown | Why it matters | How to check (under 30 min) |
|---|---|---|
| Full brief behind the QR code | Judging criteria, weighting, persona definitions could differ | Scan the QR code on the InstaLILY booth or ask a volunteer |
| What the "team kit" contains (language, repo layout, LLM provider, token budget) | Decides our stack | Ask an InstaLILY engineer at the booth; check kit licence |
| Format of hidden tests (CLI? repo? a task list?) | Decides whether we need a runnable CLI | Ask at the booth |
| Whether the evaluator drives our agent via API, CLI or an editor plugin | Decides the interface | Same as above |
| How "adapt to user" is measured (LLM judge rubric? human rubric?) | Decides how we write persona behaviour | Ask; read the kit's LLM prompt if provided |
| Whether the ship26 / Toronto hackathon briefs are the same track | Possibly a pre-brief | Read ship26.instalily.ai and toronto26.instalily.ai |
| Whether our baseline agentic browser can run inside the kit | Dual-track fit | Only after the kit is read |

## How the baseline agentic-browser idea scores on this track

**Baseline:** a Wordsmith-track agentic browser (an agent that completes a complex end-to-end web workflow).

**Fit: weak to moderate.** Honest view:

- **Where it fits.** A browser is useful for two things here:
  1. Showing a beginner **live docs or a visual run** of their code (for example, opening the MDN page for the loop they got wrong, or rendering a small web page they built).
  2. **Verifying a web change** by browsing it, which is the "engineer" persona's proof that work was done.
- **Where it does not fit.** The hidden tests are about the coding task, not browsing. A browser adds latency, flakiness and a second failure mode. It also draws attention away from persona behaviour, which is the highest-weighted criterion.
- **Trade-off.** Use the browser as an optional verification tool, not as the core. It can earn points for "reports honestly" if the agent shows the page it checked. Keep it behind a flag so the core path stays fast and offline.

**Score (rough, 1 to 5):**
- Hidden-test value: 1 (browser does not help pass tests).
- Persona value: 3 (browser can help the beginner see the result; the engineer persona needs less).
- Demo value for InstaLILY engineers: 3, if the browser proof is quick and shown on screen.
- Net: a supporting feature, not the main project. Pick a different core for this track, or fold the browser in as a stage-2 proof step.

## Implications

- Treat this as a coding-agent track first. The browser is an optional extra.
- Build the core (hidden-test pass rate) before any persona UI. Stage 1 is a gate.
- Make persona switching visible and tool-level, not just prompt-level.
- Read the QR-code brief before committing the design. This file should be revised after that.
