# Team skills: HackTheBurgh XIII

All four of us are final-year MEng Software Engineering students at Heriot-Watt University, graduating in 2027. This file draws on Hamish's CV and on Aiden's, Jake's and Mano's portfolio sites (aidenruz.com, jakecallcut.dev, mano.ong), as read on 6 November 2026.

---

## At a glance

| Area | Hamish | Aiden | Jake | Mano |
|---|---|---|---|---|
| Python | Strong | Yes | Strong | Yes (CARLA work) |
| TypeScript / JavaScript | Yes | Strong | Yes | |
| C / C++ | Yes | C | | |
| Other languages | Java, SQL | SQL | Rust, Dart | C#, MATLAB |
| Front end | React, Next.js | React, Svelte, HTML/CSS | Flutter | |
| Back end and data | FastAPI, Node, PostgreSQL | Node, PostgreSQL, MongoDB | APIs, Firebase, Socket.IO | |
| ML and AI | VLMs, LoRA, quantisation, RAG, PyTorch, speech recognition | AI-assisted feedback (dissertation) | PyTorch, Hugging Face, diffusion models, FinBERT, scikit-learn-style ML | |
| Computer vision | OpenCV, CLIP, Grounding DINO, SAM | | Machine vision (album covers), diffusion for wafer images | |
| Data analysis and statistics | Bayesian optimisation, evaluation design | | Pandas, Brier scores, Wilson intervals, logistic regression | Lap-time simulation, curve fitting |
| Agentic coding | Multi-agent orchestration, MCP, AGENTS.md, Claude Code | Agent harness with orchestration (Claude plus GPT or DeepSeek workers) | AI-assisted development | |
| DevOps and cloud | Docker, AWS EC2, Azure, GitHub Actions, Cloudflare | Docker, CI/CD | Docker, Azure, Kubernetes | |
| Embedded and hardware | ROS, Raspberry Pi, robotics | | Raspberry Pi (smart home hub) | ARM Cortex (MAX32666), Simulink, PLL algorithms |
| Simulation | ROS latency simulation | | | CARLA, IPG CarMaker, MoTeC telemetry |
| Design, media and pitching | Branding and media for Formula Student | UX clarity | Figma UI/UX | Graphic design, video, YouTube channel |
| Teaching and explaining | Employability talks, student rep | Web-development lab support | Writing (published essays) | YouTube explainers on F1 technical concepts |

---

## Hamish Marshall Dawson

**Current role:** AI and Machine Learning Engineer Intern, STMicroelectronics, Edinburgh (May to December 2026).

**Experience**
- Built a VLM fault-detection pipeline with 98% accuracy across 25 fault classes.
- Deployed it on Azure and cut runtime on 10,000 images from 10 hours to 35 minutes by profiling on an H100 and batching by LoRA adapter.
- Made an AI pipeline measurable with reproducible train/test splits and Bayesian-optimised parameters.
- Ran AI-tooling sessions that led 8 senior engineers outside software to adopt GitHub Copilot.
- Research intern in human-robot interaction (summer 2025): a 12-participant latency study, a ROS latency simulation for a Tiago dual-arm robot, and a paper accepted at British HCI 2026.
- JPMorganChase Code for Good (October 2026): led the front end and the overnight build, and orchestrated 11 parallel coding agents against Figma, Playwright and context7 MCP servers.

**Technical skills**
- Languages: Python, TypeScript, C++, C, Java, SQL, JavaScript.
- AI and ML: agentic pipelines, VLMs, CLIP, LoRA, quantisation (FP8, NF4), RAG, embeddings, LLM evaluation, PyTorch, Hugging Face, OpenCV, speech recognition and text-to-speech.
- Software: Next.js/React, FastAPI, Node, PostgreSQL, Drizzle, Zod, Playwright, Vitest, Docker, AWS EC2, Azure, GitHub Actions.
- Agentic coding: multi-agent orchestration, MCP, AGENTS.md conventions, Claude Code, GitHub Copilot.
- Robotics: ROS1/ROS2, Raspberry Pi.

**Projects:** TensorRoom (local AI interior redesign that fits 31 GB of models into 16 GB of VRAM), LocalMind (self-hosted assistant on an RTX 5080), Gyminit (local-first training tracker PWA), Lothian Bus Tracker (C++ on a Raspberry Pi), robotic-arm dissertation (89/100).

**Other:** University Prize winner, student representative, Branding and Media Manager for Heriot-Watt Racing (15+ sponsorship partnerships), volunteer judo coach.

**Best hackathon roles:** AI pipeline and agent lead, multi-agent coding orchestration, evaluation design, front end.

---

## Aiden Ruz

**Focus:** full-stack software engineer, interested in how an application fits together, from its look and feel to the systems behind it.

**Experience**
- Medical AI research: in a two-person team, brought a medical AI research tool to the web so researchers can inspect model predictions and heatmaps.
- Digital-twin internship: built Cesium tools for annotating and measuring 3D maps and photogrammetry models for a university digital-surveying platform.
- Web-development lab support: helped students with HTML, CSS and JavaScript, explaining concepts and debugging with them.

**Technical skills**
- Languages: TypeScript, Python, C, SQL.
- Interfaces: HTML, CSS, React, Svelte.
- Services and data: Node.js, PostgreSQL, MongoDB.
- Delivery: Docker, Git, CI/CD.
- Agentic tooling: his own agent harness with orchestration and delegation; uses DeepSeek through OpenRouter for fast, cheap research agents.

