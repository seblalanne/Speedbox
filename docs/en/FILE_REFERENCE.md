# SpeedBox File Reference

This document describes every file in the SpeedBox project, its purpose, and its key contents.

---

## app.py

**Lines:** ~1392
**Purpose:** Main Flask application. Contains all backend logic: HTTP routes, REST API endpoints, WebSocket handlers, utility functions, and process management.

### Imports and Initialization (lines 1-48)

- `gevent.monkey.patch_all()` -- must be called before any other import
- Flask app creation, SocketIO initialization with `async_mode='gevent'`
- Directory constants: `RESULTS_DIR`, `CONFIG_DIR`
- Secret key auto-generation and persistence
- Process tracking dictionaries: `iperf3_processes`, `diag_processes`, `quicktest_processes`, `quicktest_stop_flags`

### Utility Functions

| Function | Lines | Purpose |
|---|---|---|
| `validate_target(host)` | 50-54 | Validates hostname/IP against `^[a-zA-Z0-9.\-:]+$` regex |
| `parse_mtr_hubs(hubs_raw)` | 56-91 | Parses MTR JSON hubs into structured data with loss classification and spike detection |
| `parse_ping_summary(output)` | 93-106 | Extracts packet stats and RTT values from ping text output using regex |
| `get_current_ip(interface)` | 111-118 | Runs `ip -4 addr show` to get current IPv4 address |
| `get_interface_status(interface)` | 120-126 | Runs `ip link show` to check UP/DOWN state |
| `get_link_speed(interface)` | 128-135 | Runs `ethtool` to get negotiated link speed |
| `save_result(test_type, data, test_name)` | 137-149 | Saves test result as timestamped JSON file in results/ |
| `load_results()` | 151-163 | Loads up to 200 most recent JSON results, sorted reverse chronologically |
| `get_mac_address(interface)` | 191-198 | Extracts MAC address from `ip link show` output |
| `get_default_gateway()` | 200-207 | Extracts default gateway from `ip route show default` |
| `get_dns_servers()` | 209-215 | Reads nameserver entries from `/etc/resolv.conf` |
| `_clean_html(text)` | 219-221 | Strips HTML tags and normalizes whitespace |
| `parse_iperf_servers(html)` | 223-265 | Parses iperf.fr public server list HTML into structured JSON |
| `cidr_to_netmask(cidr)` | 350-353 | Converts CIDR prefix length to dotted netmask string |
| `netmask_to_cidr(netmask)` | 355-359 | Converts dotted netmask to CIDR prefix length |
| `parse_eth0_config()` | 361-389 | Parses `/etc/network/interfaces` to extract eth0 configuration |
| `write_eth0_config(mode, ip, mask, gateway, dns)` | 391-411 | Rewrites eth0 block in `/etc/network/interfaces`, creates .bak backup |
| `load_servers()` | 861-866 | Reads `servers.json` into a Python list |
| `save_servers(servers)` | 868-870 | Writes server list back to `servers.json` |

### Page Routes

| Route | Method | Function | Purpose |
|---|---|---|---|
| `/` | GET | `index()` | Dashboard / home page |
| `/speedtest` | GET | `speedtest()` | Speed test page |
| `/network` | GET | `network()` | Network configuration page |
| `/diagnostic` | GET | `diagnostic()` | Diagnostic tools page |
| `/history` | GET | `history()` | Test history page |

### REST API Endpoints

