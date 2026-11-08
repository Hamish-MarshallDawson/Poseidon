#!/bin/bash
# Deploy entry point on the Vultr server, installed root-owned at /usr/local/sbin/dvm-deploy (not under /opt/dvm, which the dvm user owns).
# It is the forced command of the GitHub Actions deploy key in /root/.ssh/authorized_keys:
#   command="/usr/local/sbin/dvm-deploy",restrict ssh-ed25519 AAAA... github-actions-deploy
# so that key can run nothing else. CI sends a tar on stdin:
#   tar -C frontend/dist -cf - . | ssh root@<server> frontend
#   git archive HEAD backend     | ssh root@<server> backend
# CI cannot change this script; copy it to the server by hand when it changes.
set -euo pipefail

case "${SSH_ORIGINAL_COMMAND:-}" in
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
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' EXIT
    chmod 755 "$tmp"   # pip runs as dvm and must read requirements.txt
    tar -x -C "$tmp"
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
        echo "backend deployed and healthy"
        # The delayed-source jobs (poll and backfill) run this same code: restart the running ones so they pick it
        # up. SIGINT stop, and each resumes from the source_windows ledger, so nothing is lost or refetched.
        systemctl try-restart 'dvm-poll-*' 'dvm-backfill-*' && echo "source jobs restarted"
        exit 0
      fi
      sleep 2
    done
    echo "backend did not answer /health within 60 s" >&2
    journalctl -u dvm -n 40 --no-pager >&2
    exit 1
    ;;
  *)
    echo "usage: frontend | backend, with a tar on stdin" >&2
    exit 2
    ;;
esac
