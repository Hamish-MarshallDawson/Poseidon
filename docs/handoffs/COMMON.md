# Rules for Aiden's backend agents (8 Nov 2026, from 03:45 UTC)

Team Hedged Bets, project POSEIDON, HackTheBurgh. Feature freeze 09:00 UTC Sunday 8 Nov. Aiden owns the backend
and the Tiger database. The integrator agent `be-integrate` (in worktree `59-ingest-resilience`) started you,
reviews your work and merges it. You report by ending your turn with your result; never `hc send` your parent.

- Read `agent-chat/AGENTS.md`, `backend/README.md` and `backend/dvm/sources/README.md`, then only the code your task
  touches. Plan and context: `docs/prediction-loop/PLAN.md`.
- **Board:** don't post and don't act on board posts; `be-integrate` relays. Skip the board-wait hook if it asks.
- **Never run the backend** (`python -m dvm`) with the real `.env`: it holds Hamish's AISStream key and the shared Tiger
  URL, so it would open a second AISStream connection and store every position twice. If you need a server for a
  test, set `AISSTREAM_API_KEY=` and point `TIGER_DATABASE_URL` at your own local database.
- **Tiger:** read-only only. Open sessions with `server_settings={"default_transaction_read_only": "on"}`. Never write
  to Tiger and never run `dvm.sources` jobs with `--allow-tiger`. Writes to Tiger happen only on the Vultr server,
  deployed through Hamish's laptop agent after `be-integrate` merges.
- **Local database for tests:** `docker run -d --name <you>-tsdb -p <your port>:5432 -e POSTGRES_PASSWORD=local
  timescale/timescaledb:latest-pg17`, and remove it when done. Tests that need it read `SOURCES_TEST_DATABASE_URL`.
- **GFW API:** the token is `GFW_API_TOKEN` in the repo `.env` (load it with python-dotenv; never print it, never put
  it in a command line, a log, a commit or a PR). The Vultr server's backfill uses the same token right now, so keep
  your total load modest: at most 4 requests in flight unless your brief says otherwise, stop and back off on any 429,
  and keep test runs short. GFW data is CC BY-NC 4.0.
- **Python** 3.12, venv `backend/.venv` (create it in your worktree: `cd backend && python3 -m venv .venv &&
  .venv/bin/pip install -r requirements.txt`). Noisy commands through `quiet-run`. Run tests from `backend/`.
- **Git:** your own worktree and branch. Stage files by name, never `git add -A` or `.`. Small coherent commits.
  `git fetch origin && git rebase origin/main` before every push. Never force-push. Open one PR with `Closes #<issue>`
  (or `Part of #<issue>` if your brief says so), saying what changed, how to run it and what you measured or tested.
  **Don't merge.**
- **Done means:** your tests pass, the backend suite still passes
  (`pytest -q tests --ignore=tests/stress --ignore=tests/test_tiger.py`), you exercised the real path you changed, and
  you end your turn with: PR URL, what's verified (with numbers), what isn't, in at most 200 words. If you are blocked
  on a decision, end your turn with the question.
