#!/bin/bash
# One-time server setup (Ubuntu 24.04, as root). Usage: setup.sh <hostname>
# Afterwards, by hand: put coast.pmtiles in /opt/dvm/tiles/, install deploy.sh as /usr/local/sbin/dvm-deploy,
# and add the CI key to /root/.ssh/authorized_keys with command="/usr/local/sbin/dvm-deploy",restrict.
set -euo pipefail
HOST="$1"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q python3-venv python3-pip caddy ufw
id dvm >/dev/null 2>&1 || useradd --system --home /opt/dvm --shell /usr/sbin/nologin dvm
mkdir -p /opt/dvm
chown -R dvm:dvm /opt/dvm
chmod 600 /opt/dvm/.env
sudo -u dvm python3 -m venv /opt/dvm/backend/.venv
sudo -u dvm /opt/dvm/backend/.venv/bin/pip install -q -r /opt/dvm/backend/requirements.txt

cat > /etc/systemd/system/dvm.service <<UNIT
[Unit]
Description=Dark Vessel Monitor backend
After=network-online.target
Wants=network-online.target

[Service]
User=dvm
WorkingDirectory=/opt/dvm/backend
ExecStart=/opt/dvm/backend/.venv/bin/python -m dvm
Restart=on-failure
RestartSec=60
# Ctrl+C equivalent: the AISStream rules say never force-kill.
KillSignal=SIGINT
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
UNIT

cat > /etc/caddy/Caddyfile <<CADDY
$HOST {
	handle_path /api/* {
		reverse_proxy 127.0.0.1:8000
	}
	handle {
		root * /opt/dvm/frontend/dist
		# no compression on .pmtiles: the map reads them with byte ranges
		@text not path *.pmtiles
		encode @text zstd gzip
		try_files {path} /index.html
		file_server
	}
}
CADDY

ufw allow OpenSSH >/dev/null; ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null; ufw --force enable >/dev/null
systemctl daemon-reload
systemctl enable --now dvm
systemctl restart caddy
echo SETUP-DONE