**Projects:** Hakoniwa (self-hosted streaming platform that matches sources to the correct episodes), KeySight (sheet-music reading tutor that grades each note from a MIDI piano), live coding quizzes (dissertation: students run Python inside a quiz, instructors review code, output and AI-assisted feedback).

**Strengths he describes:** bringing fragmented systems together, thinking through edge cases, making system behaviour clear, and building software people can trust.

**Best hackathon roles:** full-stack and app lead, integration across parts, UX for beginners and learners, edge-case testing.

---

## Jake Callcut

**Focus:** software engineer working on AI, machine learning and data engineering, with an emphasis on reliable systems and rigorous evaluation.

**Experience**
- AI and ML Engineer Intern, STMicroelectronics (May 2026 to present): fine-tunes diffusion models with LoRA to generate synthetic wafer images. This improved defect-detection accuracy by 8% and increased training data by 20%. He benchmarks with PyTorch, CNNs and transformers.
- Software Engineer, Diamond (July 2025 to May 2026): designed and built a startup's consumer mobile app and business platform end to end, and contributed to investor pitches and funding applications.
- Software Engineer, GI Healthcare Industries (August 2024 to November 2025): built a fault-tolerant multi-machine control system with Flutter, TypeScript and Socket.IO, and attended stakeholder demos.
- UI/UX Intern, GI Healthcare Industries (summer 2024): designed the interface in Figma, from wireframes to developer handoff, working with engineers and military personnel.
- Fund Analyst, Heriot-Watt Investment Society (October 2026 to present), in the Technology and Professional Services team.

**Technical skills**
- Languages: Python, TypeScript, Rust, Dart/Flutter.
- ML and AI: PyTorch, Hugging Face, diffusion models, FinBERT and NLP, machine vision.
- Data: Pandas, Matplotlib, statistical methods (Brier scores, Wilson intervals, logistic regression), API data pipelines.
- Tooling: Git, Docker, Azure, Kubernetes, Jupyter, AI-assisted development.

**Projects:** social-sentiment stock prediction by sector (FinBERT, Streamlit), Tensor Room (with Hamish), prediction-market calibration study (Kalshi and Polymarket), T212 Client (read-only Rust API client for Trading212), Lumina (IoT smart home with Flutter and a Raspberry Pi hub), a music genre classifier from audio features and cover art (50,000+ tracks), a social mobility data study. More notebooks are on his Kaggle.

**Other:** writes essays on technology; A Levels in Maths, Physics and Computer Science (AAA). He has a JPMorganChase final-stage interview on Monday 9 November.

**Best hackathon roles:** data and evaluation lead, ML modelling, statistics and honest metrics, finance domain knowledge, mobile if needed.

---

## Mano Manikandan

**Focus:** software and embedded systems engineer, with simulation and motorsport.

**Experience**
- Embedded Systems Intern, Analog Devices (summer 2026 to present): benchmarks phase-locked loop and zero-crossing frequency-tracking algorithms for grid synchronisation on a MAX32666 ARM Cortex, and builds a Simulink verification framework.
- Embedded Systems Intern, Analog Devices (summer 2024): built a curve-fitting algorithm in MATLAB and Simulink, shipped as a block in the company's standard Simulink library, and optimised a compiler pipeline for runtime.
- Vehicle Dynamics Engineer, Heriot-Watt Racing (2025 to present): lap-time simulation and vehicle setup research in IPG CarMaker.
- Operations Director, Heriot-Watt Racing (2024): ran sponsorship, budgeting and HR for a 50-person Formula Student team.
- VCU Software Engineer, Heriot-Watt Racing (2023): rewrote the Simulink control logic for the car's vehicle control unit and looked after software infrastructure and documentation.
- Race Engineer Intern, Virtual Drivers by TX3 (summer 2024): MoTeC telemetry analysis to tune setups and driver performance.

**Technical skills**
- Languages: C#/.NET 8, Python, MATLAB.
- Embedded and signal processing: ARM Cortex, Simulink, PLL and frequency-tracking algorithms, curve fitting on large datasets.
- Simulation and telemetry: CARLA, IPG CarMaker, MoTeC, shared-memory telemetry, UDP streaming.

**Projects:** Automotive Simulation Framework (dissertation: CARLA interface to stress-test road and vehicle safety standards), SF1000 telemetry bridge (C# app streaming Assetto Corsa and rFactor 2 telemetry to a Thrustmaster wheel over Wi-Fi), PLL benchmark test bench.

**Outside work:** founded the Assetto Formula Open sim-racing league (telemetry tools, Discord bots), the Camber F1 YouTube channel (700+ subscribers, about 1,000 views a video, 500+ Discord members, explaining F1 technical concepts simply), and the design agency Maadu Media (branding, graphic design, video, client management).

**Best hackathon roles:** signal processing and numerical methods, simulation and stress-testing, hardware, pitch, slides and demo video, explaining technical ideas simply.

---

## How the skills map to this weekend's tracks

| Track | Strongest people for it |
|---|---|
| InstaLILY (adaptive coding agent) | Hamish (agents), Aiden (teaching beginners, coding quizzes), Mano (explaining simply, a third persona) |
| JetBrains (help the developer) | Hamish and Aiden (agentic coding workflows) |
| Viridien (log extraction) | Hamish (VLM and vision pipelines), Jake (ML and evaluation), Mano (signal processing) |
| HRT and G-Research (data, predictions, hidden patterns) | Jake (statistics, calibration, finance), Hamish (ML) |
| Wordsmith (browser agents) | Hamish (Playwright, agents), Aiden (integration) |
| Bank of Scotland (cost of living) | Jake (finance), Aiden (app), Mano (design) |
| Metaview (best overall) | Everyone; Mano for pitch and video |