| Route | Method | Function | Purpose |
|---|---|---|---|
| `/api/status` | GET | `api_status()` | Returns eth0/wlan0 status, gateway, DNS, hostname, uptime |
| `/api/public-servers` | GET | `get_public_servers()` | Returns cached public iperf3 server list |
| `/api/public-servers/update` | POST | `update_public_servers()` | Fetches and parses iperf3 servers from iperf.fr |
| `/api/reboot` | POST | `api_reboot()` | Triggers system reboot or service restart |
| `/api/network/config` | GET | `api_network_config()` | Returns current eth0 IP configuration |
| `/api/network/apply` | POST | `api_network_apply()` | Applies DHCP or static IP configuration to eth0 |
| `/api/network/vlan` | POST | `api_network_vlan()` | Creates a VLAN sub-interface |
| `/api/network/vlan/delete` | POST | `api_network_vlan_delete()` | Deletes a VLAN sub-interface |
| `/api/ping` | POST | `api_ping()` | Runs ping via REST (non-streaming) |
| `/api/traceroute` | POST | `api_traceroute()` | Runs traceroute via REST |
| `/api/dns` | POST | `api_dns()` | Runs nslookup via REST |
| `/api/history` | GET | `api_history()` | Returns all stored test results as JSON array |
| `/api/history/clear` | POST | `api_clear_history()` | Deletes all JSON files in results/ |
| `/api/servers` | GET | `get_servers()` | Returns saved iperf3 server list |
| `/api/servers` | POST | `add_server()` | Adds a new server to servers.json |
| `/api/servers/<index>` | DELETE | `delete_server(index)` | Removes a server by index |
| `/api/servers/<index>/favorite` | POST | `toggle_favorite(index)` | Toggles favorite status on a server |
| `/api/ftp/config` | GET | `ftp_config()` | Returns saved FTP/SFTP configuration |
| `/api/ftp/config` | POST | `ftp_config()` | Saves FTP/SFTP configuration with base64-encoded password |
| `/api/ftp/test` | POST | `ftp_test()` | Tests FTP/SFTP connection and lists remote directory |
| `/api/ftp/send` | POST | `ftp_send()` | Uploads results to FTP/SFTP server |

### Captive Portal Routes

| Route | Purpose |
|---|---|
| `/generate_204` | Android captive portal detection |
| `/gen_204` | Chrome captive portal detection |
| `/hotspot-detect.html` | Apple captive portal detection |
| `/canonical.html` | Firefox captive portal detection |
| `/connecttest.txt` | Windows captive portal detection |
| `/redirect` | Generic redirect endpoint |
| `/success.txt` | Additional captive portal endpoint |
| `/ncsi.txt` | Windows NCSI detection |

All captive portal routes return `index.html` with HTTP 200, allowing SpeedBox to serve as a captive portal landing page.

### WebSocket Event Handlers

| Event | Handler | Purpose |
|---|---|---|
| `start_iperf3` | `handle_iperf3(data)` | Runs iperf3 test, streams intervals, emits results |
| `stop_iperf3` | `handle_stop()` | Terminates running iperf3 process |
| `run_ping` | `handle_ping(data)` | Runs ping with line-by-line streaming |
| `run_mtr` | `handle_mtr(data)` | Runs MTR with progress updates, parses JSON output |
| `run_dns` | `handle_dns(data)` | Runs nslookup, returns output |
| `stop_diagnostic` | `handle_stop_diagnostic()` | Terminates running ping/mtr/dns process |
| `start_quicktest` | `handle_quicktest(data)` | Orchestrates multi-step QuickTest across favorite servers |
| `stop_quicktest` | `handle_stop_quicktest()` | Sets stop flag and terminates current quicktest process |

### WebSocket Events Emitted (Server to Client)

