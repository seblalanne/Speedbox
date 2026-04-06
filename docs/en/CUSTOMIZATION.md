# SpeedBox Customization Guide

This guide explains how to modify and extend SpeedBox for your specific needs.

---

## 1. Adding a Language

SpeedBox ships with French (fr) and English (en). Adding a third language requires changes to one file only: `static/js/i18n.js`.

### Step 1: Add the translation dictionary

In `static/js/i18n.js`, the `TRANSLATIONS` object contains `fr` and `en` sub-objects. Add a new sub-object for your language. For example, to add German:

```javascript
var TRANSLATIONS = {
  fr: {
    'nav.home': 'Accueil',
    // ... existing French translations
  },
  en: {
    'nav.home': 'Home',
    // ... existing English translations
  },
  de: {
    'nav.home': 'Startseite',
    'nav.speedtest': 'Geschwindigkeitstest',
    'nav.network': 'Netzwerk',
    'nav.diagnostic': 'Diagnose',
    'nav.history': 'Verlauf',
    // ... translate all ~250 keys
  }
};
```

You must provide all keys. Any missing key will fall back to French (the fallback language in the `t()` function).

### Step 2: Update the language toggle

The current `toggleLang()` function only toggles between two languages:

```javascript
function toggleLang() {
  setLang(getLang() === 'fr' ? 'en' : 'fr');
}
```

Replace it with a cycle through all available languages:

```javascript
function toggleLang() {
  var langs = ['fr', 'en', 'de'];
  var current = getLang();
  var idx = langs.indexOf(current);
  var next = langs[(idx + 1) % langs.length];
  setLang(next);
}
```

### Step 3: Update the toggle button label

In `applyTranslations()`, the button label currently shows the "other" language. For a multi-language toggle, show the current language code or the next language:

```javascript
// In applyTranslations(), replace the label logic:
var lang = getLang();
var label = lang.toUpperCase();  // Shows current language: "FR", "EN", "DE"
```

### Step 4: Update getLocale()

Add the locale mapping for date/number formatting:

```javascript
function getLocale() {
  var locales = { fr: 'fr-FR', en: 'en-GB', de: 'de-DE' };
  return locales[getLang()] || 'en-GB';
}
```

### Step 5: Update base.html default language

In `templates/base.html`, the `<html lang="fr">` attribute sets the initial language. This is overridden by `applyTranslations()` on page load, so it only affects the brief moment before JavaScript executes. You can leave it as `fr` or change it to your preferred default.

---

## 2. Changing the Theme

SpeedBox uses a dark theme defined in `static/css/style.css`. Here are the key colors and how to change them.

### Key Color Variables

| Color | Usage | CSS locations |
|---|---|---|
| `#0a0e17` | Page background (body) | `body { background: #0a0e17; }` |
| `#131a2b` | Card/navbar background | `.navbar`, `.card`, `.section-collapse`, multiple components |
| `#00d4ff` | Primary accent (cyan) | Brand text, borders, buttons, links, active states |
| `#e0e0e0` | Primary text color | `body { color: #e0e0e0; }` |
| `#8899aa` | Secondary text / inactive links | `.nav-link { color: #8899aa; }` |
| `#1a2540` | Hover/active background | `.nav-link:hover`, `.nav-link.active` |
| `#1e3a5f` | Border color for buttons | `.lang-btn { border: 1px solid #1e3a5f; }` |

### Creating a Light Theme

To convert to a light theme, replace the core colors:

```css
/* Light theme overrides */
body {
    background: #f5f7fa;
    color: #1a1a2e;
}

.navbar, .bottom-bar {
    background: #ffffff;
    border-color: #0077b6;
}

.nav-brand {
    color: #0077b6;
}

.card, .section-collapse {
    background: #ffffff;
    border: 1px solid #e0e0e0;
}

.nav-link {
    color: #666;
}

.nav-link:hover, .nav-link.active {
    color: #1a1a2e;
    background: #f0f0f5;
}
```

You will also need to adjust Chart.js colors in the template JavaScript (axis labels, grid lines, etc.) and the brand logo filter in `.brand-logo`.

### Accent Color Change

To change the accent from cyan (`#00d4ff`) to another color, perform a global find-and-replace in `style.css`. Also update:

- `templates/base.html`: the footer link color (`style="color:#00d4ff"`)
- Any `rgba(0,212,255,...)` references (these are the same cyan color with opacity)

---

## 3. Adding a Diagnostic Tool

This section walks through adding a new network diagnostic tool (for example, a "Whois" lookup) by following the patterns established by the existing Ping, MTR, and DNS tools.

### Backend Pattern (app.py)

#### A. Add a WebSocket handler

