<!-- Converted from slides-instalily-track-hacktheburgh-2026.pptx on 7 Nov 2026. The original file is the source of truth. -->

## Slide 1

- THE AGENTIC IDE CHALLENGE
- INSTALILY
- 1
- Build a coding agent that
- adapts to whoever’s using it.
- Edinburgh · 7–8 November 2026 · InstaLILY
- HACKTHEBURGH 2026  ·  SPONSOR TRACK

## Slide 2

- WHO WE ARE
- 2
- INSTALILY
- InstaLILY is an AI-native software company.
- We build AI agents into the flow of real businesses, so work gets faster, more efficient and easier to see.
- SIGNALS WE LOOK FOR
- Confidence
- Client-facing, and owns the result.
- Creativity
- Features people want to use.
- Strong engineering
- Systems-level understanding, not just code that runs.

## Slide 3

- THE CHALLENGE
- 3
- INSTALILY
- Build an AI coding agent that helps someone
- debug, refactor or engineer a project,
- and adapts to who they are.
- Your agent is never told who it’s talking to. We test two users; you design for a third.
- The beginner
- Plain words, one step at a time, the real cause explained.
- The engineer
- Short, exact, the smallest change, honest about it.
- Your persona
- Design for one more kind of person, of your choosing.
- Our reviewers test your persona live, and you show us who it is for, and why, in your demo.
- Your agent is one command we run for each message. Tools, memory, subagents and the interface are up to you.

## Slide 4

- STARTER IDEAS
- 4
- INSTALILY
- A few seeds to get you going
- The patient tutor
- Gives hints, not answers, when the user wants to learn.
- The quiet senior
- Smallest diff, keeps to your boundaries, says what changed.
- The codebase guide
- Maps an unfamiliar repo for someone on day one.
- Your wildcard
- A data scientist, a designer, a screen-reader user…
- Tip: fork an open-source editor (Code-OSS, VSCodium). Building on open source is fine if you say so.

## Slide 5

- EXAMPLE
- 5
- INSTALILY
- One way a beginner session could go
- python_programs/pascal.py
- 4
- for r in range(1, n):
- 5
- row = []
- 6
- for c in range(0, r):
- 7
- upleft = rows[r - 1][c - 1] if c > 0 else 0
- 8
- upright = rows[r - 1][c] if c < r else 0
- 9
- row.append(upleft + upright)
- Line 6: the real cause
- Line 8: where it crashes
- After the fix: 5 tests pass
- It crashes with an IndexError. I want to understand why, not just get a fix.
- AGENT
- The real cause is line 6: range stops before its end, so each row is one item short. I’ve changed it to range(0, r + 1) and all 5 tests pass. Quick check: what does range(0, 3) give you?
- 0, 1, 2?
- Inspiration only, from a mock editor built on a public example. Yours can look completely different.

## Slide 6

- JUDGING
- 6
- INSTALILY
- How we’ll judge it
- 01
- Clear the bar
- Same hidden tests for every team.
- 02
- Adapt to the user
- Does what was asked, no more. Reports honestly.
- 03
- Win over real people
- Our engineers use it live, with your persona.
- HINTS
- Understanding your user weighs the most.
- We score user value, not difficulty.
- Do what’s asked, respect limits, ask only when needed.
- Each persona is scored separately & equally

## Slide 7

- PRIZES
- 7
- INSTALILY
- What’s up for grabs
- 1ST PLACE
- Fast-track interview
- With InstaLILY, for the winning team.
- Sony WH-1000XM5
- Headphones, for the winning team.
- 2ND PLACE
- Logitech MX Master 3S
- Mouse, for the runners-up.
- EVERY TEAM
- Expert feedback
- A review from four InstaLILY engineers.
- Aimed at final-year students. The top prize is an interview, so you’ll get the most from it if you’re graduating soon. Everyone’s welcome to enter.

## Slide 8

- Go build something
- people want to use.
- And have fun with it!
- Submissions close Sun 8 Nov, 12:00  ·  Team kit will be provided
- INSTALILY
- 8
- SCAN FOR THE FULL BRIEF