| Event | Source Handler | Data |
|---|---|---|
| `iperf3_started` | `handle_iperf3` | `{message_key, message}` |
| `iperf3_interval` | `handle_iperf3` | `{seconds, mbps, bytes, retransmits, jitter_ms?, lost_packets?, lost_percent?}` |
| `iperf3_complete` | `handle_iperf3` | `{data: {server, port, duration, direction, protocol, sent_mbps, received_mbps, ...}}` |
| `iperf3_error` | `handle_iperf3`, `handle_stop` | `{message_key?, message?}` |
| `ping_output` | `handle_ping` | `{line}` |
| `ping_complete` | `handle_ping` | `{}` |
| `mtr_started` | `handle_mtr` | `{message}` |
| `mtr_progress` | `handle_mtr` | `{cycle, total}` |
| `mtr_result` | `handle_mtr` | `{src, dst, cycles, hubs: [...]}` |
| `diag_error` | Diagnostic handlers | `{message_key?, message?}` |
| `diag_stopped` | `handle_stop_diagnostic` | `{message_key}` |
| `dns_result` | `handle_dns` | `{output}` |
| `quicktest_started` | `handle_quicktest` | `{total_steps, test_name}` |
| `quicktest_step` | `handle_quicktest` | `{step, total, label, attempt, status, result?, error?}` |
| `quicktest_countdown` | `handle_quicktest` | `{step, total, remaining, duration, label}` |
| `quicktest_complete` | `handle_quicktest` | `{test_name, total_steps}` |
| `quicktest_stopped` | `handle_stop_quicktest` | `{}` |

---

## templates/base.html

**Lines:** 115
**Purpose:** Base Jinja2 layout template inherited by all pages.

**Key contents:**
- HTML head with meta viewport, favicon, CSS, vendored JS libraries (i18n.js, socket.io.min.js, chart.umd.min.js)
- Desktop navbar with brand logo, navigation links (Home, SpeedTest, Network, Diagnostic, History), language toggle button
- Mobile bottom tab bar with SVG icons and short labels (Home, Test, Network, Diag, History)
- Main content container (`{% block content %}`)
- Footer with project link, author credit, AGPL-3.0 notice, and live clock
- Toast notification container
- Global scripts: clock update (1-second interval with locale from i18n), active nav link highlighting, `showToast()` function, `toggleSection()` for collapsible sections
- `applyTranslations()` called on page load to initialize i18n

---

## templates/index.html

**Lines:** ~155
**Purpose:** Dashboard / home page with QuickTest hero card and system status overview.

**Key contents:**
- Hero card: QuickTest launcher with prominent call-to-action button
- Status cards: eth0 (status, IP, speed), wlan0 (status, IP), System (hostname, uptime)
- Tool grid: four cards linking to SpeedTest, Diagnostic, Network, History
- Maintenance section: Restart Service and Reboot System buttons with confirmation dialogs
- JavaScript: fetches `/api/status` on load to populate status cards, handles reboot/restart with polling for reconnection, QuickTest modal integration

---

## templates/speedtest.html

**Lines:** ~824
**Purpose:** Full-featured speed test page with server management, test configuration, real-time results, and QuickTest modal.

**Key contents:**
- Saved servers section: list with favorite toggle, delete, click-to-select. Add server form (name, host, port)
- Public server browser: collapsible section, region filter tabs, "Update" button to fetch from iperf.fr, "Add to saved" per server
- Test parameters form: server input, direction (upload/download), protocol (TCP/UDP), target bitrate, advanced options (test name, duration 1-300s, streams 1-64)
- Real-time results area: Chart.js line chart (bitrate over time), stat cards (average bitrate, transfer, duration, protocol, jitter, packet loss, retransmissions), log output area
- QuickTest modal: test name, target bitrate, favorite server list display, step progress bar, countdown timer, per-step result cards, completion summary
- JavaScript (~500 lines): Socket.IO connection, server CRUD, public server fetching, chart initialization, iperf3 event handling, QuickTest orchestration UI

---

## templates/diagnostic.html

**Lines:** ~293
**Purpose:** Network diagnostic tools page with Ping, MTR, and DNS Lookup.

**Key contents:**
- Three collapsible sections, each with:
  - **Ping**: target input, count selector (1-50), Start/Stop buttons, terminal-style output area with line-by-line streaming
  - **MTR**: target input, cycles (1-100), max hops (5-50), Start button, progress bar, results table (hop, hostname, IP, ASN, loss%, sent, last/avg/best/worst/stdev, spike indicator, MPLS labels)
  - **DNS Lookup**: target input, optional DNS server, Start button, preformatted output area