```python
@socketio.on('run_whois')
def handle_whois(data):
    host = validate_target(data.get('host', ''))
    if not host:
        emit('diag_error', {'message_key': 'srv.invalid_target'})
        return

    try:
        process = subprocess.Popen(
            ['whois', host],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True
        )
        diag_processes[request.sid] = process
        stdout, _ = process.communicate(timeout=30)
        emit('whois_result', {'output': stdout})
    except subprocess.TimeoutExpired:
        process.kill()
        emit('diag_error', {'message_key': 'srv.timeout'})
    except Exception as e:
        emit('diag_error', {'message': str(e)})
    finally:
        proc = diag_processes.pop(request.sid, None)
        if proc and proc.poll() is None:
            proc.kill()
```

Key points:
1. **Validate input** with `validate_target()` before passing to subprocess.
2. **Track the process** in `diag_processes[request.sid]` so the Stop button works.
3. **Use list arguments** for subprocess (never `shell=True`).
4. **Clean up** in a `finally` block: pop from dictionary, kill if still running.
5. **Emit results** as a named event that the frontend listens for.

#### B. Install the system package

```bash
sudo apt install -y whois
```

### Frontend Pattern (templates/diagnostic.html)

#### A. Add a collapsible section

```html
<div class="section-collapse">
    <div class="section-header" onclick="toggleSection(this)">
        <h2 data-i18n="diag.whois">Whois</h2>
        <span class="collapse-icon">+</span>
    </div>
    <div class="section-body">
        <div class="form-group">
            <label data-i18n="diag.target">Target</label>
            <input type="text" id="whois-host" placeholder="example.com">
        </div>
        <button onclick="runWhois()" data-i18n="diag.launch">Start</button>
        <pre id="whois-output" class="terminal-output" data-i18n="diag.waiting">Waiting...</pre>
    </div>
</div>
```

#### B. Add JavaScript handler

```javascript
function runWhois() {
    var host = document.getElementById('whois-host').value.trim();
    if (!host) return;
    document.getElementById('whois-output').textContent = t('diag.whois_running', {host: host});
    socket.emit('run_whois', {host: host});
}

socket.on('whois_result', function(data) {
    document.getElementById('whois-output').textContent = data.output;
});
```

### i18n Keys

Add translation keys to both the `fr` and `en` sections of `static/js/i18n.js`:

```javascript
// In fr:
'diag.whois': 'Whois',
'diag.whois_running': 'Recherche Whois pour {host}...',

// In en:
'diag.whois': 'Whois',
'diag.whois_running': 'Whois lookup for {host}...',
```

### Optional: Save Results

To save whois results to history, add a `save_result()` call in the backend:

```python
save_result('whois', {'target': host, 'output': stdout})
```

Then add a Whois tab in `templates/history.html` following the Ping tab pattern.

---

## 4. Changing the Default Network Interface

SpeedBox defaults to `eth0` as the primary network interface. If your system uses a different interface name (e.g., `enp0s3`, `end0`), you need to update several locations.

### Locations where eth0 is referenced

**app.py:**
- `get_current_ip('eth0')` -- called in `api_status()` (line 325)
- `get_interface_status('eth0')` -- called in `api_status()` (line 331)
- `get_link_speed('eth0')` -- called in `api_status()` (line 335)
- `get_mac_address('eth0')` -- called in `api_status()` (line 332)
- `parse_eth0_config()` -- regex matches `iface eth0 inet` (line 368)
- `write_eth0_config()` -- writes `allow-hotplug eth0` and `iface eth0 inet` (lines 398-409)
- `api_network_apply()` -- uses `'eth0'` as default interface (line 423)

**templates/index.html:**
- Status card labels reference "Ethernet Port" / "Port Ethernet" (via i18n keys, not hardcoded)

**static/js/i18n.js:**
- Display labels use generic terms ("Ethernet Port") rather than interface names

### How to change

The simplest approach is to define a constant at the top of `app.py` and use it everywhere:

```python
PRIMARY_INTERFACE = 'end0'  # Change this to your interface name
```

Then replace all hardcoded `'eth0'` references in `api_status()`, `parse_eth0_config()`, `write_eth0_config()`, and `api_network_apply()` with `PRIMARY_INTERFACE`.

For `parse_eth0_config()` and `write_eth0_config()`, also update the regex patterns to use the new interface name instead of the literal string `eth0`.

---

## 5. Disabling Features

### Disable FTP/SFTP

To remove the FTP/SFTP upload feature:

1. **app.py:** Remove or comment out the routes `/api/ftp/config`, `/api/ftp/test`, `/api/ftp/send` (lines 918-1073).
2. **templates/network.html:** Remove the FTP/SFTP section from the template.
3. **static/js/i18n.js:** Optionally remove all `net.ftp_*` translation keys.
4. **requirements.txt:** Remove `paramiko==4.0.0` if you do not need SFTP support at all.

