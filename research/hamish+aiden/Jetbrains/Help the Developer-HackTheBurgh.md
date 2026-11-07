<!-- Converted from Help the Developer-HackTheBurgh.docx on 7 Nov 2026. The original file is the source of truth. -->

# Help the Developer

JetBrains is here to help developers improve their coding experience. For this challenge, we're asking you to create an application, IntelliJ-based plugin, or ACP agent (connected via JetBrains Air) with the primary goal of making developers' lives easier.

Build with JetBrains Air:

Build your project using JetBrains Air in your JetBrains IDE. Air lets you run AI coding agents side by side, track and review their work in one place, and steer them with the IDE’s own intelligence behind them:

- Bring the agent you already use: Codex, Gemini, GitHub Copilot, Claude and Junie work out of the box, and others connect via ACP.
- No agent or subscription? Try Junie Lite for free.
- Agents work with the IDE’s deterministic tools, so they take fewer wrong turns and use fewer tokens.
- Getting started: install the Air plugin in your JetBrains IDE and read the Air documentation.

### Description

For this challenge, we're asking you to create an application, IntelliJ-based plugin, or ACP agent (connected via JetBrains Air) with the primary purpose of making the lives of developers easier. Some starting points:

- Routine test creator: consider what makes this more than "call the API with the function body": does it use surrounding context, existing test conventions in the repo, or catch edge cases a generic prompt would miss?
- Refactor suggester: what does codebase-aware refactoring look like, versus a suggestion that ignores how the rest of the project is structured?
- Your idea:  anything the team comes up with. The challenge is to create an application that will make your coding experience more comfortable.

Your application is expected to be an AI solution, (you can use the OpenAI API, another model, or an agent framework such as Koog for your task). Integrating your solution with JetBrains tools would be a great idea, but it is not a requirement.

### Expectations

We're mostly looking for good ideas with a proof of concept, so focus on this aspect. The final project could be:

- An ACP agent
- A web app
- A plugin
- A desktop app
- A mobile app

### Judging Criteria

Your submission will be evaluated based on the following criteria (in order of priority):

- Implementation and Proof of Concept: does it actually run and solve the developer pain point end-to-end, not just a mocked screenshot?
- User Experience and Interface: how naturally it fits into a developer's existing workflow; friction here kills adoption even for a technically strong idea.
- Innovation and Creativity: originality of the problem chosen and the angle taken, especially anything that goes beyond "wrap a prompt around a common IDE action" (see the note above).
- Agentic Development Process: did agents in JetBrains Air do real work on the project while you reviewed and steered them, rather than you accepting everything they produced? Extra credit for multi-agent workflows, such as different agents on different parts or a comparison of their results.
- Presentation: clarity of the demo and explanation of design decisions.

### Useful Resources

Air and agents

- Air in JetBrains IDEs and the Air plugin
- Junie: free Junie Lite option

Building an ACP agent

- Agent Client Protocol: the specification
- ACP Kotlin SDK
- ACP Registry: existing agents and how to submit your own
- Koog ACP guide: build an ACP agent in Kotlin and connect it to the IDE (beta, JVM only). It includes a ready-made acp-agent example in the Koog repo.
- Blog: Koog x ACP

Building a plugin

- IDE Plugin Generator: the fastest way to start. In IntelliJ IDEA 2026.1+ with Plugin DevKit, use File | New | Project | IDE Plugin.
- IntelliJ Platform Plugin SDK documentation
- Blog: IDE Plugin Generator – The New Beginning
