#!/bin/bash
# Deploy entry point on the Vultr server, installed root-owned at /usr/local/sbin/dvm-deploy (not under /opt/dvm, which
# the dvm user owns). CI cannot change this script; copy it to the server by hand when it changes.
#
# Two ways in:
#  1. CI (the GitHub Actions key). This script is that key's forced command in /root/.ssh/authorized_keys:
#       command="/usr/local/sbin/dvm-deploy",restrict ssh-ed25519 AAAA... github-actions-deploy
#     so the key can run nothing else. CI sends a tar on stdin:
#       tar -C frontend/dist -cf - . | ssh root@<server> frontend        deploys the frontend at once
#       git archive HEAD backend     | ssh root@<server> "backend <sha>"  only STAGES the backend
#  2. A supervisor with the admin key (Hamish's laptop agent; the key lives only on that laptop):
#       ssh root@<server> dvm-deploy status    lists staged backends
#       ssh root@<server> dvm-deploy apply     deploys the newest staged backend
#     Hamish's rule (8 Nov 03:36): no agent deploys the backend without that supervision.
set -euo pipefail
STAGE=/opt/dvm-staged   # root-only; the dvm user cannot write here

apply_backend() {   # $1 = staged tar
  local tmp
  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' EXIT
  chmod 755 "$tmp"   # pip runs as dvm and must read requirements.txt
  tar -x -C "$tmp" -f "$1"
  test -f "$tmp/backend/requirements.txt"
  sudo -u dvm /opt/dvm/backend/.venv/bin/pip install -q -r "$tmp/backend/requirements.txt"
  # Ctrl+C equivalent (KillSignal=SIGINT): the AISStream rules forbid a force-kill.
  systemctl stop dvm
  # .venv and data/ are not in git, so they survive; everything tracked is replaced.
  rm -rf /opt/dvm/backend/dvm /opt/dvm/backend/tests
  cp -r "$tmp/backend/." /opt/dvm/backend/
  chown -R dvm:dvm /opt/dvm/backend
  systemctl start dvm
  for _ in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
      echo "backend deployed and healthy: $(basename "$1")"
      # The delayed-source jobs (poll and backfill) run this same code: restart the running ones so they pick it
      # up. SIGINT stop, and each resumes from the source_windows ledger, so nothing is lost or refetched.
      systemctl try-restart 'dvm-poll-*' 'dvm-backfill-*' && echo "source jobs restarted"
      mkdir -p "$STAGE/applied" && mv "$1" "$STAGE/applied/"
      return 0
    fi
    sleep 2
  done
  echo "backend did not answer /health within 60 s" >&2
  journalctl -u dvm -n 40 --no-pager >&2
  return 1
}

if [ -n "${SSH_ORIGINAL_COMMAND:-}" ]; then
  # CI key: the requested command arrives here, never as arguments.
  read -r cmd arg _ <<< "$SSH_ORIGINAL_COMMAND"   # no word-splitting or globbing of CI input
  set -- "$cmd" "${arg:-}"
  case "${1:-}" in
    frontend)
      cd /opt/dvm/frontend
      rm -rf dist.new && mkdir dist.new
      tar -x -C dist.new
      test -f dist.new/index.html
      # coast.pmtiles is git-ignored (91 MB), so CI never has it: hard-link the copy kept on the server.
      mkdir -p dist.new/basemap
      [ -e dist.new/basemap/coast.pmtiles ] || ln /opt/dvm/tiles/coast.pmtiles dist.new/basemap/coast.pmtiles
      rm -rf dist.old
      [ -d dist ] && mv dist dist.old
      mv dist.new dist
      echo "frontend deployed"
      ;;
    backend)
      sha=${2:-unknown}
      [[ "$sha" =~ ^[0-9a-f]{7,40}$ ]] || sha=unknown
      install -d -m 700 "$STAGE"
      f="$STAGE/backend-$(date -u +%Y%m%dT%H%M%SZ)-${sha:0:12}.tar"
      cat > "$f.part"
      # Refuse anything that is not a backend archive.
      tar -tf "$f.part" backend/requirements.txt >/dev/null 2>&1 || { rm -f "$f.part"; echo "not a backend archive" >&2; exit 2; }
      mv "$f.part" "$f"
      echo "backend STAGED, not deployed: $(basename "$f"). Hamish's laptop agent reviews and applies it."
      ;;
    *)
      echo "usage: frontend | backend <sha>, with a tar on stdin" >&2
      exit 2
      ;;
  esac
else
  # Admin key only (a forced-command key always has SSH_ORIGINAL_COMMAND set).
  case "${1:-}" in
    status)
      ls -1t "$STAGE"/backend-*.tar 2>/dev/null || echo "nothing staged"
      ;;
    apply)
      f=${2:-$(ls -1t "$STAGE"/backend-*.tar 2>/dev/null | head -1)}
      [ -n "$f" ] && [ -f "$f" ] || { echo "nothing staged" >&2; exit 1; }
      apply_backend "$f"
      # Older staged snapshots are superseded: each one is the whole backend at its commit.
      for old in "$STAGE"/backend-*.tar; do [ -e "$old" ] && mv "$old" "$STAGE/applied/"; done
      ;;
    *)
      echo "usage: dvm-deploy status | apply [file]" >&2
      exit 2
      ;;
  esac
fi
