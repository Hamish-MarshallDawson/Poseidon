# HackTheBurgh XIII: research notes

Compiled on Saturday 7 November 2026 from the opening ceremony recordings, the sponsor slides, the HackTheBurgh website and the team call on 6 November. Prizes and quotes are as stated on the slides or in the talks. Anything not confirmed is marked **(unverified)**.

---

## 1. Event essentials

| Item | Detail |
|---|---|
| Dates | Saturday 7 to Sunday 8 November 2026 |
| Venue | The Nucleus Building, Edinburgh |
| Hacking | 12:00 Saturday to the 12:00 Sunday submission deadline |
| Team deadline | 13:00 Saturday |
| Demos and judging | From 12:30 Sunday; closing ceremony 15:00 |
| Size | 300 participants from about 1,000 applications (220 from 700 last year) |
| Submission | On the HackTheBurgh site's projects page ("hacktheburgh.com/projects" **(unverified)**). One team member's Discord username goes in the submission. |
| Judging slots | Announced on Discord. The whole team must attend the judging slot. |
| Venue access | Wear lanyards at all times; they are also needed for food. The building closes to the public at 19:00. |
| Help | Volunteers wear orange or blue badges. A yellow lanyard means the person does not want to be photographed. |

### Workshops (Larch Lecture Theatre, first floor)

| Time | Sponsor | Topic as described |
|---|---|---|
| 14:00 to 14:50 | HRT | Their work and their challenge (brownies promised) |
| 15:00 to 15:50 | Metaview | Build a small agent that finds people for a warm referral and drafts outreach |
| 16:00 to 16:50 | JetBrains | Agentic development in their IDEs and building AI agents |
| 17:00 to 17:50 | G-Research | An internal tool they built recently using AI |
| 18:00 to 18:50 | MLH | Not described |

Discord announces each workshop shortly before it starts.

---

## 2. Rules

From the organisers' talk and the [code of conduct](https://hacktheburgh.com/code-of-conduct):

- One project per team, one codebase. A single project may be entered for several sponsor tracks.
- Only work built during the hackathon counts. Projects started earlier and adapted are not allowed.
- Public open-source code and libraries are allowed if you follow their licences.
- Generative AI and other AI tools are allowed, but you must disclose them and explain what they did.
- Submitting someone else's work is cheating and leads to disqualification.
- The MLH Code of Conduct applies to everyone.

