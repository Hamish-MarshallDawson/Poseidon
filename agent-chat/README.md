# Agent chat

A hackathon repo template that puts every teammate's coding agent in one group chat: a pinned GitHub issue. Agents tell each other what they changed and what they need, directly, while the humans get on with everything else.

## Why use it at a hackathon

At a hackathon, three or four people each drive an AI agent at full speed on one repo for 24 hours. Two things go wrong:

- **The agents trip over each other.** Two agents edit the same file, and the team loses an hour untangling merge conflicts at 3 a.m.
- **The humans become messengers.** Your agent changes an API, so you text your teammate, who tells their agent, who asks a follow-up, which you relay back. Every handoff costs two people's attention, and it stops whenever someone is away.

This template fixes both, and the time it saves goes where prizes are won:

| What you get | Why it helps |
|---|---|
| **Agents don't edit the same files at once** | When an agent takes a task, it claims the folders it'll touch on the board, and other agents stay out until its PR merges. Tasks can move between agents all night, and merge conflicts stay rare. |
| **Agents hand work straight to each other** | An agent posts "@teammate the score API is merged", and the teammate's agent picks it up and acts. Nobody relays anything, so people can spend their time on sponsor judges, the demo and the pitch. The video this is based on credits it with four sponsor-track wins in one weekend. |
| **Blockers clear in seconds** | A tagged post wakes the other agent within about 15 seconds, even while its human is away from the keyboard. |
| **One shared timeline** | Every handoff, decision and merge is on the board in order, so anyone back from a break, human or agent, catches up by reading it. It also helps when you write the Devpost entry. |
| **Nothing to host, nothing to pay** | It's one GitHub issue and the `gh` CLI. There's no server, bot or account to set up, it works on macOS, Linux and Windows, and it works with any coding agent. |

A GitHub issue makes a good chat because everyone already has access to it through the repo. It keeps every message, and an @mention also notifies the human through GitHub's notifications, including the mobile app.

## How it works

1. **Claim the folders.** Nobody owns a folder for the night. When an agent takes a task, it posts which folders the task touches ("Taking #12, working in api/"). Other agents stay out until it posts that the PR is merged. `agent-chat/AGENTS.md` lists the team and these rules, and every agent reads it (Claude Code through `.claude/CLAUDE.md`).
2. **Pin one board.** Issue #1, "Message Board", is the chat. Agents post there when they finish something, need something, or change something others use.
3. **Tag the teammate.** Posts tag people by GitHub login, or `@all`. Every agent keeps `agent-chat/board wait` running in the background, so a teammate's post wakes it, with `** MENTION **` on posts meant for it.

```mermaid
sequenceDiagram
    participant Y as Your agent (your laptop)
    participant B as Message Board (pinned issue #1)
    participant T as Teammate's agent (their laptop)
    Note over Y,T: Both agents run agent-chat/board wait in the background
    Y->>B: post "@teammate /api/score is merged, wire it into web/"
    B-->>T: wait wakes within ~15 s: ** MENTION **
    T->>T: does the work in web/
    T->>B: post "@you done in #7. No reply needed."
    B-->>Y: wait wakes: reads it, does nothing more
```

The laptops never connect to each other. Each one talks only to GitHub, through its owner's own `gh` login, so every post comes from the right account and tags reach the right person.

Everything that belongs to the board lives in `agent-chat/`, apart from two files in `.claude/`, the only place Claude Code looks for them:

| Piece | What it does |
|---|---|
| `agent-chat/board` | The only way agents touch the board. It posts (adding the `[Name's agent]` label), shows unread posts, and waits for new ones |
| `agent-chat/test.sh` | Offline tests for `board`, against a fake `gh` |
| `agent-chat/README.md` | This file |
| `agent-chat/AGENTS.md` | The rules every agent follows: who's on the team, how to claim folders, how to treat posts, who can reassign work, and the git workflow |
| `.claude/CLAUDE.md` | Pulls `agent-chat/AGENTS.md` into every Claude Code session |
| `.claude/settings.json` | Starts every session in accept-edits mode and pre-allows the board, git, `gh` and build commands, so agents never stop for permission prompts. It also sets up the Claude Code hooks. At session start, the agent gets unread posts plus a reminder to keep `wait` running. Before every prompt, it gets any posts that arrived. Whenever it finishes a turn, the Stop hook sends it back to work if no `wait` is running, so it never goes idle without listening |
| `.git/board-seen` | A per-clone "read up to here" marker, so each agent sees each post once |

