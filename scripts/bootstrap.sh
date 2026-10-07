#!/usr/bin/env bash
# Instalează VPS-ul de la zero (Ubuntu 24.04, ca root). Idempotent: poate fi rerulat.
#   curl -fsSL https://raw.githubusercontent.com/cristinbernic-stack/Aide/main/scripts/bootstrap.sh | bash
set -euo pipefail

REPO_URL="https://github.com/cristinbernic-stack/Aide.git"
APP_DIR="/opt/aide"

echo "==> Pachete de bază + actualizări automate"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q ca-certificates curl git ufw unattended-upgrades fail2ban
dpkg-reconfigure -f noninteractive unattended-upgrades

echo "==> Docker"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker

echo "==> Tailscale (acces privat la UI-uri)"
if ! command -v tailscale >/dev/null; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi

echo "==> Firewall: public doar SSH; restul prin Tailscale"
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow in on tailscale0
ufw --force enable
systemctl enable --now fail2ban

echo "==> Cod"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull --ff-only
else
  git clone "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"
mkdir -p data/postgres data/open-webui data/openhands data/runner data/uptime-kuma
chown -R 1000:1000 data/runner data/openhands

if [ ! -f .env ]; then
  cp .env.example .env
  sed -i "s/^LITELLM_MASTER_KEY=.*/LITELLM_MASTER_KEY=sk-$(openssl rand -hex 24)/" .env
  sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 16)/" .env
  sed -i "s/^WEBUI_SECRET_KEY=.*/WEBUI_SECRET_KEY=$(openssl rand -hex 24)/" .env
  echo "    .env creat cu chei generate; completează RUNPOD_*, GITHUB_TOKEN, TARGET_REPO, TELEGRAM_*."
fi

echo "==> Backup zilnic al datelor (fără greutăți de model; codul e oricum în GitHub)"
cat > /etc/cron.daily/aide-backup <<'EOF'
#!/bin/sh
mkdir -p /var/backups/aide
tar czf /var/backups/aide/data-$(date +%F).tgz -C /opt/aide data/open-webui data/openhands data/uptime-kuma .env
docker exec -t $(docker ps -qf name=aide-postgres) pg_dumpall -U aide | gzip > /var/backups/aide/pg-$(date +%F).sql.gz || true
find /var/backups/aide -mtime +14 -delete
EOF
chmod +x /etc/cron.daily/aide-backup

cat <<EOF

==> Gata. Pașii rămași (o singură dată):
  1. tailscale up            # deschide link-ul, aprobă din contul Tailscale
  2. echo "BIND_IP=\$(tailscale ip -4)" >> $APP_DIR/.env
  3. nano $APP_DIR/.env       # RUNPOD_API_KEY, RUNPOD_ENDPOINT_ID, GITHUB_TOKEN, TARGET_REPO, TELEGRAM_*
  4. cd $APP_DIR && docker compose up -d --build
  5. bash scripts/test-endpoint.sh

UI-uri (doar din Tailscale):  Open WebUI :3000  OpenHands :3001  Uptime Kuma :3002  LiteLLM :4000/ui
EOF
