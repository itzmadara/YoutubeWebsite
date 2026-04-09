#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/opt/clipforge/app"
VENV_ROOT="/opt/clipforge/venv"

echo "Installing system packages..."
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip ffmpeg curl ca-certificates gnupg nginx

if ! command -v node >/dev/null 2>&1; then
  echo "Installing Node.js 22..."
  sudo mkdir -p /etc/apt/keyrings
  curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
    | sudo gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
  echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" \
    | sudo tee /etc/apt/sources.list.d/nodesource.list >/dev/null
  sudo apt-get update
  sudo apt-get install -y nodejs
fi

if ! id clipforge >/dev/null 2>&1; then
  echo "Creating clipforge user..."
  sudo useradd --system --create-home --shell /bin/bash clipforge
fi

echo "Preparing directories..."
sudo mkdir -p /opt/clipforge /opt/clipforge/secrets
sudo chown -R "$USER":www-data /opt/clipforge

if [ ! -d "$VENV_ROOT" ]; then
  python3 -m venv "$VENV_ROOT"
fi

echo "Installing Python dependencies..."
"$VENV_ROOT/bin/pip" install --upgrade pip
"$VENV_ROOT/bin/pip" install -r "$APP_ROOT/requirements.txt"

echo "Copy deploy/clipforge.env.example to deploy/clipforge.env and edit it before starting the service."
echo "Copy deploy/clipforge.service to /etc/systemd/system/clipforge.service"
echo "Copy deploy/nginx-clipforge.conf to /etc/nginx/sites-available/clipforge"
