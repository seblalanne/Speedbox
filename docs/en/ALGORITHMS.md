# SpeedBox Algorithms

This document provides detailed descriptions and pseudo-code for the key algorithms used in SpeedBox.

---

## 1. MTR Hop Analysis

**Source:** `parse_mtr_hubs()` in `app.py`, lines 56-91

### Purpose

Transforms raw MTR JSON hub data into structured hop records with loss severity classification and latency spike detection. This processed data drives the color-coded MTR results table in the diagnostic page.

### Loss Classification

Each hop's packet loss percentage is categorized into one of four severity levels:

| Loss % | Class | Meaning |
|---|---|---|
| 0% | `good` | No packet loss |
| 1-5% | `warn` | Minor loss, possibly normal for transit hops |
| 6-20% | `degraded` | Significant loss, likely a problem |
| >20% | `critical` | Severe loss, definite network issue |

### Spike Detection

A latency spike is flagged when a hop's average latency deviates significantly from the previous hop, indicating a potential bottleneck. Two conditions are checked (either triggers a spike):

1. **Absolute delta:** The difference between the current hop's average latency and the previous hop's average exceeds 20ms.
2. **Relative multiplier:** The current hop's average is more than 3x the previous hop's average.

A guard condition prevents false positives: the hop's `count` (number of samples) must be greater than 1. This avoids flagging hops that only responded once.

### MPLS Label Extraction

If the MTR data includes MPLS information (from the `-e` flag), it is extracted from either the `MPLS` or `Mplss` field (MTR versions vary in field naming).

### Pseudo-code

```
function parse_mtr_hubs(hubs_raw):
    hubs = []
    prev_avg = 0

    for each hub in hubs_raw:
        # Parse hostname and IP from "hostname (ip)" format
        if hub.host matches "name (ip)":
            hostname = name portion
            ip = ip portion
        else:
            hostname = ip = hub.host

        # Classify loss severity
        loss = hub.Loss%
        if loss == 0:       loss_class = "good"
        elif loss <= 5:     loss_class = "warn"
        elif loss <= 20:    loss_class = "degraded"
        else:               loss_class = "critical"

        # Detect latency spikes
        avg = hub.Avg
        delta = avg - prev_avg
        spike = (delta > 20 OR (prev_avg > 0 AND avg > prev_avg * 3))
                AND hub.count > 1

        # Update previous average (skip zero-avg hops to avoid resetting baseline)
        if avg > 0:
            prev_avg = avg

        # Extract MPLS labels if present
        mpls_info = hub.MPLS or hub.Mplss or null

        # Build structured hop record
        hubs.append({
            hop: hub.count,
            hostname, ip,
            asn: hub.ASN,
            loss, loss_class,
            snt: hub.Snt,
            last: hub.Last, avg,
            best: hub.Best, wrst: hub.Wrst,
            stdev: hub.StDev,
            spike, mpls: mpls_info
        })

    return hubs
```

### Example

Given three hops with averages 1.2ms, 5.4ms, 45.8ms:

- Hop 1: delta=1.2, not a spike (1.2 < 20 and no previous)
- Hop 2: delta=4.2, not a spike (4.2 < 20 and 5.4 < 1.2*3=3.6... actually 5.4 > 3.6 but need count > 1)
- Hop 3: delta=40.4, spike detected (40.4 > 20)

---

## 2. QuickTest Orchestration

**Source:** `handle_quicktest()` in `app.py`, lines 1080-1368

### Purpose

QuickTest automates a comprehensive network assessment against all favorite servers. It runs a predefined sequence of tests (MTR + multiple iperf3 configurations) per server, with retry logic, real-time progress reporting, and graceful cancellation.

### Step Construction

For each favorite server (maximum 3), four steps are generated:

```
Per favorite server:
    Step A: MTR          - 60 cycles, 20 max hops
    Step B: iperf3 UDP   - target bitrate, 60 seconds, 1 stream
    Step C: iperf3 TCP   - unlimited bitrate, 60 seconds, 1 stream
    Step D: iperf3 TCP   - target_bitrate/4 per stream, 60 seconds, 4 streams
```

With 3 favorite servers, this produces 12 total steps. At 60 seconds per step plus 10-second pauses between steps, a full QuickTest takes approximately 14 minutes.

### Retry Logic