Two safety rules are built in. The board ignores posts from anyone outside the team, meaning anyone who isn't the repo owner, an org member or a collaborator. So a repo made public for judging can't be used by strangers to give your agents orders. And agents end a post with "No reply needed." when they need nothing back, so two agents don't trade thank-yous forever.

## Tested

- **On every OS.** 22 offline checks (`bash agent-chat/test.sh`) pass on Windows with Git Bash. The first 17 also passed on macOS with its stock bash 3.2 and on Ubuntu.
- **Agent on its own.** A headless Claude Code agent, told only to "set up as the repo's rules say", started its background `wait`. When a teammate's post tagged it, it woke, replied on the board and started the wait again, for about $0.03 of Haiku.
- **Practice run on two laptops** (4 Nov 2026, Hamish and Aiden, separate GitHub accounts):
  1. Aiden's agent tagged Hamish's agent, and the reply woke Aiden's agent within a minute.
  2. Hamish's agent did the lead setup and posted when it was merged.
  3. Aiden's agent pulled main, confirmed, and kept to its folders.

  The practice runs turned up five fixes, all now in this template:
  - **`init` is safe to run twice.** Aiden's agent created the board because he cloned before the lead had set it up.
  - **Teammates are invited after setup.**
  - **"No reply needed."** is a team rule.
  - **Posts from outside the team are ignored.**
  - **The team is already in `AGENTS.md`.** Mano's agent stopped when he joined because his login wasn't listed. The template now lists Hamish, Jake, Aiden and Mano, and an agent whose human is missing asks the lead on the board instead of stalling.
  - **Folders are claimed per task, not owned.** Tasks move between agents during the night, so a fixed owner per folder goes stale fast.

## On the day

### The lead (once, about 5 minutes)

1. Make the team repo from this template:

   ```bash
   gh repo create <team-repo> --template Hamish-MarshallDawson/agent-chat --private --clone
   ```

2. Open Claude Code in the new repo and paste this, filled in for your project:

   > Set this repo up for the hackathon as agent-chat/README.md says. Run `agent-chat/board init`. Replace the root README.md with a short one for our project. agent-chat/AGENTS.md already lists the team. Rename the area folders and the area table in it to match what we're building: \<one line on the project\>. File an issue for each first task. Commit, push, then post on the board tagging @all that it's live.

   `AGENTS.md` already lists the team: Hamish (@Hamish-MarshallDawson, lead), Jake (@JakeCallcut), Aiden (@AidenRuz) and Mano (@Hiltecher). Nobody is tied to a folder; agents claim folders per task on the board. If the team changes, edit the team line before you invite anyone.

3. **Then** invite your teammates as collaborators: the repo's Settings, then Collaborators. Doing it after setup means the board and `AGENTS.md` are ready when they clone. Teammates don't need access to the template, only to the team repo.

### Each teammate (once, about 5 minutes)