**Practical consequences:** start a fresh repo after 12:00 Saturday, commit often, and keep a running log of AI tool use for the write-up. Earlier personal projects (TensorRoom, LocalMind, Jake's calibration pipeline, the letting-agent chatbot) cannot be reused as code.

---

## 3. Sponsor tracks

### 3.1 Metaview (Platinum): Best Overall Project

- **Track:** none. Metaview awards the best overall project from any track, or from no track.
- **Judged on:** creativity; any project is eligible.
- **Prize:** $500 for every member of the winning team. Second prize: GTA 6.
- **About them:** an agentic recruiting platform. AI agents source candidates, shortlist applications and follow interviews to summarise them for hiring managers.
- **Workshop:** 15:00.

### 3.2 Hudson River Trading (Platinum): Best Use of Data for Predictions and Decision Making

- **Brief:** any use of data for prediction or decision-making. "It doesn't have to be financial."
- **What they stressed:** data drives everything they do (petabyte-scale storage, very fast trading). They want decisions made as quickly as possible from data.
- **Prize:** PlayStation 5s. Second place: keyboards.
- **Opportunities:** internships and spring weeks.
- **Workshop:** 14:00.

### 3.3 G-Research (Gold): Make the Invisible Visible

- **Brief:** find hidden patterns in data and turn them into something that looks cool or is cool.
- **What they stressed:** creative solutions and well-structured solutions. The firm began with finding signals in data.
- **Prize:** Nintendo Switch 2s (with Mario Kart).
- **Opportunities:** software engineering and ML internships still open; a year-long cybersecurity placement.
- **Workshop:** 17:00.

### 3.4 JetBrains (Gold): Help the Developer

- **Brief:** deliberately vague. Their advice: build something for yourself that you would use. Tools for developer education, AI that works alongside development, anything in software development.
- **Process requirement:** do the agentic development inside JetBrains IDEs using AI. They will ask how you used AI to code, and prefer that you did.
- **Judging:** five criteria in a document behind a QR code at their booth, also posted on Discord **(not read yet)**.
- **Resources:** their coding agent is free until the end of the year. OpenAI API keys, one per team, from the booth or Discord. Do not commit keys to GitHub, because they get blocked.
- **Prize:** €350 for every member of the winning team. Second place: €150 each.
- **Opportunities:** in-person interns in their new London office, or remote across the UK. Their tools are free for students.
- **Workshop:** 16:00.

### 3.5 Bank of Scotland, part of Lloyds Banking Group (Gold): Smart Cost of Living

- **Brief:** help customers navigate their everyday choices to save money and to optimise for sustainability. Different customers have different priorities. "If you can build something which will help people in their day to day lives, we'd love to see it."
- **Prize:** £150 Amazon gift card for every member of the winning team. Second place: £75 each.
- **Opportunities:** graduate scheme (three rotations of eight months), year-long industrial placements, summer internships, apprenticeships. They said applications are still open.
- **On site:** a stall all weekend.

### 3.6 Wordsmith AI (Silver): the most complicated end-to-end agentic AI browser-use workflow

- **Brief:** "make something really, really cool with browsers and agents." Open-ended, so it can overlap with other tracks. Find a niche within the unsolved problem of agents using browsers.
- **Complexity:** a complex task end to end, not complex internals for their own sake.
- **Bonus:** a few extra points if it is legal-focused, but that is not required.
- **Tie-breaker:** tokens used, model used and compute efficiency.
- **From their deck** (`research/hamish+aiden/Wordsmith/HackTheBurgh — Wordsmith.pdf`): the main criterion is **workflow complexity** ("how complex a workflow your team managed to make"). Also considered: **tokens used, model used, time to complete the task**. On legal focus: "Ideally legally involved, but not required. Creativity required."
- **Judges:** three engineers. Ash (Operations Engineer: systems and automations), Eli (Product Engineer: features lawyers use), Chapman (GTM Engineer: go-to-market tools). Emails `ash@`, `eli@`, `chapman@wordsmith.ai`.
- **Prize:** AirPods Max for every member of the winning team. Second and third: goodie bags.
- **About them:** Edinburgh-based legal AI company; Series B recently; hiring fast. Contact emails were on their slide.

### 3.7 InstaLILY (Silver): Build a coding agent that adapts to whoever is using it

- **Brief:** an agentic IDE. The agent must be designed for three personas:
    1. A beginner: "if you were twelve and sat down to code, how would you want this product to teach you?"
    2. An engineer who wants things done fast.
    3. A persona of your own design.
- **Example scenario:** a beginner has a simple for loop that is going wrong. How does the agent respond, how does it know to respond that way, and what context and tools does it get?
- **Judging:**
    1. Clear the bar: the same hidden tests for every team.
    2. Adapt to the user: does what was asked, no more, and reports honestly.
    3. Win over real people: their engineers use it live with your personas.
- **Hints from the slide:** understanding your user weighs the most. Do what is asked, respect limits, ask only when needed. User value is scored, not difficulty. Each persona is scored separately and equally.
- **Evaluation:** partly automatic and partly subjective. The team kit includes an evaluator harness that plugs into your solution, plus an LLM.
- **Logistics:** submissions close 12:00 Sunday 8 November. A team kit is provided. The full brief is behind a QR code **(not read yet)**.
- **Prize:** fast-track interview with InstaLILY plus Sony WH-1000XM5 headphones for the winning team. Second place: Logitech MX Master 3S mice. Every team gets expert feedback from four InstaLILY engineers. It is aimed at final-year students, but everyone may enter.
- **About them:** builds custom AI agents for manufacturing and distribution clients (sales enablement, lead generation, quote-to-order, email and master-data management). Their engineers are forward-deployed and work directly with clients.

### 3.8 Viridien (Silver): Automate lithological interval detection, depth mapping, pattern clustering and legend classification

- **Context:** a geoscience technology company of nearly 100 years. Borehole reports are archived as scanned images and used to be read by hand. A single oil well can cost about $100 million to drill.
- **Task:** build an automated solution that can:
    1. Identify individual rock-type (lithological) intervals and their boundaries.
    2. Group intervals that have the same or similar visual patterns.
    3. Work out the top and base depth of each interval.
    4. Map each group to the legend to give its rock-type name.
    5. Bonus: find the depth column, lithology column and legend without using the supplied bounding boxes.
- **Dataset:** 50 document images, described as very long. Annotation files give bounding boxes for the depth column, the interpreted lithology column and the lithology legend. Manual annotation of the development images is allowed for training, tuning and validation. Held-out evaluation images are released near the end.
- **Expected output per document:**
    - A CSV with one row per interval: `top_y`, `bottom_y` (pixels), `cluster_id`, `lithology`, `top_depth`, `base_depth`.
    - An annotated image showing the lithology column with predicted boundaries, depth estimates and cluster or rock-type labels.
- **Example row from the slide:** `300, 450, Siltstone, A, 100, 115`.
- **Suggested approach (not required):** segment the column, cluster similar patterns and match them to the legend, then convert pixels to depths. Traditional computer vision is also acceptable.
- **Things to consider (from the slide):** correctness on challenging cases; generalisation to unseen documents; efficiency (processing time, memory, hardware, running cost); simplicity (complexity only where it improves results); automation (no manual correction of final predictions).
- **In the demo:** explain the approach, show results and limitations, and report runtime and resource needs.
- **Judged on:** correctness and efficiency.
- **Prize:** "AirPods 5" (as written on the slide) plus £100 of fossils.

### 3.9 MLH prize categories

From the [MLH event prizes page](https://www.mlh.com/events/hacktheburgh-9f/prizes), read 7 Nov 2026. The page lists 8 categories with one-line descriptions only. The full qualification rules are behind each category's "Read more" link and have **not been read yet**. The prize shown is the label above each heading, so the mapping is inferred from the layout.

| Category | What the page says | Prize |
|---|---|---|
| Best Use of Gemini API | "push the boundaries of what's possible with AI using Google Gemini" | MLH swag kits |
| Best Use of ElevenLabs | "Deploy natural, human-sounding audio with ElevenLabs" | Wireless earbuds |
| Best Use of Entire | "the Git forge for agent-human collaboration" | Mini portable projector |
| Best Use of Solana | Solana network for infrastructure | Hardware wallets |
| Best Use of Tiger Data | high-performance databases without complex setup | Stream Deck Mini |
| Best Use of Vultr | cloud hosting for high-performance projects | Assorted prizes |
| Best Use of Auth0 | "Auth0 wants your applications to be secure!" | Wireless headphones |
| DEV Writing Challenge | publish the project's story on dev.to after the event | $100 |

**Practical consequences:** these are add-ons, not main tracks. A project can pick up several by using the technology somewhere real: Gemini as the model, Auth0 for login and approvals, Tiger Data for storage, Vultr for hosting, ElevenLabs for voice. The DEV post costs only a write-up after the event. Read each "Read more" page before relying on a category.

---

## 4. Team

| Person | Relevant strengths |
|---|---|
| Hamish | Agentic pipelines, VLMs, speech recognition, local AI and quantisation, multi-agent coding (ran 11 agents at Code for Good) |
| Aiden | Full-stack TypeScript, React/Svelte, Node, Postgres; web-development lab support; dissertation on live coding quizzes with AI feedback |
| Jake | AI/ML and data engineering, FinBERT sentiment, prediction-market calibration, Rust, Flutter; fund analyst |
| Mano | Embedded and simulation (MATLAB/Simulink, CARLA), C#/.NET telemetry, design and video production |

---

## 5. Project options

| Option | Tracks it can enter | Team fit | Build risk in 24 h | Demo |
|---|---|---|---|---|
| A. Adaptive coding agent | InstaLILY, JetBrains, Metaview | Strong: Aiden's teaching, Hamish's multi-agent work | Medium; depends on InstaLILY's kit | Their engineers use it live |
| B. Basket Agent (shopping list in, best basket out) | Bank of Scotland, Wordsmith, Metaview; HRT only weakly | Good | Medium to high; supermarket sites may block bots | A judge watches it shop |
| C. Viridien log extraction | Viridien, Metaview; G-Research is a stretch | Strong: close to Hamish's STMicro work, plus Jake's ML and Mano's signal processing | Medium; well-defined task | Accuracy on their hidden test set |
| D. Forecast calibration game | HRT, G-Research, Metaview | Strong for Jake | Low to medium; public data APIs | Judges play it on their phones |
| E. Diff Risk (flags risky AI-written code) | JetBrains, Metaview | Good | Low as a command-line tool | A seeded bad change gets caught |
| F. Scam Call Shield | Metaview; Bank of Scotland is a stretch | Good | Medium (Twilio, network) | A judge takes a live scam call |

### A. Adaptive coding agent
An agent in the IDE that behaves differently for each persona. For a beginner it explains and asks guiding questions rather than fixing the code. For an engineer it does exactly what was asked, quickly, with minimal chat. A third persona is of the team's design (for example a teacher or a hardware engineer).
- **For:** two tracks overlap almost exactly. The scoring is the clearest of any track, and the prize includes an interview.
- **Against:** the full brief and team kit have not been read yet. Hidden tests mean failures you cannot see. Strong coding teams will compete.

### B. Basket Agent
A user gives a shopping list and priorities (cheapest, greenest, fewest shops, diet). A browser agent goes through two or three supermarket websites and builds the best basket, explaining each swap. Sustainability data could come from the Open Food Facts API. For Wordsmith's legal bonus, it could check each site's terms and robots.txt before acting.
- **For:** a real everyday problem. It fits two sponsor briefs at once and makes a visible, relatable demo.
- **Against:** it depends on outside websites. Cost-of-living apps are a common hackathon idea. Browser agents can be slow and unreliable live.

### C. Viridien log extraction
A computer vision pipeline that produces the required CSV and annotated image for each document.
- **For:** an objective score. Specialised entries probably mean fewer competitors. A direct match to the team's computer-vision experience.
- **Against:** effectively one sponsor track and the smallest prize. Hidden-test accuracy is unforgiving. Less of a crowd-pleaser for the general prize.

### D. Forecast calibration game
A phone game that scores how well players' confidence matches outcomes (Brier score), using public prediction-market questions, with an AI opponent.
- **For:** fits HRT and G-Research, uses public data, fun to demo.
- **Against:** Jake's earlier calibration code cannot be reused under the rules. It risks becoming a dashboard unless it stays a game. Quant firms will have seen many finance projects.

### E. Diff Risk
A tool that marks the risky parts of AI-written code changes (authentication, deleted tests, money handling) so reviewers look there first.
- **For:** the simplest build, and a real developer pain.
- **Against:** only JetBrains plus the general prize. Similar commercial tools exist.

### F. Scam Call Shield (from the 6 November call)
A live scam-call warning, with the full spec in the "Possible Projects" doc.
- **For:** the most spec work already done, and the most memorable demo.
- **Against:** no matching track (there is no fraud or security track). It relies on Twilio, and the telephony is the riskiest part of any option.

### What should decide it
- **Most tracks per codebase:** A or B (three each); D also reaches three.
- **Clearest scoring and the best odds of a measurable result:** A or C.
- **Lowest build risk:** E, then D.
- **Career value:** A includes an interview. Every other sponsor has a hiring stand to talk to over the weekend.
- **Biggest unknowns:** InstaLILY's team kit (A) and how supermarket sites respond to bots (B). Each can be checked in under 30 minutes.

---

## 6. Open questions and checks

- [ ] Scan InstaLILY's QR code for the full brief and team kit.
- [ ] Get JetBrains' judging-criteria document (QR code at their booth, or Discord).
- [ ] Collect the JetBrains OpenAI API key (one per team). Keep it out of the repo.
- [ ] If option B: spend 20 minutes testing Tesco, Asda and Sainsbury's with an automated browser (Playwright), and check Open Food Facts coverage of UK products.
- [ ] If option C: find where Viridien's dataset is downloaded from, and when the held-out images are released.
- [ ] Confirm the submission page address and register a team member's Discord username.
- [ ] Decide which workshops to attend.

---

## 7. Agreed ways of working (from the 6 November call)

- One main challenge, a second only if confident in the first.
- The main feature must carry the demo on its own.
- No dashboards, and no "wrapper plus a dashboard".
- A physical demo on a real device where possible.
- Have a real answer on privacy.
- Show sponsors the flow on paper before coding.
- Feature freeze three hours before the deadline (09:00 Sunday), then rehearse and record a backup video.

---

## 8. Sources

- Opening ceremony recordings, 7 November 2026: HackTheBurgh intro, organisers' rules talk, HRT, Metaview, G-Research, JetBrains, Bank of Scotland, Wordsmith AI, InstaLILY, Viridien (machine-transcribed; names and numbers may contain transcription errors)
- Photographed slides: workshop schedule, sponsor challenge and prize table, InstaLILY judging and prizes, Viridien challenge, approach, dataset, outputs and considerations
- [HackTheBurgh](https://hacktheburgh.com/), [itinerary](https://hacktheburgh.com/itinerary), [code of conduct](https://hacktheburgh.com/code-of-conduct)
- [MLH event prizes page](https://www.mlh.com/events/hacktheburgh-9f/prizes) (read 7 Nov 2026)
- Wordsmith sponsor deck: `research/hamish+aiden/Wordsmith/HackTheBurgh — Wordsmith.pdf`
- Team call transcript, 6 November 2026, and the "Possible Projects" doc