- JavaScript: Socket.IO event handling for `ping_output`, `ping_complete`, `mtr_started`, `mtr_progress`, `mtr_result`, `dns_result`, `diag_error`, `diag_stopped`

---

## templates/network.html

**Lines:** ~381
**Purpose:** Network configuration page with interface status, IP configuration, VLAN management, and FTP/SFTP upload.

**Key contents:**
- Interface status cards: eth0 (status, IP, mask, MAC, speed), wlan0 (status, IP, MAC), Gateway/DNS
- IP configuration form: mode toggle (DHCP/Static), conditional fields (IP, CIDR mask, gateway, DNS), Apply button
- VLAN section: interface selector, VLAN ID (1-4094), optional IP, Create/Delete buttons
- FTP/SFTP section: protocol selector (FTP/SFTP/SCP), TLS toggle, host/port/username/password fields, remote directory, Save/Test buttons, file source selector (all results / last result), filename input, Send button, remote directory listing display
- JavaScript: fetches `/api/status` and `/api/network/config` on load, handles apply with connection loss detection, FTP config save/load/test/send

---

## templates/history.html

**Lines:** ~720
**Purpose:** Test history viewer with tabbed interface, charts, tables, and data management.

**Key contents:**
- Tab bar: iPerf3, MTR, Ping, QuickTest tabs
- Per-tab content:
  - **iPerf3 tab**: Chart.js bar chart (sent/received Mbps over time), data table (date, name, server, direction, protocol, sent, received, retransmits, jitter, packet loss), mobile card layout
  - **MTR tab**: table (date, name, destination, cycles, hops, destination loss, average latency), problematic nodes highlighting
  - **Ping tab**: table (date, target, packets, loss%, RTT min/avg/max/mdev)
  - **QuickTest tab**: grouped by quicktest_id, summary cards (servers, steps, max/min bitrate, max loss, destination latency)
- Action buttons: Refresh, Delete All (with confirmation), Download JSON
- JavaScript (~400 lines): fetches `/api/history`, categorizes results by test_type, builds charts and tables, handles responsive card layout for mobile

---

## static/js/i18n.js

**Lines:** ~638
**Purpose:** Client-side internationalization engine with French and English translations.

**Key contents:**
- `TRANSLATIONS` object with `fr` and `en` sub-objects, each containing ~250 key-value pairs organized by section (nav, index, speedtest, qt, diag, net, hist, srv)
- `getLang()` -- reads language from `localStorage` key `speedbox_lang`, defaults to `'fr'`
- `setLang(lang)` -- writes language to localStorage, calls `applyTranslations()`
- `toggleLang()` -- switches between `'fr'` and `'en'`
- `t(key, params)` -- translation lookup with parameter interpolation (`{param}` syntax), falls back to French then returns the key itself
- `applyTranslations()` -- scans DOM for `[data-i18n]` elements (sets textContent or placeholder), `[data-i18n-placeholder]` elements (sets placeholder only), updates `<html lang>` attribute, updates language toggle button labels, triggers clock locale update
- `getLocale()` -- returns `'fr-FR'` or `'en-GB'` based on current language

---

## static/css/style.css

**Lines:** ~264+
**Purpose:** Complete application stylesheet with dark theme, responsive design, and component styles.

**Key contents:**
- Reset and base styles: `#0a0e17` background, `#e0e0e0` text color, system-ui font stack
- Navbar: `#131a2b` background, `#00d4ff` accent border and brand color, sticky positioning
- Mobile bottom tab bar: hidden by default, shown via media query, fixed at bottom with safe-area-inset padding
- Language toggle button: cyan accent styling
- Container and card layouts: responsive grid, card backgrounds `#131a2b`, rounded corners
- Form elements: dark input fields, cyan focus borders, styled buttons
- Table styles: striped rows, responsive overflow
- Toast notifications: positioned fixed, color-coded by type
- Collapsible sections: `section-collapse` with `open` class toggle
- Chart container styles
- Responsive breakpoints: mobile bottom bar visibility, card stacking, font size adjustments

