# SpeedBox Architecture

## 1. System Overview

SpeedBox is a three-tier network testing web application designed for Raspberry Pi 5 running DietPi. It provides real-time speed tests, diagnostics, and network configuration through a browser-based interface.

```
+-------------------+         WebSocket / HTTP          +-------------------------+
|                   |  <------------------------------>  |                         |
|   Browser         |    Socket.IO (bidirectional)       |   Flask + SocketIO      |
|                   |    REST API (request/response)     |   (gevent async_mode)   |
|  - Vanilla JS     |                                    |                         |
|  - Chart.js       |                                    |   app.py (1392 lines)   |
|  - Socket.IO      |                                    |                         |
|  - Custom i18n    |                                    +----------+--------------+
|                   |                                               |
+-------------------+                                               |
                                                          +---------+---------+
                                                          |                   |
                                                   +------+------+    +------+------+
                                                   | System      |    | Filesystem  |
                                                   | Tools       |    |             |
                                                   |             |    | results/    |
                                                   | - iperf3    |    |   *.json    |
                                                   | - mtr       |    |             |
                                                   | - ping      |    | config/     |
                                                   | - traceroute|    |  .secret_key|
                                                   | - nslookup  |    |  ftp_config |
                                                   | - ip        |    |  pub_servers|
                                                   | - ethtool   |    |             |
                                                   +-------------+    | servers.json|
                                                                      +-------------+
```

**Tier 1 -- Presentation (Browser):** Vanilla JavaScript with Chart.js for data visualization and Socket.IO client for real-time communication. A custom i18n system provides French and English translations. No build step or framework is required; all scripts run directly in the browser.

**Tier 2 -- Application (Flask + SocketIO):** A single Python process (`app.py`) serves both the REST API and WebSocket handlers. Flask-SocketIO with gevent async_mode enables cooperative multitasking so that long-running subprocesses (iperf3, mtr) do not block other connections.

**Tier 3 -- System and Storage:** External CLI tools are invoked via `subprocess.Popen` or `subprocess.run` to perform actual network measurements. Results are persisted as individual JSON files in the `results/` directory. Configuration is stored in `config/` and `servers.json`.

## 2. Technology Stack

### Python 3.13 + Flask 3.1

Flask serves as the lightweight web framework. It handles page rendering (Jinja2 templates), REST API endpoints, and acts as the HTTP server foundation. Flask was chosen for its simplicity: no ORM, no database, no heavy abstractions. The entire application fits in a single `app.py` file.

### Flask-SocketIO 5.6 with gevent async_mode

Flask-SocketIO provides WebSocket support on top of Flask. The `async_mode='gevent'` setting is critical: it allows the server to handle multiple concurrent WebSocket connections without threads. When one client runs a 60-second iperf3 test, other clients can still interact with the application because gevent yields control during I/O waits.

WebSocket is used (rather than HTTP polling) because network tests produce streaming output. An iperf3 test emits one interval measurement per second for the duration of the test. WebSocket allows the server to push each interval to the client immediately, enabling real-time chart updates.

### gevent monkey.patch_all()

The very first lines of `app.py` are:

```python
from gevent import monkey
monkey.patch_all()
```

This must happen before any other imports. `monkey.patch_all()` replaces the standard library's blocking I/O operations (socket, threading, subprocess, time.sleep) with cooperative (non-blocking) versions. Without this patch, a `subprocess.Popen.communicate()` call would block the entire server. With the patch, gevent can switch to another greenlet while waiting for subprocess output, enabling concurrent request handling in a single-threaded process.

### Chart.js (vendored)

Chart.js is used for real-time bitrate visualization during speed tests and for historical trend charts on the history page. The library is vendored (`static/js/chart.umd.min.js`) rather than loaded from a CDN. This is a deliberate choice: SpeedBox is often deployed on isolated networks where internet access may be unavailable or unreliable. Vendoring ensures the application works fully offline.

### Socket.IO Client (vendored)

Similarly, `static/js/socket.io.min.js` is bundled with the application. The Socket.IO client handles WebSocket connection management, automatic reconnection, and event-based communication with the Flask-SocketIO backend.

### Vanilla JavaScript

No framework (React, Vue, Angular) is used. Each page template contains its own inline `<script>` block with plain JavaScript. This eliminates build tooling, reduces complexity, and keeps the frontend immediately understandable. DOM manipulation is done with `document.getElementById`, `document.querySelector`, and direct property assignment.

### Custom i18n System

Rather than using Flask-Babel or any server-side localization, SpeedBox implements a client-side i18n engine in `static/js/i18n.js`. A `TRANSLATIONS` dictionary contains approximately 250 keys in both French and English. The `t(key, params)` function looks up translations with parameter interpolation. The `applyTranslations()` function scans the DOM for elements with `data-i18n` attributes and replaces their content. Language preference is stored in `localStorage`. This approach was chosen because all translation happens in the browser, avoiding server-side locale management entirely.

