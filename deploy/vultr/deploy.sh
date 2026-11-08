#!/bin/bash
# Deploy entry point on the Vultr server, installed root-owned at /usr/local/sbin/dvm-deploy (not under /opt/dvm, which
# the dvm user owns). CI cannot change this script; copy it to the server by hand when it changes (strip CRs).
#
# Two ways in:
#  1. CI (the GitHub Actions key). This script is that key's forced command in /root/.ssh/authorized_keys:
#       command="/usr/local/sbin/dvm-deploy",restrict ssh-ed25519 AAAA... github-actions-deploy
#     so the key can run nothing else. CI sends a tar on stdin:
#       tar -C frontend/dist -cf - . | ssh root@<server> "frontend <sha>"  deploys at once, or stages while held
#       git archive HEAD backend     | ssh root@<server> "backend <sha>"   only ever STAGES the backend
#  2. A supervisor with the admin key (Hamish's laptop agent; the key lives only on that laptop):
#       dvm-deploy status            what is staged, held or deployed
#       dvm-deploy apply             deploys the newest staged backend
#       dvm-deploy release           deploys the newest staged frontend
#       dvm-deploy hold on|off       hold frontend deploys for one combined release (Hamish, 8 Nov 04:50)
#     Hamish's rule (8 Nov 03:36): no agent deploys the backend without that supervision.
set -euo pipefail
STAGE=/opt/dvm-staged   # root-only; the dvm user cannot write here
TMPD=""
trap 'rm -rf "${TMPD:-}"' EXIT

stage() {   # $1 = kind (backend|frontend), $2 = sha, $3 = file that must be in the archive; tar on stdin
  local sha=$2 f
  [[ "$sha" =~ ^[0-9a-f]{7,40}$ ]] || sha=unknown
  install -d -m 700 "$STAGE"
  f="$STAGE/$1-$(date -u +%Y%m%dT%H%M%SZ)-${sha:0:12}.tar"
  cat > "$f.part"
  tar -tf "$f.part" "$3" >/dev/null 2>&1 || { rm -f "$f.part"; echo "not a $1 archive" >&2; exit 2; }
  mv "$f.part" "$f"
  echo "$1 STAGED, not deployed: $(basename "$f"). Hamish's laptop agent reviews and releases it."
}

deploy_frontend() {   # tar of frontend/dist on stdin
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
}

apply_backend() {   # $1 = staged tar
  TMPD=$(mktemp -d)
  chmod 755 "$TMPD"   # pip runs as dvm and must read requirements.txt
  tar -x -C "$TMPD" -f "$1"
  test -f "$TMPD/backend/requirements.txt"
  sudo -u dvm /opt/dvm/backend/.venv/bin/pip install -q -r "$TMPD/backend/requirements.txt"
  # Ctrl+C equivalent (KillSignal=SIGINT): the AISStream rules forbid a force-kill.
  systemctl stop dvm
  # .venv and data/ are not in git, so they survive; everything tracked is replaced.
  rm -rf /opt/dvm/backend/dvm /opt/dvm/backend/tests
  cp -r "$TMPD/backend/." /opt/dvm/backend/
  chown -R dvm:dvm /opt/dvm/backend
  systemctl start dvm
  for _ in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
      echo "backend deployed and healthy: $(basename "$1")"
      # The delayed-source jobs (poll and backfill) run this same code: restart the running ones so they pick it
      # up. SIGINT stop, and each resumes from the source_windows ledger, so nothing is lost or refetched.
      systemctl try-restart 'dvm-poll-*' 'dvm-backfill-*' && echo "source jobs restarted"
      basename "$1" > "$STAGE/DEPLOYED_BACKEND"
      return 0
    fi
    sleep 2
  done
  echo "backend did not answer /health within 60 s" >&2
  journalctl -u dvm -n 40 --no-pager >&2
  return 1
}

newest() { ls -1t "$STAGE"/"$1"-*.tar 2>/dev/null | head -1; }
retire() { mkdir -p "$STAGE/applied"; for old in "$STAGE"/"$1"-*.tar; do [ -e "$old" ] && mv "$old" "$STAGE/applied/"; done; return 0; }

if [ -n "${SSH_ORIGINAL_COMMAND:-}" ]; then
  # CI key: the requested command arrives here, never as arguments.
  read -r cmd arg _ <<< "$SSH_ORIGINAL_COMMAND"   # no word-splitting or globbing of CI input
  case "$cmd" in
    frontend)
      if [ -e "$STAGE/HOLD_FRONTEND" ]; then stage frontend "${arg:-}" ./index.html; else deploy_frontend; fi
      ;;
    backend)
      stage backend "${arg:-}" backend/requirements.txt
      ;;
    *)
      echo "usage: frontend <sha> | backend <sha>, with a tar on stdin" >&2
      exit 2
      ;;
  esac
else
  # Admin key only (a forced-command key always has SSH_ORIGINAL_COMMAND set).
  case "${1:-}" in
    status)
      echo "frontend hold: $([ -e "$STAGE/HOLD_FRONTEND" ] && echo ON || echo off)"
      echo "deployed backend: $(cat "$STAGE/DEPLOYED_BACKEND" 2>/dev/null || echo unknown)"
      ls -1t "$STAGE"/*.tar 2>/dev/null || echo "nothing staged"
      ;;
    apply)
      f=${2:-$(newest backend)}
      [ -n "$f" ] && [ -f "$f" ] || { echo "no staged backend" >&2; exit 1; }
      apply_backend "$f"
      retire backend   # older snapshots are superseded: each one is the whole backend at its commit
      ;;
    release)
      f=${2:-$(newest frontend)}
      [ -n "$f" ] && [ -f "$f" ] || { echo "no staged frontend" >&2; exit 1; }
      deploy_frontend < "$f"
      retire frontend
      ;;
    hold)
      install -d -m 700 "$STAGE"
      case "${2:-}" in
        on) touch "$STAGE/HOLD_FRONTEND"; echo "frontend hold ON: merges stage until 'dvm-deploy release'" ;;
        off) rm -f "$STAGE/HOLD_FRONTEND"; echo "frontend hold off: merges deploy at once" ;;
        *) echo "usage: dvm-deploy hold on|off" >&2; exit 2 ;;
      esac
      ;;
    *)
      echo "usage: dvm-deploy status | apply [file] | release [file] | hold on|off" >&2
      exit 2
      ;;
  esac
fi
