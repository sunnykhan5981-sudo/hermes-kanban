# Hermes Kanban - Free Always-On Setup Guide

## Current working URL
- Local: `http://127.0.0.1:9121`
- Render: `https://hermes-kanban-1.onrender.com` (UI only, no backend data)

## Local test only (laptop must stay on)
```powershell
cd C:\Users\PROJECT-1\pl-kanban
python server.py
# then open http://127.0.0.1:9121
```

## Cloud / Always-on setup (Oracle Free Tier)

### Step 1: Create Oracle Cloud account
- Go to: https://www.oracle.com/cloud/free/
- Click "Start for free"
- Sign up with credit card (verify only, $0 charge unless you upgrade)
- Complete identity verification

### Step 2: Create VM instance
1. Open https://cloud.oracle.com/
2. Menu → Compute → Instances
3. Click "Create Instance"
4. Settings:
   - Name: `kanban-server`
   - Image: `Oracle Linux 8`
   - Shape: `VM.Standard.E2.1.Micro` (Always Free)
   - SSH key: Generate or upload your own
   - Boot volume: 30 GB
   - Networking: Default VCN, add SSH ingress rule for port 22
5. Click "Create"
6. Wait ~2 minutes, note the PUBLIC IP

### Step 3: SSH into VM
From your laptop PowerShell:
```powershell
ssh -i "C:\Users\PROJECT-1\.ssh\oracle_key.pem" opc@<PUBLIC_IP>
```

### Step 4: Run setup script
```bash
curl -fsSL https://raw.githubusercontent.com/sunnykhan5981-sudo/hermes-kanban/master/deploy/setup_vps.sh | bash
```

Or manually:
```bash
git clone https://github.com/sunnykhan5981-sudo/hermes-kanban.git
cd hermes-kanban
pip3 install --user -r requirements.txt
mkdir -p ~/.config/hermes ~/.local/share/hermes ~/.local/share/hermes/kanban ~/.cache/hermes
sudo cp deploy/kanban.service /etc/systemd/system/kanban.service
sudo systemctl daemon-reload
sudo systemctl enable kanban.service
sudo systemctl start kanban.service
sudo firewall-cmd --permanent --add-port=9121/tcp
sudo firewall-cmd --reload
```

### Step 5: Verify
```bash
sudo systemctl status kanban.service
curl http://localhost:9121/health
```

### Step 6: Open in phone
```
http://<PUBLIC_IP>:9121
```

## Important
- Do NOT use Render URL for task creation; it has no backend.
- The VPS setup gives you 24/7 access from any network.
- Laptop can be off; phone will still work.
- Database lives on the VPS at: `~/.local/share/hermes/kanban.db`

## Troubleshooting
- Service not starting: `sudo journalctl -u kanban.service -n 50`
- Port blocked: `sudo firewall-cmd --list-ports`
- Permission issues: ensure folder ownership `sudo chown -R opc:opc /home/opc/hermes-kanban /home/opc/.local/share/hermes`