## 3. Speed Test Flow

The following describes the complete lifecycle of a single iperf3 speed test from user click to result display:

1. **User clicks Start**: The user fills in server, port, direction, protocol, and optional parameters (bandwidth, threads, duration, test name) in the SpeedTest page form, then clicks the Start button.

2. **JS emits 'start_iperf3'**: The frontend JavaScript constructs a data object with all parameters and emits a `start_iperf3` WebSocket event via Socket.IO:
   ```javascript
   socket.emit('start_iperf3', {
       server: '192.168.1.100', port: 5201,
       duration: 10, direction: 'download',
       bandwidth: '100M', threads: 1,
       protocol: 'tcp', test_name: 'My Test'
   });
   ```

3. **Flask handler receives event**: The `handle_iperf3()` function decorated with `@socketio.on('start_iperf3')` is invoked. Flask-SocketIO automatically associates the event with the client's session (`request.sid`).

4. **Input validation**: The handler validates that a server was provided. If bandwidth was specified without a unit suffix, it appends `'M'` (megabits).

5. **Command construction**: An iperf3 command list is built:
   ```python
   cmd = ['iperf3', '-c', server, '-p', str(port), '-t', str(duration), '-J', '--forceflush']
   ```
   The `-J` flag requests JSON output. `-R` is appended for download (reverse) mode. `-u` and `-b` are added for UDP. `-P` sets the number of parallel streams.

6. **Subprocess launch**: `subprocess.Popen(cmd, stdout=PIPE, stderr=PIPE, text=True)` starts the iperf3 process. The process object is stored in `iperf3_processes[request.sid]` for lifecycle management.

7. **Output collection**: `process.communicate(timeout=duration+30)` waits for the process to complete and captures all stdout/stderr. The timeout prevents indefinite hangs.