---

## static/js/socket.io.min.js

**Purpose:** Vendored Socket.IO client library. Provides WebSocket communication with automatic reconnection, event-based messaging, and fallback to HTTP long-polling.

---

## static/js/chart.umd.min.js

**Purpose:** Vendored Chart.js library (UMD build). Provides line charts (real-time bitrate during tests) and bar charts (history trends). No external dependencies.

---

## servers.json

**Lines:** ~20
**Purpose:** User-managed list of iperf3 servers. JSON array of objects.

**Structure:**
```json
[
  {
    "name": "France",
    "host": "iperf3.moji.fr",
    "port": 5200,
    "favorite": true
  }
]
```

Each server has: `name` (display label), `host` (hostname or IP), `port` (iperf3 port), and optional `favorite` (boolean, used by QuickTest).

---

## config/.secret_key

**Purpose:** Auto-generated Flask secret key (64 hex characters = 256 bits). Created on first run with `secrets.token_hex(32)`. File permissions `0600`.

---

## config/ftp_config.json

**Purpose:** Saved FTP/SFTP server configuration. Created when user saves FTP settings. File permissions `0600`.

**Structure:**
```json
{
  "protocol": "sftp",
  "host": "ftp.example.com",
  "port": 22,
  "username": "user",
  "password_b64": "base64encodedpassword",
  "remote_path": "/uploads",
  "tls": false,
  "save_password": true
}
```

---

## config/public_servers.json

**Purpose:** Cached list of public iperf3 servers fetched from iperf.fr. Created/updated when user clicks "Update" in the public servers browser.

**Structure:**
```json
{
  "updated": "2026-04-06 14:30:22",
  "source": "https://iperf.fr/iperf-servers.php",
  "servers": [
    {
      "hostname": "bouygues.iperf.fr",
      "port": 5201,
      "location": "Paris",
      "region": "Europe",
      "datacenter": "Bouygues",
      "speed": "10G",
      "ip_version": "IPv4/IPv6"
    }
  ]
}
```

---

## results/*.json

**Purpose:** Individual test result files. Each file contains one test result.

**Naming:** `{optional_name_}{type}_{YYYYMMDD_HHMMSS}.json`

**Common fields:** `timestamp` (ISO 8601), `test_type` (iperf3, mtr, ping)

---

## speedbox.service

**Lines:** 14
**Purpose:** systemd unit file for running SpeedBox as a system service.

```ini
[Unit]
Description=SpeedBox Flask App
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/speedbox
ExecStart=/opt/speedbox/venv/bin/python app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Key settings: runs as root (required for network configuration commands), auto-restarts on failure after 3 seconds, starts after network is available.

---

## requirements.txt

**Lines:** 5
**Purpose:** Python package dependencies for pip installation.

```
Flask==3.1.3
Flask-SocketIO==5.6.1
gevent==25.9.1
paramiko==4.0.0
requests==2.33.1
```

- **Flask** -- web framework
- **Flask-SocketIO** -- WebSocket support
- **gevent** -- async runtime for cooperative multitasking
- **paramiko** -- SFTP/SCP client library
- **requests** -- HTTP client for fetching public server list from iperf.fr

---

## .gitignore

**Lines:** ~8
**Purpose:** Excludes runtime files from version control: `config/`, `results/`, `__pycache__/`, `venv/`, `*.pyc`.

---

## LICENSE

**Lines:** ~661
**Purpose:** Full text of the GNU Affero General Public License v3.0.

---

## README.md

**Lines:** ~100
**Purpose:** Project overview, features, installation instructions, and license information.
