# SpeedBox Installation Guide

## 1. Prerequisites

### Hardware

- Raspberry Pi 5 (recommended) or Raspberry Pi 4
- MicroSD card (16 GB minimum)
- Ethernet connection (required for network testing)
- Power supply appropriate for your Pi model

### Software

- DietPi or Raspberry Pi OS (Debian 12 Bookworm or newer)
- Python 3.11 or newer (Python 3.13 recommended)
- Root access (required for network configuration commands)

## 2. Install System Packages

SpeedBox depends on several system-level network tools. Install them with apt:

```bash
sudo apt update
sudo apt install -y iperf3 mtr traceroute ethtool dnsutils
```

**Package purposes:**
- `iperf3` -- bandwidth/throughput testing
- `mtr` -- advanced traceroute with statistics (My TraceRoute)
- `traceroute` -- basic route tracing
- `ethtool` -- Ethernet link speed detection
- `dnsutils` -- provides `nslookup` for DNS lookups

Verify each tool is available:

```bash
iperf3 --version
mtr --version
traceroute --version
ethtool --version
nslookup -version
```

## 3. Clone the Repository

```bash
cd /opt
sudo git clone https://github.com/OWNER/speedbox.git
sudo chown -R root:root /opt/speedbox
cd /opt/speedbox
```

If you do not have git installed:

```bash
sudo apt install -y git
```

## 4. Set Up Python Virtual Environment

Create an isolated Python environment and install dependencies:

```bash
cd /opt/speedbox
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

This installs:
- Flask 3.1.3
- Flask-SocketIO 5.6.1
- gevent 25.9.1
- paramiko 4.0.0
- requests 2.33.1

## 5. Initial Configuration

Create the required directories:

```bash
mkdir -p /opt/speedbox/config
mkdir -p /opt/speedbox/results
```

These directories will be populated automatically at runtime:
- `config/.secret_key` -- auto-generated Flask secret key
- `config/ftp_config.json` -- created when user saves FTP settings
- `config/public_servers.json` -- created when user fetches public server list
- `results/*.json` -- created as tests are run

## 6. Set Up the systemd Service

Copy the provided service file and enable it:

```bash
sudo cp /opt/speedbox/speedbox.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable speedbox
sudo systemctl start speedbox
```

The service file (`speedbox.service`) configures:
- Runs as root (required for ip, ethtool, reboot commands)
- Starts after network.target
- Automatically restarts on failure (3-second delay)
- Working directory: `/opt/speedbox`
- Executable: `/opt/speedbox/venv/bin/python app.py`

## 7. Verification

### Check service status

```bash
sudo systemctl status speedbox
```

Expected output should show `active (running)`.

### Check the application log

```bash
sudo journalctl -u speedbox -f
```

You should see:

```
==================================================
  SpeedBOX - http://0.0.0.0:5000
==================================================
```

### Test HTTP access

From the Raspberry Pi itself:

```bash
curl http://localhost:5000/api/status
```

This should return a JSON response with eth0/wlan0 status information.

### Browser access

Open a web browser and navigate to:

```
http://<raspberry-pi-ip>:5000
```

Replace `<raspberry-pi-ip>` with the actual IP address of your Pi. You should see the SpeedBox dashboard with system status cards.

## 8. Optional Configuration

### Reverse Proxy (nginx)

To run SpeedBox behind nginx (for example, to serve on port 80 or with SSL):

```bash
sudo apt install -y nginx
```

Create the nginx configuration:

```bash
sudo nano /etc/nginx/sites-available/speedbox
```

```nginx
server {
    listen 80;
    server_name speedbox.local;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
}
```

The `proxy_set_header Upgrade` and `Connection "upgrade"` lines are essential for WebSocket support. The `proxy_read_timeout 86400` prevents nginx from closing long-running WebSocket connections.

Enable and start:

```bash
sudo ln -s /etc/nginx/sites-available/speedbox /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

### SSL with Let's Encrypt

If your Pi is publicly accessible:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d speedbox.yourdomain.com
```

### Firewall (ufw)

```bash
sudo apt install -y ufw
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS (if using SSL)
sudo ufw allow 5000/tcp  # SpeedBox direct (optional, skip if using reverse proxy)
sudo ufw enable
```

## 9. Update Procedure

To update SpeedBox to the latest version:

```bash
cd /opt/speedbox

# Pull latest changes
sudo git pull origin main

# Update Python dependencies
source venv/bin/activate
pip install -r requirements.txt

# Restart the service
sudo systemctl restart speedbox
```

Check for any issues after update:

```bash
sudo systemctl status speedbox
sudo journalctl -u speedbox --since "5 minutes ago"
```

Note: Updates will never overwrite your `config/` or `results/` directories (they are excluded in `.gitignore`).

## 10. Uninstall Procedure

To completely remove SpeedBox:

```bash
# Stop and disable the service
sudo systemctl stop speedbox
sudo systemctl disable speedbox
sudo rm /etc/systemd/system/speedbox.service
sudo systemctl daemon-reload

# Remove application files
sudo rm -rf /opt/speedbox

# Remove nginx config (if applicable)
sudo rm /etc/nginx/sites-enabled/speedbox
sudo rm /etc/nginx/sites-available/speedbox
sudo systemctl restart nginx
```

Optionally remove system packages that were installed only for SpeedBox:

```bash
sudo apt remove --purge iperf3 mtr traceroute ethtool dnsutils
```

## Troubleshooting

### Service fails to start

Check the journal for errors:

```bash
sudo journalctl -u speedbox -n 50
```

Common causes:
- Python venv not created or dependencies not installed
- Port 5000 already in use by another application
- Missing system packages (iperf3, mtr, etc.)

### Cannot access from browser

- Verify the service is running: `sudo systemctl status speedbox`
- Check if the port is open: `ss -tlnp | grep 5000`
- Ensure no firewall is blocking port 5000
- Try accessing from the Pi itself: `curl http://localhost:5000`

### iperf3 tests fail

- Verify iperf3 is installed: `iperf3 --version`
- Test connectivity to the iperf3 server manually: `iperf3 -c <server> -p <port> -t 5`
- Check if the server is busy (iperf3 public servers only accept one connection at a time)

### Network configuration changes cause loss of access

If you change the IP address via the Network page and lose access:
- Connect to the Pi via console (HDMI + keyboard) or serial
- The previous configuration is backed up at `/etc/network/interfaces.bak`
- Restore it: `sudo cp /etc/network/interfaces.bak /etc/network/interfaces && sudo reboot`

### WebSocket connection fails

- If behind a reverse proxy, ensure the `Upgrade` and `Connection` headers are forwarded
- Check browser console (F12) for WebSocket errors
- Verify that `cors_allowed_origins='*'` in app.py is not being restricted by proxy settings
