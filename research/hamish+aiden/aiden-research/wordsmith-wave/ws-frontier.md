# ws-frontier: unsolved problems and efficiency

Research agent ws-frontier, Saturday 7 November 2026. Claims dated; anything not confirmed against a primary source is marked **(unverified)**.

## 1. Bottom line

1. **The headline benchmark number does not survive audit.** Browser Use reports **97% (291/300)** on Online-Mind2Web, but the judging in that repo is Claude grading the agent's own final answer, not the benchmark's evaluator, and two tasks were declared impossible (291/298 = 97.7%). The benchmark authors' careful human evaluation of the same 300 tasks put the best agent at **61.3%** in 2025 and most near **30%**. Judges are themselves unreliable: WebVoyager-style judges show **≥45% false positives**, WebJudge **≥22%**. Design for verifiable success, not a judge's opinion.
2. **Page representation beats model choice at component level.** Changing only the observation and action space moves GPT-5 mini from **83.1%** (accessibility-tree text, element IDs) to **48.9%** (screenshot, coordinates) — 34 points, same model, same tasks. AX-tree text is the right default; pixels alone are not.
3. **Success collapses geometrically, at about 16 steps.** Across nine models including deployed proprietary systems, success fell from near-perfect to near-zero within **16 dependent steps** on an agentic loop. It is step count, not context length: shrinking the context makes decay *steeper*.
4. **Compile once, replay deterministically — the biggest measured token/time lever.** Plan-and-execute tied ReAct (88.8% vs 92.0%, n.s.) at **83.6% fewer input tokens, 67.3% fewer calls, 80.4% less money, 4.1× faster**. Recording a successful run into a guarded state machine replays **8.5–13× faster with no per-step LLM calls**; compiling to a deterministic blueprint takes per-workflow cost from ~$15 (cached ReAct) to **under $0.10**.
5. **Approval prompts are not a security boundary; enforcement outside the model is.** Injected page text got agents in a signed-in session to approve third-party access in **all 73 attack runs**; "only the user's task authorises this" still left **7 of 10** succeeding. A gate outside the model, checking the pending action against an envelope fixed before the run, blocked **100%** while every legitimate control task passed.

## 2. Findings

### 2.1 Page representation

- **AX-tree text with element IDs is the strongest single default.** ComponentBench (COLM 2026; 2,910 tasks, 97 components, seven models) finds a >30% success swing from the observation/action space alone, and that even the *fastest* configuration takes **3.7× as long as the matched human reference**.
- **Hybrid usually wins, but the best mode reverses between task sets.** Six modes across eight site–model cells on WebArena/VisualWebArena are complementary and fail in structurally different ways. MobiBench (Android) reports GPT-4.1 at 27.17% AX-text, 4.72% pixel-only, **31.50% hybrid** **(unverified, secondary)**.
- **Per-task routing is not worth building yet.** Oracle mode-picking is inflated by noise: re-running the same mode flips **12–14% of outcomes**. Five routing policies were tested and **none robustly beat fixing one well-chosen mode**. What survives: send only the tasks no mode solves to the cheapest mode — **9.5–30.6% cheaper in 8 of 8 cells at unchanged success**. Practical read: pick AX-text, add a screenshot only on ambiguous steps.
- **Observation frequency, not size, drives cost.** DOM/AX trees run to "tens of thousands of tokens" at *every* step. The proposed fix — a cheap sub-call returns only task-relevant elements, re-invoked only when a signal fires (URL change, new interactive elements, action failure) — is an argued position from an ICML 2026 workshop paper, **not yet benchmarked**.

### 2.2 Techniques that cut tokens and time, with measurements