### Disable Network Configuration

To prevent users from changing IP settings, VLANs, or rebooting:

1. **app.py:** Remove or comment out:
   - `/api/network/apply` (line 419)
   - `/api/network/vlan` (line 473)
   - `/api/network/vlan/delete` (line 509)
   - `/api/reboot` (line 310)
2. **templates/network.html:** Remove the IP configuration form, VLAN section, and reboot buttons.
3. **templates/index.html:** Remove the Maintenance section with reboot buttons.

### Disable QuickTest

1. **app.py:** Remove or comment out the `start_quicktest` and `stop_quicktest` WebSocket handlers (lines 1080-1382).
2. **templates/speedtest.html:** Remove the QuickTest modal HTML and related JavaScript.
3. **templates/index.html:** Remove the QuickTest hero card.

### Disable Reboot

1. **app.py:** Remove or comment out the `/api/reboot` route (lines 310-321).
2. **templates/index.html:** Remove both reboot buttons from the Maintenance section.

---

## 6. Running Without Root

By default, SpeedBox runs as root because several operations require elevated privileges. Here is how to run as a non-root user with selective sudo.

### Operations That Require Root

| Operation | Command | Why |
|---|---|---|
| Set IP address | `ip addr add/flush` | Modifying network interfaces requires CAP_NET_ADMIN |
| Set routes | `ip route add/del` | Modifying routing table requires CAP_NET_ADMIN |
| Create VLANs | `ip link add` | Creating network interfaces requires CAP_NET_ADMIN |
| Read link speed | `ethtool` | Accessing NIC registers requires root |
| Reboot system | `sudo reboot` | System control requires root |
| Restart service | `sudo systemctl restart` | Service management requires root |
| Write /etc/network/interfaces | Direct file write | File is owned by root |
| Write /etc/resolv.conf | Direct file write | File is owned by root |

### Step 1: Create a dedicated user

```bash
sudo useradd -r -s /bin/false -d /opt/speedbox speedbox
sudo chown -R speedbox:speedbox /opt/speedbox
sudo chown -R speedbox:speedbox /opt/speedbox/config
sudo chown -R speedbox:speedbox /opt/speedbox/results
```

### Step 2: Configure sudoers

Create a sudoers file that allows the speedbox user to run specific commands without a password:

```bash
sudo visudo -f /etc/sudoers.d/speedbox
```

```
speedbox ALL=(root) NOPASSWD: /usr/sbin/ip
speedbox ALL=(root) NOPASSWD: /usr/sbin/ethtool
speedbox ALL=(root) NOPASSWD: /sbin/reboot
speedbox ALL=(root) NOPASSWD: /usr/bin/systemctl restart speedbox
speedbox ALL=(root) NOPASSWD: /usr/sbin/ifup
speedbox ALL=(root) NOPASSWD: /usr/sbin/ifdown
```

### Step 3: Modify app.py subprocess calls

Prefix all privileged commands with `sudo`. For example:

```python
# Before:
subprocess.run(['ip', 'addr', 'flush', 'dev', interface], ...)

# After:
subprocess.run(['sudo', 'ip', 'addr', 'flush', 'dev', interface], ...)
```

Commands that need the `sudo` prefix:
- All `ip` commands (addr, link, route)
- `ethtool`
- `ifup` / `ifdown`

For writing `/etc/network/interfaces` and `/etc/resolv.conf`, you would need to either:
- Use `sudo tee` via subprocess instead of direct `open()`
- Or grant write permission on those specific files to the speedbox group

### Step 4: Update the service file

```ini
[Service]
Type=simple
User=speedbox
Group=speedbox
WorkingDirectory=/opt/speedbox
ExecStart=/opt/speedbox/venv/bin/python app.py
```

### Step 5: Handle non-root tools

The following tools work without root and need no changes:
- `iperf3`
- `mtr` (uses raw sockets via setuid bit, typically already set)
- `ping` (uses setuid or CAP_NET_RAW, typically already set)
- `traceroute` (may need `sudo` depending on your system)
- `nslookup`

Check if mtr and ping have the correct capabilities:

```bash
ls -la /usr/bin/mtr-packet
# Should show setuid bit: -rwsr-xr-x
getcap /usr/bin/ping
# Should show: cap_net_raw=ep
```

### Trade-offs

Running without root improves security isolation but adds complexity. For a dedicated test appliance on an isolated network (the typical SpeedBox deployment), running as root is an acceptable trade-off. The non-root approach is recommended if SpeedBox is exposed to untrusted users or accessible from the internet.
