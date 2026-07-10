#!/bin/bash
set -euo pipefail

# Hermes Kanban - VPS Setup Script
# Use on: Oracle Linux / RHEL / Ubuntu
# Run AFTER ssh into server

echo "=== Hermes Kanban Server Setup ==="

# 1. Update system
if command -v dnf >/dev/null 2>&1; then
  echo "[1/6] Updating system (dnf)..."
  sudo dnf update -y
  echo "[2/6] Installing packages..."
  sudo dnf install -y git python3 python3-pip curl
elif command -v apt >/dev/null 2>&1; then
  echo "[1/6] Updating system (apt)..."
  sudo apt update && sudo apt upgrade -y
  echo "[2/6] Installing packages..."
  sudo apt install -y git python3 python3-pip curl
else
  echo "Unsupported package manager. Use dnf or apt."
  exit 1
fi

# 2. Clone repo
echo "[3/6] Cloning repo..."
if [ -d "$HOME/hermes-kanban" ]; then
  echo "Repo exists, pulling latest..."
  cd "$HOME/hermes-kanban"
  git pull origin master
else
  git clone https://github.com/sunnykhan5981-sudo/hermes-kanban.git "$HOME/hermes-kanban"
  cd "$HOME/hermes-kanban"
fi

# 3. Install Python deps
echo "[4/6] Installing Python dependencies..."
pip3 install --user --upgrade pip
pip3 install --user -r requirements.txt

# 4. Create Hermes data dirs
echo "[5/6] Creating Hermes directories..."
mkdir -p "$HOME/.config/hermes"
mkdir -p "$HOME/.local/share/hermes"
mkdir -p "$HOME/.local/share/hermes/kanban"
mkdir -p "$HOME/.cache/hermes"

# 5. Install systemd service
echo "[6/6] Installing systemd service..."
sudo cp "$HOME/hermes-kanban/deploy/kanban.service" /etc/systemd/system/kanban.service
sudo systemctl daemon-reload
sudo systemctl enable kanban.service
sudo systemctl start kanban.service

echo ""
echo "=== Setup Complete ==="
echo "Service status:"
sudo systemctl status kanban.service --no-pager
echo ""
echo "Test: curl http://localhost:9121/health"
echo "Public access: http://$(curl -s ifconfig.me):9121"
