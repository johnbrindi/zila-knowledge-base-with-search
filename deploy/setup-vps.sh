#!/usr/bin/env bash
# One-time root setup for the shared VPS: Docker Engine + the ai.zigexconnect.com nginx site.
# Safe to re-run. Touches no other nginx site and no PM2 app.
# Run: sudo bash ~/apps/ZILA-AI/deploy/setup-vps.sh
set -euo pipefail
APP_USER=${SUDO_USER:-sawaflix}
DOMAIN=ai.zigexconnect.com
HERE=$(cd "$(dirname "$0")" && pwd)

echo "== 1. Docker Engine (official apt repository)"
if ! command -v docker >/dev/null; then
  apt-get update -q
  apt-get install -y -q ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -q
  apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker
usermod -aG docker "$APP_USER"
docker --version && docker compose version

echo "== 2. nginx site for $DOMAIN"
SITE=/etc/nginx/sites-available/$DOMAIN
if [ ! -e "$SITE" ]; then
  cp "$HERE/nginx-$DOMAIN.conf" "$SITE"
  ln -sf "$SITE" "/etc/nginx/sites-enabled/$DOMAIN"
fi
if ! nginx -t; then
  echo "nginx config test failed: removing the new site, nginx left untouched"
  rm -f "/etc/nginx/sites-enabled/$DOMAIN" "$SITE"
  exit 1
fi
systemctl reload nginx

echo "== 3. TLS certificate (certbot, same as the other sites)"
if [ ! -d "/etc/letsencrypt/live/$DOMAIN" ]; then
  certbot --nginx -d "$DOMAIN" --non-interactive --redirect
fi
nginx -t && systemctl reload nginx
echo "Done. Now, as $APP_USER in a NEW ssh session: cd ~/apps/ZILA-AI && docker compose up -d --build"