8. **JSON parsing**: The stdout (which contains iperf3's JSON output) is parsed with `json.loads()`. Errors are checked at multiple levels: JSON decode errors, iperf3-level errors in the `error` field, and non-zero return codes.

9. **Interval streaming**: The parsed JSON contains an `intervals` array. For each interval, the handler extracts bitrate (bits_per_second / 1,000,000 for Mbps), bytes transferred, retransmits (TCP), or jitter/loss (UDP). Each interval is emitted as an `iperf3_interval` event with a 50ms sleep between emissions to prevent flooding:
   ```python
   emit('iperf3_interval', interval_data)
   socketio.sleep(0.05)
   ```

10. **Final results emission**: After all intervals, the `end` section of the JSON is parsed for summary statistics. For TCP, both `sum_sent` and `sum_received` are extracted. For UDP, the `sum` object provides jitter, loss, and packet counts. An `iperf3_complete` event is emitted with the full result.

11. **Client-side chart update**: The frontend JavaScript listens for `iperf3_interval` events and adds each data point to the Chart.js line chart in real time. On `iperf3_complete`, it displays the final statistics (average bitrate, transfer, retransmits/jitter/loss).

12. **Result persistence**: `save_result('iperf3', result, test_name=test_name)` writes the result to a JSON file in the `results/` directory with a timestamped filename.

13. **Process cleanup**: In a `finally` block, the process is removed from `iperf3_processes` and killed if still running.

## 4. Process Management

SpeedBox manages multiple concurrent subprocess executions using per-session dictionaries keyed by `request.sid` (the Socket.IO session identifier).

### Process Tracking Dictionaries

```python
iperf3_processes = {}        # sid -> Popen object for iperf3 tests
diag_processes = {}          # sid -> Popen object for ping/mtr/dns
quicktest_processes = {}     # sid -> Popen object for current quicktest step
quicktest_stop_flags = set() # set of sids requesting quicktest stop
```

Each dictionary maps a Socket.IO session ID to the active subprocess for that session. This ensures that only one test of each type can run per client session, and that stop requests target the correct process.

### Process Lifecycle

1. **Launch**: `subprocess.Popen(cmd, stdout=PIPE, stderr=PIPE)` creates the child process.
2. **Track**: The process object is stored in the appropriate dictionary: `iperf3_processes[session_id] = process`.
3. **Communicate**: For iperf3, `process.communicate(timeout=...)` collects all output at once. For ping and MTR, `process.stdout.readline()` streams output line by line.
4. **Cleanup (finally block)**: The process is popped from the dictionary. If it is still running (`proc.poll() is None`), it is killed:
   ```python
   finally:
       proc = iperf3_processes.pop(session_id, None)
       if proc and proc.poll() is None:
           proc.kill()
   ```

### Stop Handlers

When a user clicks Stop, the corresponding handler is invoked:

1. The process is popped from the tracking dictionary.
2. `proc.terminate()` sends SIGTERM for graceful shutdown.
3. `proc.wait(timeout=3)` waits up to 3 seconds for the process to exit.
4. If the process has not exited after 3 seconds, `proc.kill()` sends SIGKILL for forced termination.

```python
@socketio.on('stop_iperf3')
def handle_stop():
    proc = iperf3_processes.pop(request.sid, None)
    if proc:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            proc.kill()
    emit('iperf3_error', {'message_key': 'srv.stopped_by_user'})
```

### QuickTest Stop Flags

QuickTest runs multiple sequential steps in a loop. A simple `terminate()` would only stop the current subprocess, not the orchestration loop. The `quicktest_stop_flags` set solves this:

- When the user requests a stop, `quicktest_stop_flags.add(sid)` is called.
- The orchestration loop checks `if session_id in quicktest_stop_flags` before each step and before each retry/pause countdown.
- When the loop exits (naturally or via flag), `quicktest_stop_flags.discard(session_id)` cleans up.

## 5. Data Flow

### Result Storage

Test results are stored as individual JSON files in `/opt/speedbox/results/`. The naming convention is:

```
{test_name_sanitized}_{type}_{YYYYMMDD_HHMMSS}.json
```

If no test name is provided:

```
{type}_{YYYYMMDD_HHMMSS}.json
```

Examples:
- `iperf3_20260406_143022.json`
- `Client_Paris_mtr_20260406_143100.json`
- `ping_20260406_143200.json`

The `save_result()` function sanitizes the test name (replacing non-alphanumeric characters with underscores), adds a `timestamp` (ISO format) and `test_type` field to the data, and writes the JSON with 2-space indentation.

### Result Loading

The `load_results()` function reads up to 200 of the most recent JSON files from the results directory, sorted in reverse chronological order by filename. Files that fail to parse (corrupt JSON, I/O errors) are silently skipped.

```python
json_files = [f for f in os.listdir(RESULTS_DIR) if f.endswith('.json')]
for filename in sorted(json_files, reverse=True)[:200]:
    ...
```

### History Display

The history page (`/history`) loads all results via the `/api/history` REST endpoint. The frontend JavaScript categorizes results by `test_type` (iperf3, mtr, ping, quicktest) and displays them in separate tabs. Each tab contains:

- A Chart.js chart showing trends (bitrate over time for iperf3, latency for MTR/ping).
- A responsive data table (desktop) or card layout (mobile) showing individual test results.
- A "Download JSON" button for raw data export.

The "Clear History" button calls `/api/history/clear`, which deletes all JSON files in the results directory.

## 6. Security Model

### Secret Key Management

Flask's session security depends on a secret key. SpeedBox auto-generates one on first run:

```python
SECRET_FILE = os.path.join(CONFIG_DIR, '.secret_key')
if os.path.exists(SECRET_FILE):
    app.config['SECRET_KEY'] = open(SECRET_FILE).read().strip()
else:
    _key = secrets.token_hex(32)  # 256-bit random key
    open(SECRET_FILE, 'w').write(_key)
    os.chmod(SECRET_FILE, 0o600)  # Owner-only read/write
    app.config['SECRET_KEY'] = _key
```

The key is persisted in `config/.secret_key` with mode `0600` so that only root can read it. This ensures sessions survive application restarts without requiring manual configuration.

### FTP Credential Storage

FTP/SFTP passwords are base64-encoded (not encrypted) and stored in `config/ftp_config.json` with mode `0600`. Base64 encoding prevents casual exposure in logs or terminal output but does not provide cryptographic security. The file permission restricts access to the root user.

### Input Validation

All user-supplied input that reaches subprocess commands is validated:

- **Hostnames/IPs**: Must match `^[a-zA-Z0-9.\-:]+$` (alphanumeric, dots, hyphens, colons). This prevents shell injection and command injection.
- **IP addresses**: Must match `^\d+\.\d+\.\d+\.\d+$`.
- **CIDR masks**: Must be an integer between 1 and 32.
- **VLAN IDs**: Must be an integer between 1 and 4094.
- **Interface names**: Must match `^[a-zA-Z0-9]+$`.
- **Numeric parameters** (duration, count, threads): Clamped to safe ranges using `max(min_val, min(max_val, user_input))`.

### Subprocess Safety

All subprocess calls use list arguments rather than shell strings:

```python
subprocess.Popen(['iperf3', '-c', server, '-p', str(port)], ...)
```

No call uses `shell=True`. This eliminates shell injection vulnerabilities because each element of the list is passed as a separate argument to `execvp`, preventing metacharacter interpretation.

### Execution Context

SpeedBox runs as root (configured in `speedbox.service`). This is required because several operations need root privileges:

- `ip addr add/flush/route` for network configuration
- `ip link add` for VLAN creation
- `ethtool` for link speed detection
- `sudo reboot` for system restart
- Writing to `/etc/network/interfaces` and `/etc/resolv.conf`

### CORS Configuration

`cors_allowed_origins='*'` is set on the SocketIO instance. This allows connections from any origin, which is necessary when SpeedBox is accessed through a reverse proxy or from a different hostname/IP than the one configured. In a typical deployment on an isolated test network, this is an acceptable trade-off for ease of use.
