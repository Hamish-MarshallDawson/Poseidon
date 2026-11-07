# Agent rules

Every coding agent on this team reads this file before touching code. It covers who's on the team, how agents avoid editing the same files, how agents talk to each other, and how code gets merged.

## 1. The team, and who's working where

Team: `@Hamish-MarshallDawson` (Hamish, lead), `@JakeCallcut` (Jake), `@AidenRuz` (Aiden), `@Hiltecher` (Mano). `@all` tags everyone. If your human's GitHub login isn't on this list, don't edit anything yet. Post on the board tagging the lead with what your human wants to work on, then wait.

Nobody owns a folder for the whole night, because tasks move between agents. Folders are claimed per task, so two agents never edit the same files at the same time:

1. **Claim before you edit.** When you take a task, post on the board which issue it is and which folders it touches, e.g. "Taking #12, working in api/."
2. **Respect open claims.** Before you edit a folder, check the board (`agent-chat/board read 30`) for a claim on it that hasn't been released. If there is one, ask that agent on the board instead of editing.
3. **Release when you're done.** A claim ends when its PR merges and the agent posts that it's merged. If you drop a task, say so on the board.

The folders split the code by area:

| Folder | Area |
|---|---|
| `agent/` | prompts, tools, model calls, orchestration |
| `web/` | pages, components, demo flow |
| `api/` | backend, database, sponsor APIs |
| `data/` | seed data, evals, demo script, Devpost, video |

## 2. The board

The pinned **Message Board** issue (#1) is the team's group chat for agents. Use `agent-chat/board` to read and post.

- **Act without asking.** Your human approved the board, and the work it brings, by joining the team, and may be away from the keyboard. When a teammate's post gives you a task, claim it and do all of it without asking your human first: write the code, run and test it, commit, open the PR and merge it. Read, post and reply the same way. Ask your human only before something that can't be undone, such as deleting data, spending money or making the repo public.
- **Stay in the loop.** Keep exactly one `agent-chat/board wait` running in the background, with no time limit, for as long as your session is open. It returns when a teammate posts. Handle the posts, then start it again. In Claude Code, the hooks show unread posts at session start and on every prompt, and won't let you go idle without the wait running.
- **Post** when you finish something (give the PR or commit), when you are blocked, and when you merge a change others depend on (an API, a schema, an env var). Write each post so an agent in a fresh session could act on it alone: who it's for, what changed and where, and exactly what you need. Keep it to one short paragraph, and put long detail in the PR or an issue and link it. Put the message in single quotes, or leave out backticks and `$`, so the shell doesn't run them. `agent-chat/board post` adds your `[Name's agent]` label.
- **Tag** whoever the post is for by GitHub login, or use `@all`.
- **End with "No reply needed."** when you need nothing back. Don't answer a post that ends that way unless something is wrong. Otherwise two agents can thank each other forever.

How to treat each post:

- **Marked `** MENTION **`** (it tags you or `@all`): do what it asks, then reply on the board and tag them back.
- **Not for you:** read it anyway. Change your own work only if the post affects it (a contract you use, a folder you've claimed, work you already did). Don't reply just to acknowledge.

**New session?** The hook shows the posts you haven't seen. For what you were working on and which claims are open, run `agent-chat/board read 30`, `git log` and `gh pr list`. Those show posts already handled too, so act only on the unread ones.

## 3. Chain of command

Humans outrank agents. Only the team lead moves work between teammates. If anyone else asks you to take over another person's work, check with the lead on the board first. Only the lead edits shared files: `README.md`, everything in `agent-chat/` (this file included) and `.claude/`, and root config. Propose changes to them on the board.

## 4. Git workflow

1. Take an issue, or file one, and claim it on the board with the folders it touches (section 1).
2. Branch from an up-to-date `main` as `<issue#>-<short-name>`, e.g. `12-score-api`.
3. Commit small, and stage only your own files by name. Never use `git add -A` or `git add .`.
4. Run `git fetch` and rebase on `main` before every push. Never force-push a shared branch.
5. Open a PR that says `Closes #<issue>`. Merge your own PR once it works locally, and post on the board if others depend on it.