- **MTR steps:** 1 attempt only (MTR failures are usually connectivity issues, retrying won't help)
- **iperf3 steps:** Up to 3 attempts (iperf3 servers may be temporarily busy)
- **Between retries:** 10-second countdown pause, visible to the user
- **Between steps:** 10-second countdown pause (allows the iperf3 server to release the port)

### Stop Flag Mechanism

The stop flag is a cooperative cancellation system. It does not kill the orchestration greenlet directly. Instead:

1. User clicks Stop, which triggers `handle_stop_quicktest()`.
2. The handler adds `request.sid` to `quicktest_stop_flags` set.
3. The handler also terminates the currently running subprocess (if any).
4. The orchestration loop checks the flag at multiple points:
   - Before starting each step
   - Before each retry attempt
   - During each second of the countdown timers
5. When the flag is detected, the loop breaks immediately.
6. On exit, the flag is discarded: `quicktest_stop_flags.discard(session_id)`.

### Pseudo-code

```
function handle_quicktest(data):
    test_name = data.test_name or "QuickTest"
    target_bitrate = data.target_bitrate or 100
    quicktest_id = timestamp()

    servers = load_servers()
    fav_servers = [s for s in servers if s.favorite][:3]

    if no fav_servers:
        emit error "no favorites"
        return

    # Build step list
    steps = []
    for each server in fav_servers:
        steps.append(MTR step:  cycles=60, maxhops=20)
        steps.append(UDP step:  bitrate=target_bitrate + "M", duration=60, streams=1)
        steps.append(TCP step:  bitrate=0 (unlimited), duration=60, streams=1)
        steps.append(TCP step:  bitrate=(target_bitrate/4) + "M", duration=60, streams=4)

    total_steps = len(steps)
    emit "quicktest_started" {total_steps, test_name}

    session_id = request.sid
    remove session_id from stop_flags  # clear any stale flag

    for step_idx, step in enumerate(steps):
        if session_id in stop_flags: break

        step_num = step_idx + 1
        success = false
        attempts = 0
        max_attempts = 1 if step.type == "mtr" else 3

        while not success AND attempts < max_attempts AND not stopped:
            attempts += 1
            emit "quicktest_step" {step_num, label, attempt, status="running"}

            try:
                if step.type == "mtr":
                    # Run MTR
                    proc = Popen(["mtr", "-j", "-z", "-e", "-b",
                                  "-c", cycles, "-m", maxhops, host])
                    quicktest_processes[sid] = proc

                    # Progress: emit cycle count every second
                    elapsed = 0
                    while proc is running:
                        elapsed += 1
                        emit "quicktest_countdown" {cycle, total_cycles}
                        sleep(1)

                    parse JSON output
                    run parse_mtr_hubs() on hubs
                    save_result("mtr", result)
                    emit "quicktest_step" {status="done", result}
                    success = true

                else:  # iperf3
                    # Build command
                    cmd = ["iperf3", "-c", host, "-p", port, "-t", duration, "-J"]
                    if UDP: cmd += ["-u", "-b", bitrate]
                    if TCP with streams > 1: cmd += ["-P", streams]
                    if TCP with bitrate != 0: cmd += ["-b", bitrate]

                    proc = Popen(cmd)
                    quicktest_processes[sid] = proc

                    # Countdown: emit remaining seconds
                    for sec in range(duration):
                        if proc has exited: break
                        remaining = duration - sec
                        emit "quicktest_countdown" {remaining, duration}
                        sleep(1)

                    proc.wait(timeout=30)
                    parse JSON output
                    extract metrics (sent_mbps, received_mbps, jitter, loss, retransmits)
                    save result to file
                    emit "quicktest_step" {status="done", result}
                    success = true

            except Exception as e:
                emit "quicktest_step" {status="error", error=str(e)}

                if attempts < max_attempts AND not stopped:
                    # Retry countdown: 10 seconds
                    for r in range(10, 0, -1):
                        if stopped: break
                        emit "quicktest_countdown" {remaining=r, label="Retry pause"}
                        sleep(1)

        # Pause between steps: 10 seconds
        if not last step AND not stopped:
            for r in range(10, 0, -1):
                if stopped: break
                emit "quicktest_countdown" {remaining=r, label="Pause"}
                sleep(1)

    discard session_id from stop_flags
    emit "quicktest_complete" {test_name, total_steps}
```

---

## 3. iperf3 JSON Parsing

**Source:** `handle_iperf3()` in `app.py`, lines 591-708

### Purpose

Runs an iperf3 test, streams per-second interval data for real-time chart updates, and extracts final summary metrics. Handles both TCP and UDP protocols with different output structures.

### Command Construction

The iperf3 command is built as a list to avoid shell injection:

```
Base:       iperf3 -c <server> -p <port> -t <duration> -J --forceflush
Download:   + -R                    (reverse mode)
TCP rate:   + -b <bandwidth>        (only if bandwidth != "0")
UDP:        + -u -b <bandwidth>     (bandwidth "0" means unlimited)
Parallel:   + -P <threads>          (only if threads > 1)
```

The `-J` flag is critical: it makes iperf3 output JSON instead of human-readable text, enabling programmatic parsing. The `--forceflush` flag ensures output is flushed promptly.

### Interval Parsing

iperf3's JSON output contains an `intervals` array where each element represents one second of the test. For each interval:

```
function parse_interval(interval, protocol):
    streams = interval.streams
    summary = interval.sum or streams[0]  # sum aggregates all parallel streams

    data = {
        seconds:     round(summary.end, 1),
        mbps:        round(summary.bits_per_second / 1_000_000, 2),
        bytes:       summary.bytes,
        retransmits: summary.retransmits  # TCP only
    }

    if protocol == "udp":
        data.jitter_ms    = round(summary.jitter_ms, 3)
        data.lost_packets = summary.lost_packets
        data.packets      = summary.packets
        data.lost_percent = round((lost_packets / max(packets, 1)) * 100, 3)

    return data
```

### Final Result Extraction

After all intervals, the `end` section of the JSON provides summary statistics:

```
function parse_final_result(end_data, protocol):
    if protocol == "udp":
        ss = end_data.sum
        result = {
            sent_mbps:     round(ss.bits_per_second / 1e6, 2),
            received_mbps: round(ss.bits_per_second / 1e6, 2),
            jitter_ms:     round(ss.jitter_ms, 3),
            lost_packets:  ss.lost_packets,
            total_packets: ss.packets,
            lost_percent:  round((ss.lost_packets / max(ss.packets, 1)) * 100, 3)
        }
    else:  # TCP
        sent = end_data.sum_sent
        received = end_data.sum_received
        result = {
            sent_mbps:      round(sent.bits_per_second / 1e6, 2),
            received_mbps:  round(received.bits_per_second / 1e6, 2),
            sent_bytes:     sent.bytes,
            received_bytes: received.bytes,
            retransmits:    sent.retransmits
        }
    return result
```

### Error Handling

Errors are checked at three levels, in order:

1. **JSON decode failure:** stdout is not valid JSON (iperf3 crashed or produced garbled output).
2. **iperf3 application error:** The parsed JSON contains an `error` field (e.g., "unable to connect to server").
3. **Non-zero exit code:** iperf3 returned a non-zero status with an error in stderr.

### Pseudo-code (Full Flow)

```
function handle_iperf3(data):
    server = data.server
    port = data.port or 5201
    duration = data.duration or 10
    direction = data.direction or "download"
    bandwidth = data.bandwidth or "0"
    threads = data.threads or 1
    protocol = data.protocol or "tcp"
    test_name = data.test_name

    # Validate
    if not server: emit error; return
    if bandwidth has no unit suffix: bandwidth += "M"

    # Build command
    cmd = ["iperf3", "-c", server, "-p", port, "-t", duration, "-J", "--forceflush"]
    if direction == "download": cmd += ["-R"]
    if bandwidth != "0" and protocol == "tcp": cmd += ["-b", bandwidth]
    if protocol == "udp": cmd += ["-u", "-b", bandwidth]
    if threads > 1: cmd += ["-P", threads]

    emit "iperf3_started"
    session_id = request.sid

    try:
        process = Popen(cmd, stdout=PIPE, stderr=PIPE)
        iperf3_processes[session_id] = process

        stdout, stderr = process.communicate(timeout=duration + 30)

        # Parse JSON
        try:
            iperf_data = json.loads(stdout)
        except JSONDecodeError:
            emit error; return

        if iperf_data.error: emit error; return
        if process.returncode != 0: emit error; return

        # Stream intervals
        for interval in iperf_data.intervals:
            interval_data = parse_interval(interval, protocol)
            emit "iperf3_interval" interval_data
            sleep(0.05)  # pace emission to avoid flooding

        # Extract and emit final results
        result = parse_final_result(iperf_data.end, protocol)
        result.test_name = test_name
        save_result("iperf3", result)
        emit "iperf3_complete" {data: result}

    except TimeoutExpired:
        process.kill()
        emit error "timeout"
    except Exception as e:
        emit error str(e)
    finally:
        proc = iperf3_processes.pop(session_id, None)
        if proc and proc.poll() is None:
            proc.kill()
```

---

## 4. Network Configuration Rewriting

**Source:** `write_eth0_config()` in `app.py`, lines 391-411; `parse_eth0_config()` lines 361-389

### Purpose

Modifies the eth0 network interface configuration in `/etc/network/interfaces` while preserving all other interface blocks (wlan0, lo, VLANs). Creates a backup before writing.

### Parsing Algorithm

`parse_eth0_config()` extracts the current eth0 configuration:

```
function parse_eth0_config():
    config = {mode: "dhcp", ip: "", mask: "24", gateway: "", dns: ""}

    content = read("/etc/network/interfaces")

    # Find the eth0 block using regex
    # Match: iface eth0 inet <mode> followed by indented config lines
    # Stop at: next "iface" line, WiFi comment section, or end of file
    match = regex search:
        pattern: "iface\s+eth0\s+inet\s+(\w+)(.*?)(?=\niface\s|\n#\s*WiFi|\n#\s*wifi|\Z)"
        flags: DOTALL (. matches newlines)

    if no match: return config  # defaults

    config.mode = match.group(1)  # "static" or "dhcp"
    block = match.group(2)        # remaining lines of eth0 block

    # Extract parameters from block
    config.ip      = search "address\s+(\S+)" in block
    config.mask    = netmask_to_cidr(search "netmask\s+(\S+)" in block)
    config.gateway = search "gateway\s+(\S+)" in block
    config.dns     = search "dns-nameservers\s+(.+)" in block

    return config
```

### Writing Algorithm

`write_eth0_config()` replaces the eth0 block in-place:

```
function write_eth0_config(mode, ip, mask, gateway, dns):
    # Step 1: Create backup
    copy "/etc/network/interfaces" to "/etc/network/interfaces.bak"

    # Step 2: Read current content
    content = read("/etc/network/interfaces")

    # Step 3: Build new eth0 block
    if mode == "dhcp":
        new_block = "allow-hotplug eth0\niface eth0 inet dhcp\n"
    else:
        netmask = cidr_to_netmask(mask)
        new_block = "allow-hotplug eth0\niface eth0 inet static\n"
        new_block += "address " + ip + "\n"
        new_block += "netmask " + netmask + "\n"
        if gateway: new_block += "gateway " + gateway + "\n"
        if dns:     new_block += "dns-nameservers " + dns + "\n"

    # Step 4: Replace eth0 block using regex substitution
    # Pattern matches: allow-hotplug eth0, iface eth0 line, and all
    # subsequent address/netmask/gateway/dns-nameservers lines
    new_content = regex replace:
        pattern: "allow-hotplug eth0\niface eth0 inet \w+[^\n]*\n
                  (?:(?:address|netmask|gateway|dns-nameservers)\s+[^\n]+\n)*"
        replacement: new_block
        in: content

    # Step 5: Write modified content
    write("/etc/network/interfaces", new_content)
```

### CIDR / Netmask Conversion

```
function cidr_to_netmask(cidr):
    bits = integer(cidr)
    mask = (0xFFFFFFFF >> (32 - bits)) << (32 - bits)
    return format as "A.B.C.D" by extracting each byte

    # Example: cidr=24
    # mask = 0xFFFFFF00
    # result = "255.255.255.0"

function netmask_to_cidr(netmask):
    # Count the number of 1-bits across all octets
    total = 0
    for each octet in netmask.split("."):
        total += count_ones_in_binary(integer(octet))
    return total

    # Example: "255.255.255.0"
    # 8 + 8 + 8 + 0 = 24
```

### Safety Measures

- **Backup:** `shutil.copy2()` preserves metadata and creates a `.bak` file before any write.
- **Regex precision:** The substitution pattern only matches the eth0 block. Lines for other interfaces (wlan0, lo, VLANs) are not touched because they do not start with `allow-hotplug eth0`.
- **Immediate application:** After rewriting the file, the handler applies the changes live using `ip addr`, `ip route`, and optionally updates `/etc/resolv.conf`.

---

## 5. i18n System

**Source:** `static/js/i18n.js`, 638 lines

### Purpose

Provides client-side internationalization with French and English translations. No server-side locale management is needed; everything happens in the browser.

### TRANSLATIONS Dictionary Structure

```javascript
var TRANSLATIONS = {
    fr: {
        'nav.home': 'Accueil',
        'nav.speedtest': 'SpeedTest',
        'speedtest.connecting': 'Connexion a {server}:{port} ({proto} {dir})...',
        // ~250 keys total
    },
    en: {
        'nav.home': 'Home',
        'nav.speedtest': 'SpeedTest',
        'speedtest.connecting': 'Connecting to {server}:{port} ({proto} {dir})...',
        // ~250 keys total
    }
};
```

Keys follow a dot-separated namespace convention: `section.identifier`. Sections include: `nav`, `index`, `speedtest`, `qt` (QuickTest), `diag`, `net`, `hist`, `srv` (server-side messages).

Values may contain parameter placeholders in `{param}` syntax.

### t(key, params) -- Translation Lookup

```
function t(key, params):
    lang = getLang()  # from localStorage, default "fr"

    # Lookup chain: current language -> French fallback -> raw key
    str = TRANSLATIONS[lang][key]
          or TRANSLATIONS["fr"][key]
          or key

    # Parameter interpolation
    if params:
        for each (k, v) in params:
            str = str.replace("{" + k + "}", v)

    return str
```

The fallback chain ensures that:
1. If a key exists in the current language, it is used.
2. If missing in the current language (e.g., a new key not yet translated to English), French is used.
3. If missing from both languages, the raw key string is returned (useful for debugging missing translations).

### applyTranslations() -- DOM Scanning

```
function applyTranslations():
    # Scan all elements with data-i18n attribute
    for each element with [data-i18n]:
        key = element.getAttribute("data-i18n")
        translated = t(key)

        if element is INPUT or TEXTAREA:
            element.placeholder = translated
        else:
            element.textContent = translated

    # Scan elements with data-i18n-placeholder attribute
    # (for inputs that need both visible label AND translated placeholder)
    for each element with [data-i18n-placeholder]:
        element.placeholder = t(element.getAttribute("data-i18n-placeholder"))

    # Update HTML lang attribute for accessibility
    document.documentElement.lang = getLang()

    # Update language toggle button labels
    lang = getLang()
    label = (lang == "fr") ? "EN" : "FR"
    set #lang-toggle text to label
    set #lang-toggle-mobile text to label

    # Trigger clock locale update
    if updateClock function exists:
        updateClock()
```

### localStorage Persistence

```
function getLang():
    return localStorage.getItem("speedbox_lang") or "fr"

function setLang(lang):
    localStorage.setItem("speedbox_lang", lang)
    applyTranslations()

function toggleLang():
    setLang(getLang() == "fr" ? "en" : "fr")
```

The language preference survives browser restarts and is per-browser (not per-session or per-user). The default language is French.

### getLocale() -- Date/Number Formatting

```
function getLocale():
    return (getLang() == "fr") ? "fr-FR" : "en-GB"
```

Used by the clock and by `Date.toLocaleString()` calls to format dates and numbers according to the selected language convention.

### HTML Usage

In templates, translatable elements use the `data-i18n` attribute:

```html
<h1 data-i18n="index.title">SpeedBOX</h1>
<input data-i18n-placeholder="speedtest.server_placeholder" placeholder="ex: 192.168.1.100">
<span data-i18n="nav.home">Accueil</span>
```

The hardcoded French text serves as the default content before JavaScript executes. Once `applyTranslations()` runs (on page load), all elements are updated to the user's preferred language.

For dynamic content generated in JavaScript, the `t()` function is called directly:

```javascript
showToast(t('speedtest.test_done', {rate: '950.23'}));
// -> "Test complete: 950.23 Mbps" (English)
// -> "Test termine : 950.23 Mbps" (French)
```
