#!/bin/bash
set -euo pipefail
# Quick verify post-deploy

echo "=== Post-deploy verification ==="

# 1. Service running?
echo "[1] Service status:"
sudo systemctl status kanban.service --no-pager || true

# 2. Port listening?
echo "[2] Port check:"
sudo ss -tlnp | grep 9121 || sudo netstat -tlnp | grep 9121 || true

# 3. Health endpoint
echo "[3] Health check:"
curl -s http://localhost:9121/health || true

# 4. Firewall
echo "[4] Firewall rules:"
if command -v firewall-cmd >/dev/null 2>&1; then
  sudo firewall-cmd --list-ports || true
elif command -v ufw >/dev/null 2>&1; then
  sudo ufw status || true
fi

# 5. Public IP
echo "[5] Public IP:"
curl -s ifconfig.me || curl -s ipinfo.io/ip || true

echo ""
echo "=== Open this in phone browser ==="
echo "http://$(curl -s ifconfig.me):9121"