- **Plan once, ground locally** (200 tasks, seven sites, 2,800 runs, DeepSeek v4.1 flash): 83.6% fewer input tokens, 67.3% fewer calls, 80.4% cheaper, 4.1× faster, accuracy tied with a *budget-matched* ReAct loop. Against an unmatched ReAct baseline the gain looks like +8.2 points, but that is entirely an artefact of the baseline's smaller reading window and turn cap.
- **Compile to a deterministic blueprint**: ~$150 (500× ReAct) or ~$15 (heavily cached) down to **<$0.10 per workflow**; 80–94% zero-shot compile success, near-100% with light human patching; $0.002–$0.092 per compile across five frontier models.
- **Record-then-replay into a guarded state machine**: 8.5–13× faster repeats with zero per-step calls; the screen is checked against what the program expects before it acts, and control hands back to the agent the moment it diverges. A store-time independent re-run before trusting a program is worth **1.75–2.6 tasks per benchmark**.
- **Deterministic skill replay for periodic tasks**: 93.3–99.98% lower monthly tokens, 8.7× lower latency. Single lab, vendor-style, no replication — treat as an upper bound.
- **Small-model routing / planner–executor splits: contradictory evidence.** One 2026 router reports 72% lower cost at 97.3% of frontier quality on non-browser tasks; other evaluations find the split *loses* to one strong model in a mature harness, and a compute-controlled study finds no overall validity gain from the extra planner tokens. Do not bank on it.
- **Parallel tabs: weak evidence.** One hobby project's own benchmark gets a 2.6× wall-clock speedup with 5 concurrent CDP tabs **(unverified)**; independent trace studies find the slowest sibling dominates (3.3× median tool-time imbalance). Parallelise only independent lookups, then synthesise once.
- **Self-healing selectors: no credible independent head-to-head found.** The nearest real result is the replay guard above — plus the finding that a **language-model retriever is no better than a plain embedding retriever** for picking which recorded program to reuse. "Self-healing selectors" is mostly vendor language.

Two negative results shape the design. The neural local grounder was **not significantly better than word-overlap matching** (+2.3 points, CI −0.2 to +5.0) and costs 31 ms per call — a fuzzy matcher over AX labels may be enough. And planning ahead fails exactly where the next step depends on content that does not yet exist: on a to-do-list site, plan-and-execute scored **0/30 and 2/30** against **26/30** for budget-matched ReAct, because a plan written before typing cannot name the list items that appear afterwards. Plan the stable spine, react inside content-creating steps.

One structural datapoint for the tie-breaker: **all WebArena tasks are compatible with compile-and-execute, and 81% are solvable by a purely static program with no runtime LLM call.** The stated barrier is that `click`/`type`/`scroll` have page-dependent meaning, so a compiler cannot see far enough ahead — an infrastructure gap, not a modelling one, and one a small team can partly close with typed actions for a few specific sites.

### 2.3 Verifying that a long workflow really succeeded

- **Judge-based verification is weaker than it looks.** The Universal Verifier work (Microsoft Research, Apr 2026) reports **≥45% false positives** for WebVoyager-style judging and **≥22%** for WebJudge, and gets near zero by combining non-overlapping rubrics, separate process and outcome scores, cascading-error-free scoring of controllable versus uncontrollable failures, and context over *all* screenshots.
- **The agent's own success claim contaminates the judge.** Withholding the self-report improves recall of "dangerous misreports" (a confident claim the trace does not support) by **43.4 percentage points** (Qwen3.5-35B-A3B) and **13.3 points** (DeepSeek-284B-A13B); that auditor blocks 74–90% of dangerous misreports at 45–56% inspection load. Directly relevant at DeepSeek Flash prices.
- **The cheapest reliable verification is where the environment asserts the outcome.** WebPageBench instruments the mock sites: each task declares the typed events it requires, and success is event matching with **no judge and no scraping**. If we own the demo site, this is nearly free and unimpeachable in front of judges.
- **Reusable verifiers remain open.** AgentProofBench (97 tasks, DeepSeek Flash/Pro) finds frozen acceptance rules retain only ~82–86% of source programs under decision replay — the verifier is itself a moving target.

### 2.4 Where success collapses, and how recovery works