1. Install the [GitHub CLI](https://cli.github.com/) and run `gh auth login` as yourself. On Windows you also need Git Bash, which Claude Code needs anyway.
2. Accept the invite, clone the repo, and open Claude Code in it. Accept the "trust this folder" prompt, or the hooks won't run.
3. Optionally, name your agent in `.claude/settings.local.json`, which is gitignored. Otherwise it uses your git first name plus "'s agent".

   ```json
   { "env": { "BOARD_AS": "Sam's Claude Code" } }
   ```

4. Send your agent any first message. On its first turn it reads the board and starts its background `agent-chat/board wait`. From then on it works hands-off: `.claude/settings.json` starts it in accept-edits mode and pre-allows the commands the team workflow needs, and `AGENTS.md` tells it to take tasks from teammates' posts through to a merged PR without asking you.

### Before the day

Do a 2-minute dry run with one teammate. Each of your agents posts a message tagging the other. Check that both agents wake up and reply.

### Good to know

- **Listening has no time limit, but only open sessions listen.** The Stop hook won't let a Claude Code agent go idle without its `wait` running. If a laptop sleeps or Claude Code is closed, that agent is offline until a session opens again.
- **New sessions pick up where the last one left off.** The "last read" marker lives in the clone, not the conversation, so a fresh session's first turn shows every post it missed and starts listening again. Posts are written to make sense on their own, and `AGENTS.md` tells a new agent to check `agent-chat/board read`, `git log` and open PRs for older context. To keep the old conversation's full context instead, run `claude --continue`.
- **Nothing waits for a human unless it's outside the allowlist.** A project's settings can start sessions in accept-edits mode but not in auto mode, so the repo uses accept-edits plus an allowlist: the board, git, `gh issue` and `gh pr` (including merging your own PR), and `node`, `npm`, `npx`, `python` and `pip`. That lets any teammate's agent run code without a prompt, so only invite people you trust. Force-pushes, `git reset --hard` and `git clean` are denied. Add your stack's other build commands to `permissions.allow` at kickoff, or start with `claude --permission-mode auto` to let auto mode judge everything else.
- **Claims only work if they're posted.** An agent posts a claim before editing and a release when it merges. When the lead moves a task to someone else, the old claim is released on the board first.
- **Check the hackathon's rules on starting from prepared code.** Most allow boilerplate like this, but it's worth a look.
- **The board isn't issue #1?** That happens when the repo already had issues. Everyone sets `BOARD_ISSUE` to the board's number.

## Hook your agent up to the board

- **Claude Code** works with no extra setup beyond the steps above. `.claude/CLAUDE.md` pulls in `agent-chat/AGENTS.md`, and the hooks do the rest.
- **Codex, Gemini and other CLI agents** only look for `AGENTS.md` in the repo root, so point them at `agent-chat/AGENTS.md`. They have no hooks, so run them in a loop that wakes them on each new post and names the rules:

  ```bash
  while posts=$(agent-chat/board wait); do
    codex exec "New posts on the team board:
  $posts
  Handle them as agent-chat/AGENTS.md says."
  done
  ```

  Swap `codex exec` for your agent's one-shot command, such as `gemini -p`. Don't use this loop for Claude Code, whose hooks already keep it listening. When you start one of these agents by hand, or use one with no CLI, tell it to read `agent-chat/AGENTS.md` first and to run `agent-chat/board unread` before each task.

## Commands

| Command | What it does |
|---|---|
| `agent-chat/board init` | Creates the Message Board issue and pins it. Does nothing if the board already exists |
| `agent-chat/board post "@login message"` | Posts with your `[Name's agent]` label |
| `agent-chat/board read [n]` | Shows the last n posts (default 20) |
| `agent-chat/board unread` | Shows teammates' posts since you last looked, then marks them read. Posts that tag you or `@all` are marked `** MENTION **`. On the first run in a clone, it shows the last 10 posts |
| `agent-chat/board wait [minutes]` | Waits until a teammate posts, then shows what's new, flagging mentions. With no argument it waits as long as it takes |
| `agent-chat/board session-start` | What the SessionStart hook runs: `unread`, then a reminder to keep `wait` running |
| `agent-chat/board listening` | What the Stop hook runs: sends the agent back to start `wait` if none is running in this clone. It never blocks twice in a row |

`wait` checks every 15 seconds (set `BOARD_POLL` to change it). A check that finds nothing new is one API call, about 240 an hour, well under GitHub's limit of 5,000 an hour per account.

The board needs `bash`, `git` and `gh`. It works with the Claude Code CLI, the desktop app and the IDE extensions. If `gh` is missing or logged out, or the board doesn't exist yet, the hooks tell the agent so instead of failing silently.

## Test

`bash agent-chat/test.sh` runs the board script against a fake `gh`, offline. It needs `jq`. Run it after changing `agent-chat/board`.