- **Geometrically, in step count.** "How Fast Do Agents Rot?" (nine models 1.2B–671B plus three proprietary; 10,664 trajectories) fits `P(success) ≈ a·r^H` with per-step reliability saturating below 1. Every model, including deployed systems, fell to near zero **within 16 steps**; bounding context *steepens* decay (−0.69 vs −0.44 logit slope). Projected reliability drops from **0.42 at GAIA-length horizons to 0.24 at hundred-step horizons**.
- **Live-web reality**: Odysseys puts the strongest frontier model at **44.5%** success and only **1.15%** rubric points per step — agents eventually succeed, expensively. Benchmark spread is enormous: WebArena ~74% vs a 78.2% human baseline **(secondary)**, WorkArena-L2 ~69% for GPT-5 **(secondary)**, WorkArena++ 2.1% for GPT-4o against 93.9% human.
- **Recovery is structural, not clever.** The patterns with evidence: assertions between short segments so failures surface at a boundary rather than silently at step 15; replay gated on a screen-state precondition that hands back to the model on divergence; an independent re-run before any recorded program is trusted. What did *not* matter in that study: prompt wording, runtime guardrails, and LLM-versus-embedding retrieval.

### 2.5 Prompt injection: what is actually measured

- **Confused-deputy attacks against the approval click succeed almost totally without architecture.** Two sentences of injected page text made signed-in agents approve OAuth access or register a webhook: the unauthorized action completed in **all 73** runs; a prompt instruction left **7 of 10** consent attacks succeeding. With a service-side envelope fixed before the run, the agent still sent the request in all 70 runs and the service rejected **every** one, while every control task naming the target passed.
- **Out-of-band approval rendering works.** The Verifiable Action Card (24 scenarios: confused deputy, dialog forging, injection, adaptive substitution) reports **68–100% attack success without it, 0% with it on every model**, 78% legitimate completion, 0% false blocks — approval is rebuilt from the ground-truth pending action, rendered in trusted browser chrome, and re-verified at dispatch.
- **Human approval is a weak boundary by itself.** A 340-person dialog study reports adversarial approval falling from **81% to 22%** when the dialog shows the full destination and compares parameters to the user's own words; a browser study of 1,400 injections across nine attack types reports layered defences reaching **2.4%** with no single defence below 18% **(both unverified, vendor research pages)**.
- **One design buys security and tokens together.** Compile-and-execute makes the boundary explicit: untrusted page content may fill values or choose a branch inside a predefined graph, but cannot redefine the task or synthesise a new action. That is simultaneously the injection defence and the token saving — a strong story for a legal-adjacent track.

## 3. Comparison table

| Approach | Tokens | Wall clock | Success evidence | Model at runtime? | Main failure mode |
|---|---|---|---|---|---|
| ReAct, AX-tree obs | ~24.7k input/task | 42 s/task | 92.0% on that bench; collapses past ~16 steps | Every step | Context growth; injection surface |
| ReAct, screenshot/pixel | Image tokens **+** 34-point success penalty | Slowest | 48.9% vs 83.1% same model | Every step | Grounding on dense UIs |
| Plan once + local grounder | ~4.1k input/task (−83.6%) | 10.2 s (−4.1×) | 88.8%, tie | 1 call + 31 ms/step local | Cannot name content created mid-run |
| Compiled blueprint + runtime | $0.002–$0.09 per compile | Browser speed | 80–94% zero-shot, ~100% patched | No | 6–20% compile failures need patching |
| Recorded state machine + guards | 0 calls on replay | 8.5–13× faster | Improves only if store-time verified | No | Stale programs accumulate if unverified |
| HITL approval only | Cheap | Adds a stall | — | — | 73/73 attack success; 7/10 with an instruction |
| Verifiable approval + envelope gate | Cheap | One confirm | 0% attack success, 78% completion | No | Needs action descriptor + trusted chrome |
| Judge-based success check | Adds a frontier call | +2–5 s | ≥22–45% false positive | Yes | Agent's claim leaks into the verdict |
| Event-log check on an instrumented site | ~0 | ~0 | Exact, no judge | No | Only sites we own |

## 4. Risks and unknowns

- **Most strong 2026 numbers here are preprints** (Apr–Jun 2026 papers, a single-author Zenodo study). Several are single-lab with no independent replication. I trust the *direction* of compile-and-replay far more than any single percentage.
- **The 97% headline is self-reported with a non-standard judge** and two excluded tasks; I found no independent reproduction. Don't quote it as fact.
- **Rerun noise is 12–14% of outcomes.** A "+5 points" claim from a small evaluation is inside the noise band, and a live demo can fail on a run that worked an hour earlier. Record a fallback.
- **Parallel tabs and "self-healing selectors" are the weakest evidence in this track** — one hobby benchmark and vendor language respectively.
- **Not verified to primary source**: MobiBench, the OSWorld representation figures, the 340-person approval study, the 1,400-injection corpus, and the WebArena/WorkArena headline numbers (all reached via secondary or vendor pages).
- **Injection defences are measured on curated scenarios.** 0% on 24 scenarios is not proof against an adaptive attacker; one adaptive benchmark reports initially-weak attacks rising to ~95% once tailored **(unverified preprint)**.
- **Unsettled**: whether compile-and-replay helps on a *first* run at all. All evidence is about repeats — so the honest demo shows a slow reasoning run, then a fast guarded replay.

## 5. Three openings

**A — Compile, checkpoint, replay: a workflow that visibly gets cheaper.** Run a multi-site check once with full reasoning, compile the successful trajectory into a deterministic program with per-segment assertions (screen-state preconditions, expected post-conditions), then replay with zero model calls and a live token/time counter showing the collapse between run 1 and run 2. *New*: shipped agents reason every step; nobody shows the compiled artefact and its guarded replay with the counter on screen. *Nearby*: Agentic Compilation (compiler + JSON blueprint), PreAct (state-machine replay, guard-and-hand-back), ReUseIt (synthesis with execution guards). *Evidence*: 8.5–13× faster replay, <$0.10 vs ~$15 per workflow, 80–94% compile success, store-time verification worth 1.75–2.6 tasks. *In 20 hours*: one site family, two recorded runs, a counter, and a guard failing on purpose to show hand-back.

**B — Verified, not asserted: an audit panel that proves the workflow happened.** Quarantine the agent's success claim as a separate object; check the recorded trace against typed post-conditions from a site we instrument ourselves; show "the agent says done" beside "the trace proves done", including one deliberately caught misreport. *New*: the criterion is verifiability and the punchline is catching the agent lying about a completed filing. *Nearby*: WebPageBench (event-level verification, no judge), Universal Verifier (why judges have ≥22–45% false positives), self-report leakage (13–43 point recall gain). *Evidence*: those three. This answers the sponsor's "how do you know it worked" question, which consumer agent products answer badly.

**C — A typed action layer that makes injection structurally unable to change the plan.** Define 15–25 typed, task-level actions for two or three real registers (search a company, pull a filing, check a licence, read a sanctions entry). The planner emits plans over typed actions only; page content can fill values but never add actions; every consequential action must match an envelope fixed at task start. *New*: the position paper's prescription ("the web does not expose typed interfaces") turned into a narrow working demonstration with a before/after attack. *Nearby*: Compile-and-Execute (81% of WebArena tasks static-program solvable), the envelope gate (73/73 → 0 completed), VAC (0% attack success out of band). *In 20 hours*: one site, one injected page, one rejected envelope, plus a legitimate run that passes.

A and C compose best: A carries the efficiency tie-breaker, C carries complexity, security and the legal framing.

## 6. Sources

**Benchmarks**
- https://arxiv.org/abs/2608.18307 — ComponentBench (COLM 2026): 83.1% vs 48.9%, same harness; 3.7× slower than humans.
- https://arxiv.org/abs/2608.06171 — Representation routing (6 Aug 2026): 12–14% rerun flips; 9.5–30.6% cost cut; no router beats a fixed mode.
- https://arxiv.org/abs/2604.24964 — Odysseys (27 Apr 2026): 44.5% best success; Trajectory Efficiency 1.15%.
- https://arxiv.org/abs/2504.01382 — "An Illusion of Progress?": human evaluation, most agents ~30%, Operator 61.3%.
- https://github.com/browser-use/online-mind2web/blob/main/README.md — the 97% claim's own method (Claude judging final responses; 291/298).
- https://browser-use.com/posts/online-mind2web-benchmark — vendor post for the 97% claim.
- https://arxiv.org/abs/2605.14290 — Position: Compile-and-Execute (v2, 23 Oct 2026): all WebArena tasks compatible, 81% static, injection boundary.
- https://arxiv.org/abs/2606.06708 — Signal-Driven Observation (ICML 2026 FAGEN): tens of thousands of tokens per step; position paper, not benchmarked.

**Efficiency**
- https://arxiv.org/abs/2604.09718 — Agentic Compilation: ~$150 → <$0.10 per workflow; 80–94% compile success.
- https://arxiv.org/abs/2606.17929 — PreAct: 8.5–13× replay; guards; store-time verification.
- https://arxiv.org/abs/2605.14237 — LOOP Skill Engine: 93.3–99.98% token cut (single lab).
- https://arxiv.org/abs/2510.14308 — ReUseIt: workflows with execution guards.
- https://doi.org/10.5281/zenodo.22904595 (divyanshshukla.com/research/plan-once-ground-locally) — Plan Once, Ground Locally: 83.6%/67.3%/80.4%/4.1×; TodoMVC 0/30, 2/30 vs 26/30.
- https://www.langchain.com/blog/switchyard-agent-routing-benchmark ; https://akitaonrails.github.io/en/2026/04/25/llm-benchmarks-vale-a-pena-misturar-2-modelos/ — contradictory routing evidence (secondary).

**Long horizon, verification**
- https://arxiv.org/abs/2609.01660 — How Fast Do Agents Rot?: 16-step collapse; step count not context.
- https://arxiv.org/abs/2604.06240 — Verifiers for CUAs: ≥45%/≥22% judge false positives; Universal Verifier.
- https://arxiv.org/abs/2610.29609 — Self-report leakage (ICSE 2027): 43.4pp / 13.3pp recall gain.
- https://arxiv.org/abs/2609.35026 — WebPageBench: event-level verification, no judge.
- https://arxiv.org/abs/2610.34634 — AgentProofBench: 82–86% verifier retention, DeepSeek Flash/Pro.

**Security**
- https://arxiv.org/abs/2610.15138 — The Agent Clicks Approve: 73/73; 7/10 with instruction; envelope gate rejects all 70.
- https://arxiv.org/abs/2609.18411 — Verifiable Action Card: 68–100% → 0%, 78% completion.
- https://dartbrowser.com/research-3 ; https://dartbrowser.com/research-7 — 2.4% layered defence; 81%→22% approval **(unverified, vendor)**.
- https://arxiv.org/abs/2610.17457 — adaptive injection rising to ~95% **(unverified preprint)**.

**Secondary summaries not traced to primary sources**: blolabel.ai/blog/mobibench-screenshot-grounds-worse-than-the-tree (MobiBench 27.17%/4.72%/31.50%); yourstash.ai/articles/accessibility-tree-vs-screenshot-ai-agents (OSWorld 7.0%/15.6%/20.7%); hai.stanford.edu/assets/files/ai_index_report_2026_chapter_2_technical.pdf and theaggregate.ai/benchmark?slug=browsergym-workarena-l2 (WebArena ~74.3%, WorkArena-L2 ~69.4%); jeet-dhandha.github.io/agent-webbridge/parallel-browser-automation (5-tab 2.6× concurrency, hobby project).
