from gevent import monkey
monkey.patch_all()
# SpeedBox - Network Testing Web Application
# Copyright (C) 2026 slalanne
# SPDX-License-Identifier: AGPL-3.0-only
# =============================================================================
# SpeedBOX - Application principale
# =============================================================================
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import subprocess
import json
import os
import re
import secrets
import base64
from cryptography.fernet import Fernet
import shutil
from datetime import datetime
import socket
import io
import paramiko
import ftplib
import requests as http_requests

app = Flask(__name__)

RESULTS_DIR = '/opt/speedbox/results'
CONFIG_DIR = '/opt/speedbox/config'

# SECRET_KEY auto-genere et persiste
SECRET_FILE = os.path.join(CONFIG_DIR, '.secret_key')
os.makedirs(CONFIG_DIR, exist_ok=True)
if os.path.exists(SECRET_FILE):
    with open(SECRET_FILE, 'r') as _f:
        app.config['SECRET_KEY'] = _f.read().strip()
else:
    _key = secrets.token_hex(32)
    with open(SECRET_FILE, 'w') as _f:
        _f.write(_key)
    os.chmod(SECRET_FILE, 0o600)
    app.config['SECRET_KEY'] = _key

# Cle Fernet pour chiffrer les mots de passe FTP au repos
FERNET_KEY_FILE = os.path.join(CONFIG_DIR, '.fernet_key')
if os.path.exists(FERNET_KEY_FILE):
    with open(FERNET_KEY_FILE, 'rb') as _f:
        _fernet_key = _f.read().strip()
else:
    _fernet_key = Fernet.generate_key()
    with open(FERNET_KEY_FILE, 'wb') as _f:
        _f.write(_fernet_key)
    os.chmod(FERNET_KEY_FILE, 0o600)
_fernet = Fernet(_fernet_key)

socketio = SocketIO(app, async_mode='gevent', cors_allowed_origins=['http://localhost:5000', 'http://127.0.0.1:5000', 'http://192.168.0.100:5000'])

quicktest_processes = {}
iperf3_processes = {}
diag_processes = {}
quicktest_stop_flags = set()

def validate_target(host):
    host = (host or '').strip()
    if not host or not re.match(r'^[a-zA-Z0-9.\-:]+$', host):
        return None
    return host

def parse_mtr_hubs(hubs_raw):
    hubs = []
    prev_avg = 0
    for hub in hubs_raw:
        host_str = hub.get('host', '???')
        m = re.match(r'^(.+?)\s+\((.+)\)$', host_str)
        if m:
            hostname, ip = m.group(1), m.group(2)
        else:
            hostname, ip = host_str, host_str
        loss = hub.get('Loss%', 0)
        avg = hub.get('Avg', 0)
        if loss == 0:
            loss_class = 'good'
        elif loss <= 5:
            loss_class = 'warn'
        elif loss <= 20:
            loss_class = 'degraded'
        else:
            loss_class = 'critical'
        delta = avg - prev_avg
        spike = (delta > 20 or (prev_avg > 0 and avg > prev_avg * 3)) and hub.get('count', 0) > 1
        prev_avg = avg if avg > 0 else prev_avg
        mpls_info = hub.get('MPLS') or hub.get('Mplss')
        hubs.append({
            'hop': hub.get('count', 0),
            'hostname': hostname, 'ip': ip,
            'asn': hub.get('ASN', ''),
            'loss': loss, 'loss_class': loss_class,
            'snt': hub.get('Snt', 0),
            'last': hub.get('Last', 0), 'avg': avg,
            'best': hub.get('Best', 0), 'wrst': hub.get('Wrst', 0),
            'stdev': hub.get('StDev', 0),
            'spike': spike, 'mpls': mpls_info
        })
    return hubs

def parse_ping_summary(output):
    stats = {}
    m = re.search(r'(\d+) packets transmitted, (\d+) received.*?(\d+(?:\.\d+)?)% packet loss', output)
    if m:
        stats['packets_sent'] = int(m.group(1))
        stats['packets_received'] = int(m.group(2))
        stats['loss_percent'] = float(m.group(3))
    m2 = re.search(r'rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)', output)
    if m2:
        stats['rtt_min'] = float(m2.group(1))
        stats['rtt_avg'] = float(m2.group(2))
        stats['rtt_max'] = float(m2.group(3))
        stats['rtt_mdev'] = float(m2.group(4))
    return stats

# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================
def get_current_ip(interface='eth0'):
    try:
        result = subprocess.run(['ip', '-4', 'addr', 'show', interface],
                                capture_output=True, text=True, timeout=5)
        match = re.search(r'inet (\d+\.\d+\.\d+\.\d+/\d+)', result.stdout)
        return match.group(1) if match else '--'
    except Exception:
        return '--'

def get_interface_status(interface='eth0'):
    try:
        result = subprocess.run(['ip', 'link', 'show', interface],
                                capture_output=True, text=True, timeout=5)
        return 'UP' if 'state UP' in result.stdout else 'DOWN'
    except Exception:
        return 'UNKNOWN'

def get_link_speed(interface='eth0'):
    try:
        result = subprocess.run(['ethtool', interface],
                                capture_output=True, text=True, timeout=5)
        match = re.search(r'Speed: (\S+)', result.stdout)
        return match.group(1) if match else 'N/A'
    except Exception:
        return 'N/A'

def save_result(test_type, data, test_name=''):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    if test_name:
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', test_name)
        filename = f"{safe_name}_{test_type}_{timestamp}.json"
    else:
        filename = f"{test_type}_{timestamp}.json"
    filepath = os.path.join(RESULTS_DIR, filename)
    data['timestamp'] = datetime.now().isoformat()
    data['test_type'] = test_type
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    return filename

def load_results():
    results = []
    if not os.path.exists(RESULTS_DIR):
        return results
    json_files = [f for f in os.listdir(RESULTS_DIR) if f.endswith('.json')]
    for filename in sorted(json_files, reverse=True)[:200]:
        filepath = os.path.join(RESULTS_DIR, filename)
        try:
            with open(filepath, 'r') as f:
                results.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    return results

# =============================================================================
# ROUTES PAGES
# =============================================================================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/speedtest')
def speedtest():
    return render_template('speedtest.html')

@app.route('/network')
def network():
    return render_template('network.html')

@app.route('/diagnostic')
def diagnostic():
    return render_template('diagnostic.html')

@app.route('/history')
def history():
    return render_template('history.html')

# =============================================================================
# API REST
# =============================================================================
def get_mac_address(interface='eth0'):
    try:
        result = subprocess.run(['ip', 'link', 'show', interface],
                                capture_output=True, text=True, timeout=5)
        match = re.search(r'link/ether ([0-9a-f:]+)', result.stdout)
        return match.group(1) if match else 'N/A'
    except Exception:
        return 'N/A'

def get_default_gateway():
    try:
        result = subprocess.run(['ip', 'route', 'show', 'default'],
                                capture_output=True, text=True, timeout=5)
        match = re.search(r'default via (\S+)', result.stdout)
        return match.group(1) if match else '--'
    except Exception:
        return '--'

def get_dns_servers():
    try:
        with open('/etc/resolv.conf', 'r') as f:
            servers = re.findall(r'nameserver\s+(\S+)', f.read())
        return ', '.join(servers) if servers else '--'
    except Exception:
        return '--'

PUBLIC_SERVERS_FILE = os.path.join(CONFIG_DIR, 'public_servers.json')

def _clean_html(text):
    """Remove HTML tags and clean whitespace."""
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', text)).strip()

def parse_iperf_servers(html):
    """Parse iperf.fr/iperf-servers.php HTML table."""
    servers = []
    tables = re.findall(r'<table[^>]*>(.*?)</table>', html, re.DOTALL)
    if not tables:
        return servers
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tables[0], re.DOTALL)
    current_region = ''
    for row in rows:
        cells_td = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if not cells_td:
            text = re.sub(r'<[^>]+>', '', row).strip()
            if text and 'iPerf3 server' not in text:
                current_region = text
            continue
        if len(cells_td) < 7:
            continue
        speed = _clean_html(cells_td[4])
        datacenter = _clean_html(cells_td[2])
        port_raw = _clean_html(cells_td[6])
        ip_version = _clean_html(cells_td[7]) if len(cells_td) > 7 else ''
        port_match = re.search(r'(\d+)', port_raw)
        port = int(port_match.group(1)) if port_match else 5201
        # Split by <br> to handle multi-server rows (e.g. bytel)
        host_parts = re.split(r'<br\s*/?>', cells_td[0])
        loc_parts = re.split(r'<br\s*/?>', cells_td[1])
        for idx, hp in enumerate(host_parts):
            hostname = _clean_html(hp)
            if not hostname or '.' not in hostname:
                continue
            if current_region in ('Africa', 'Oceania'):
                continue
            loc = _clean_html(loc_parts[idx]) if idx < len(loc_parts) else _clean_html(loc_parts[-1])
            servers.append({
                'hostname': hostname,
                'port': port,
                'location': loc,
                'region': current_region,
                'datacenter': datacenter,
                'speed': speed,
                'ip_version': ip_version
            })
    return servers

@app.route('/api/public-servers/update', methods=['POST'])
def update_public_servers():
    """Fetch and parse iperf3 public server list from iperf.fr."""
    # Step 1: Check internet connectivity
    try:
        socket.create_connection(('8.8.8.8', 53), timeout=3)
    except OSError:
        return jsonify(success=False, message_key='srv.no_internet')
    # Step 2: Check DNS resolution
    try:
        socket.getaddrinfo('iperf.fr', 443, socket.AF_INET, socket.SOCK_STREAM)
    except socket.gaierror:
        return jsonify(success=False, message_key='srv.dns_failed')
    # Step 3: Fetch and parse
    try:
        resp = http_requests.get('https://iperf.fr/iperf-servers.php', timeout=15)
        resp.raise_for_status()
    except Exception as e:
        return jsonify(success=False, message_key='srv.http_error', detail=str(e))
    servers = parse_iperf_servers(resp.text)
    if not servers:
        return jsonify(success=False, message_key='srv.no_servers_found')
    data = {
        'updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'source': 'https://iperf.fr/iperf-servers.php',
        'servers': servers
    }
    with open(PUBLIC_SERVERS_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    return jsonify(success=True, message=str(len(servers)) + ' serveurs importes', count=len(servers))

@app.route('/api/public-servers')
def get_public_servers():
    """Return cached public server list."""
    if not os.path.exists(PUBLIC_SERVERS_FILE):
        return jsonify(servers=[], updated=None)
    try:
        with open(PUBLIC_SERVERS_FILE) as f:
            data = json.load(f)
        return jsonify(data)
    except Exception:
        return jsonify(servers=[], updated=None)

@app.route('/api/reboot', methods=['POST'])
def api_reboot():
    action = request.json.get('action', 'service') if request.json else 'service'
    try:
        if action == 'system':
            subprocess.Popen(['sudo', 'reboot'])
            return jsonify(success=True, message='Redemarrage systeme en cours...')
        else:
            subprocess.Popen(['sudo', 'systemctl', 'restart', 'speedbox'])
            return jsonify(success=True, message='Redemarrage du service en cours...')
    except Exception as e:
        return jsonify(success=False, message=str(e))

@app.route('/api/status')
def api_status():
    eth0_ip = get_current_ip('eth0')
    ip_only = eth0_ip.split('/')[0] if '/' in eth0_ip else eth0_ip
    mask = eth0_ip.split('/')[1] if '/' in eth0_ip else 'N/A'
    wlan0_ip = get_current_ip('wlan0')
    return jsonify({
        'eth0': {
            'status': get_interface_status('eth0'),
            'ip': ip_only,
            'mask': '/' + mask if mask != 'N/A' else 'N/A',
            'mac': get_mac_address('eth0'),
            'speed': get_link_speed('eth0')
        },
        'wlan0': {
            'status': get_interface_status('wlan0'),
            'ip': wlan0_ip.split('/')[0] if '/' in wlan0_ip else wlan0_ip,
            'mac': get_mac_address('wlan0')
        },
        'gateway': get_default_gateway(),
        'dns': get_dns_servers(),
        'hostname': subprocess.getoutput('hostname'),
        'uptime': subprocess.getoutput('uptime -p')
    })

INTERFACES_FILE = '/etc/network/interfaces'

def cidr_to_netmask(cidr):
    bits = int(cidr)
    mask = (0xffffffff >> (32 - bits)) << (32 - bits)
    return f"{(mask >> 24) & 0xff}.{(mask >> 16) & 0xff}.{(mask >> 8) & 0xff}.{mask & 0xff}"

def netmask_to_cidr(netmask):
    try:
        return sum(bin(int(x)).count('1') for x in netmask.split('.'))
    except Exception:
        return 24

def parse_eth0_config():
    """Parse /etc/network/interfaces pour extraire la config eth0."""
    config = {'mode': 'dhcp', 'ip': '', 'mask': '24', 'gateway': '', 'dns': ''}
    try:
        with open(INTERFACES_FILE, 'r') as f:
            content = f.read()
        # Trouver le bloc eth0
        match = re.search(r'iface\s+eth0\s+inet\s+(\w+)(.*?)(?=\niface\s|\n#\s*WiFi|\n#\s*wifi|\Z)',
                          content, re.DOTALL)
        if not match:
            return config
        config['mode'] = match.group(1)  # 'static' ou 'dhcp'
        block = match.group(2)
        # Extraire les parametres
        addr = re.search(r'address\s+(\S+)', block)
        if addr:
            config['ip'] = addr.group(1)
        nm = re.search(r'netmask\s+(\S+)', block)
        if nm:
            config['mask'] = str(netmask_to_cidr(nm.group(1)))
        gw = re.search(r'gateway\s+(\S+)', block)
        if gw:
            config['gateway'] = gw.group(1)
        dns_match = re.search(r'dns-nameservers\s+(.+)', block)
        if dns_match:
            config['dns'] = dns_match.group(1).strip()
    except Exception:
        pass
    return config

def write_eth0_config(mode, ip='', mask='24', gateway='', dns=''):
    """Reecrit le bloc eth0 dans /etc/network/interfaces en preservant le reste."""
    shutil.copy2(INTERFACES_FILE, INTERFACES_FILE + '.bak')
    with open(INTERFACES_FILE, 'r') as f:
        content = f.read()
    # Construire le nouveau bloc eth0
    if mode == 'dhcp':
        new_block = "allow-hotplug eth0\niface eth0 inet dhcp\n"
    else:
        netmask = cidr_to_netmask(mask)
        new_block = f"allow-hotplug eth0\niface eth0 inet static\naddress {ip}\nnetmask {netmask}\n"
        if gateway:
            new_block += f"gateway {gateway}\n"
        if dns:
            new_block += f"dns-nameservers {dns}\n"
    # Remplacer le bloc eth0 existant
    new_content = re.sub(
        r'allow-hotplug eth0\niface eth0 inet \w+[^\n]*\n(?:(?:address|netmask|gateway|dns-nameservers)\s+[^\n]+\n)*',
        new_block, content)
    with open(INTERFACES_FILE, 'w') as f:
        f.write(new_content)

@app.route('/api/network/config')
def api_network_config():
    """Retourne la configuration actuelle de eth0."""
    config = parse_eth0_config()
    return jsonify(config)

@app.route('/api/network/apply', methods=['POST'])
def api_network_apply():
    data = request.json
    mode = data.get('mode', 'dhcp')
    interface = 'eth0'
    try:
        if mode == 'dhcp':
            # Persister dans /etc/network/interfaces
            write_eth0_config('dhcp')
            # Appliquer immediatement
            subprocess.run(['ip', 'addr', 'flush', 'dev', interface],
                           capture_output=True, text=True)
            subprocess.run(['ifdown', interface],
                           capture_output=True, text=True, timeout=10)
            subprocess.run(['ifup', interface],
                           capture_output=True, text=True, timeout=30)
            return jsonify({'success': True, 'message_key': 'srv.dhcp_ok', 'message': 'DHCP enabled on ' + interface})
        else:
            ip = data.get('ip', '').strip()
            mask = data.get('mask', '24').strip()
            gateway = data.get('gateway', '').strip()
            dns = data.get('dns', '').strip()
            if not ip:
                return jsonify({'success': False, 'message_key': 'srv.ip_required'}), 400
            if not mask.isdigit() or not (1 <= int(mask) <= 32):
                return jsonify({'success': False, 'message_key': 'srv.cidr_invalid'}), 400
            if not re.match(r'^\d+\.\d+\.\d+\.\d+$', ip):
                return jsonify({'success': False, 'message_key': 'srv.ip_invalid'}), 400
            if gateway and not re.match(r'^\d+\.\d+\.\d+\.\d+$', gateway):
                return jsonify({'success': False, 'message_key': 'srv.gw_invalid'}), 400
            # Persister dans /etc/network/interfaces
            write_eth0_config('static', ip, mask, gateway, dns)
            # Appliquer immediatement
            subprocess.run(['ip', 'addr', 'flush', 'dev', interface],
                           capture_output=True, text=True)
            subprocess.run(['ip', 'addr', 'add', f'{ip}/{mask}', 'dev', interface],
                           capture_output=True, text=True, check=True)
            if gateway:
                subprocess.run(['ip', 'route', 'del', 'default'],
                               capture_output=True, text=True)
                subprocess.run(['ip', 'route', 'add', 'default', 'via', gateway, 'dev', interface],
                               capture_output=True, text=True, check=True)
            if dns:
                dns_servers = [s.strip() for s in dns.split(',') if re.match(r'^\d+\.\d+\.\d+\.\d+$', s.strip())]
                if dns_servers:
                    with open('/etc/resolv.conf', 'w') as f:
                        for s in dns_servers:
                            f.write(f'nameserver {s}\n')
            return jsonify({'success': True, 'message_key': 'srv.static_applied', 'message': f'{interface}: {ip}/{mask}'})
    except subprocess.CalledProcessError as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/network/vlan', methods=['POST'])
def api_network_vlan():
    data = request.json
    interface = data.get('interface', 'eth0').strip()
    vlan_id = data.get('vlan_id', '').strip()
    ip = data.get('ip', '').strip()
    if not vlan_id or not vlan_id.isdigit() or not (1 <= int(vlan_id) <= 4094):
        return jsonify({'success': False, 'message_key': 'srv.vlan_invalid'}), 400
    if not re.match(r'^[a-zA-Z0-9]+$', interface):
        return jsonify({'success': False, 'message_key': 'srv.iface_invalid'}), 400
    vlan_if = f"{interface}.{vlan_id}"
    try:
        # Creer la sous-interface VLAN
        result = subprocess.run(['ip', 'link', 'add', 'link', interface,
                        'name', vlan_if, 'type', 'vlan', 'id', vlan_id],
                       capture_output=True, text=True)
        if result.returncode != 0 and 'File exists' not in result.stderr:
            raise Exception(result.stderr.strip() or 'VLAN creation error')
        subprocess.run(['ip', 'link', 'set', vlan_if, 'up'],
                       capture_output=True, text=True, check=True)
        # Assigner l'IP si fournie
        msg = f'VLAN {vlan_id} on {interface}'
        if ip:
            if '/' not in ip:
                ip += '/24'
            subprocess.run(['ip', 'addr', 'flush', 'dev', vlan_if],
                           capture_output=True, text=True)
            subprocess.run(['ip', 'addr', 'add', ip, 'dev', vlan_if],
                           capture_output=True, text=True, check=True)
            msg += f' IP {ip}'
        return jsonify({'success': True, 'message': msg})
    except subprocess.CalledProcessError as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/network/vlan/delete', methods=['POST'])
def api_network_vlan_delete():
    data = request.json
    interface = data.get('interface', 'eth0').strip()
    vlan_id = data.get('vlan_id', '').strip()
    if not vlan_id or not vlan_id.isdigit() or not (1 <= int(vlan_id) <= 4094):
        return jsonify({'success': False, 'message_key': 'srv.vlan_invalid'}), 400
    vlan_if = f"{interface}.{vlan_id}"
    try:
        result = subprocess.run(['ip', 'link', 'delete', vlan_if],
                       capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(result.stderr.strip() or f'{vlan_if} introuvable')
        return jsonify({'success': True, 'message_key': 'srv.vlan_deleted', 'message': f'VLAN {vlan_id} deleted'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/ping', methods=['POST'])
def api_ping():
    data = request.json
    target = data.get('target', '')
    count = data.get('count', 4)
    if not target:
        return jsonify({'success': False, 'message_key': 'srv.target_required'}), 400
    try:
        result = subprocess.run(
            ['ping', '-c', str(count), '-W', '2', target],
            capture_output=True, text=True, timeout=30
        )
        return jsonify({
            'success': result.returncode == 0,
            'output': result.stdout,
            'error': result.stderr
        })
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message_key': 'srv.timeout'}), 504

@app.route('/api/traceroute', methods=['POST'])
def api_traceroute():
    data = request.json
    target = data.get('target', '')
    if not target:
        return jsonify({'success': False, 'message_key': 'srv.target_required'}), 400
    try:
        result = subprocess.run(
            ['traceroute', '-m', '15', '-w', '2', target],
            capture_output=True, text=True, timeout=60
        )
        return jsonify({'success': True, 'output': result.stdout})
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message_key': 'srv.timeout'}), 504

@app.route('/api/dns', methods=['POST'])
def api_dns():
    data = request.json
    target = data.get('target', '')
    dns_server = data.get('dns_server', '')
    if not target:
        return jsonify({'success': False, 'message_key': 'srv.target_required'}), 400
    cmd = ['nslookup', target]
    if dns_server:
        cmd.append(dns_server)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return jsonify({'success': result.returncode == 0, 'output': result.stdout + result.stderr})
    except Exception:
        return jsonify({'success': False, 'message_key': 'srv.dns_error'}), 500

@app.route('/api/history')
def api_history():
    return jsonify(load_results())

@app.route('/api/history/clear', methods=['POST'])
def api_clear_history():
    for f in os.listdir(RESULTS_DIR):
        if f.endswith('.json'):
            os.remove(os.path.join(RESULTS_DIR, f))
    return jsonify({'success': True})

# =============================================================================
# WEBSOCKET - IPERF3
# =============================================================================
@socketio.on('start_iperf3')
def handle_iperf3(data):
    server = data.get('server', '')
    port = data.get('port', 5201)
    duration = data.get('duration', 10)
    direction = data.get('direction', 'download')
    bandwidth = data.get('bandwidth', '0')
    threads = int(data.get('threads', '1'))
    protocol = data.get('protocol', 'tcp')
    test_name = data.get('test_name', '').strip()

    if not server:
        emit('iperf3_error', {'message_key': 'srv.server_required'})
        return

    if bandwidth and bandwidth != '0' and bandwidth[-1].isdigit():
        bandwidth = bandwidth + 'M'

    cmd = ['iperf3', '-c', server, '-p', str(port), '-t', str(duration), '-J', '--forceflush']

    if direction == 'download':
        cmd.append('-R')
    if bandwidth and bandwidth != '0' and protocol == 'tcp':
        cmd.extend(['-b', bandwidth])
    if protocol == 'udp':
        cmd.extend(['-u', '-b', bandwidth if bandwidth != '0' else '0'])
    if threads > 1:
        cmd.extend(['-P', str(threads)])

    emit('iperf3_started', {'message_key': 'srv.test_started', 'message': f'Test {direction} {protocol} > {server}...'})

    session_id = request.sid
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        iperf3_processes[session_id] = process
        stdout, stderr = process.communicate(timeout=int(duration) + 30)

        # Parser le JSON (peut contenir l'erreur meme avec returncode != 0)
        err_msg = stderr.strip()
        try:
            iperf_data = json.loads(stdout)
        except json.JSONDecodeError:
            emit('iperf3_error', {'message': err_msg or 'iperf3: invalid JSON output'})
            return

        if iperf_data.get('error'):
            emit('iperf3_error', {'message': iperf_data['error']})
            return

        if process.returncode != 0:
            emit('iperf3_error', {'message': err_msg or 'iperf3 error'})
            return

        intervals = iperf_data.get('intervals', [])

        for interval in intervals:
            streams = interval.get('streams', [{}])
            summary = interval.get('sum', streams[0] if streams else {})
            interval_data = {
                'seconds': round(summary.get('end', 0), 1),
                'mbps': round(summary.get('bits_per_second', 0) / 1000000, 2),
                'bytes': summary.get('bytes', 0),
                'retransmits': summary.get('retransmits', 0)
            }
            if protocol == 'udp':
                interval_data['jitter_ms'] = round(summary.get('jitter_ms', 0), 3)
                interval_data['lost_packets'] = summary.get('lost_packets', 0)
                interval_data['packets'] = summary.get('packets', 0)
                lost = summary.get('lost_packets', 0)
                total = summary.get('packets', 1)
                interval_data['lost_percent'] = round((lost / max(total, 1)) * 100, 3)
            emit('iperf3_interval', interval_data)
            socketio.sleep(0.05)

        end_data = iperf_data.get('end', {})
        sent = end_data.get('sum_sent', {})
        received = end_data.get('sum_received', {})

        if protocol == 'udp':
            udp_sum = end_data.get('sum', {})
            result = {
                'server': server, 'port': port, 'duration': duration,
                'direction': direction, 'protocol': protocol,
                'sent_mbps': round(udp_sum.get('bits_per_second', 0) / 1000000, 2),
                'received_mbps': round(udp_sum.get('bits_per_second', 0) / 1000000, 2),
                'sent_bytes': udp_sum.get('bytes', 0),
                'received_bytes': udp_sum.get('bytes', 0),
                'retransmits': 0,
                'jitter_ms': round(udp_sum.get('jitter_ms', 0), 3),
                'lost_packets': udp_sum.get('lost_packets', 0),
                'total_packets': udp_sum.get('packets', 0),
                'lost_percent': round((udp_sum.get('lost_packets', 0) / max(udp_sum.get('packets', 1), 1)) * 100, 3)
            }
        else:
            result = {
                'server': server, 'port': port, 'duration': duration,
                'direction': direction, 'protocol': protocol,
                'sent_mbps': round(sent.get('bits_per_second', 0) / 1000000, 2),
                'received_mbps': round(received.get('bits_per_second', 0) / 1000000, 2),
                'sent_bytes': sent.get('bytes', 0),
                'received_bytes': received.get('bytes', 0),
                'retransmits': sent.get('retransmits', 0)
            }

        result['test_name'] = test_name
        save_result('iperf3', result, test_name=test_name)
        emit('iperf3_complete', {'data': result})

    except subprocess.TimeoutExpired:
        process.kill()
        emit('iperf3_error', {'message_key': 'srv.test_timeout'})
    except Exception as e:
        emit('iperf3_error', {'message': str(e)})
    finally:
        proc = iperf3_processes.pop(session_id, None)
        if proc and proc.poll() is None:
            proc.kill()

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

# =============================================================================
# WEBSOCKET - DIAGNOSTIC (Ping, MTR, DNS)
# =============================================================================
@socketio.on('run_ping')
def handle_ping(data):
    host = validate_target(data.get('host', ''))
    if not host:
        emit('diag_error', {'message_key': 'srv.invalid_target'})
        return
    count = max(1, min(50, int(data.get('count', 4))))

    try:
        process = subprocess.Popen(
            ['ping', '-c', str(count), '-W', '2', host],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1
        )
        diag_processes[request.sid] = process
        full_output = ''
        while True:
            line = process.stdout.readline()
            if not line:
                break
            full_output += line
            emit('ping_output', {'line': line.rstrip()})
            socketio.sleep(0.01)
        process.wait()
        # Sauvegarder le resultat
        stats = parse_ping_summary(full_output)
        if stats:
            stats['target'] = host
            stats['count'] = count
            save_result('ping', stats)
        emit('ping_complete', {})
    except Exception as e:
        emit('diag_error', {'message': str(e)})
    finally:
        proc = diag_processes.pop(request.sid, None)
        if proc and proc.poll() is None:
            proc.kill()

@socketio.on('run_mtr')
def handle_mtr(data):
    host = validate_target(data.get('host', ''))
    if not host:
        emit('diag_error', {'message_key': 'srv.invalid_target'})
        return
    cycles = max(1, min(100, int(data.get('cycles', 10))))
    maxhops = max(5, min(50, int(data.get('maxhops', 20))))

    emit('mtr_started', {'message': f'MTR > {host} ({cycles} cycles, max {maxhops} hops)...'})

    try:
        process = subprocess.Popen(
            ['mtr', '-j', '-z', '-e', '-b', '-c', str(cycles), '-m', str(maxhops), host],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        diag_processes[request.sid] = process
        # Boucle de progression
        elapsed = 0
        while process.poll() is None:
            elapsed += 1
            cycle = min(elapsed, cycles)
            emit('mtr_progress', {'cycle': cycle, 'total': cycles})
            socketio.sleep(1)
        stdout = process.stdout.read()
        stderr = process.stderr.read()

        if process.returncode != 0:
            emit('diag_error', {'message': stderr or 'MTR error'})
            return

        mtr_data = json.loads(stdout)
        report = mtr_data.get('report', {})
        meta = report.get('mtr', {})
        hubs = parse_mtr_hubs(report.get('hubs', []))

        result_data = {
            'src': meta.get('src', ''),
            'dst': meta.get('dst', ''),
            'cycles': meta.get('tests', cycles),
            'hubs': hubs
        }
        emit('mtr_result', result_data)
        save_result('mtr', result_data)
    except subprocess.TimeoutExpired:
        process.kill()
        emit('diag_error', {'message_key': 'srv.mtr_timeout'})
    except json.JSONDecodeError:
        emit('diag_error', {'message_key': 'srv.mtr_parse_error'})
    except Exception as e:
        emit('diag_error', {'message': str(e)})
    finally:
        proc = diag_processes.pop(request.sid, None)
        if proc and proc.poll() is None:
            proc.kill()

@socketio.on('run_dns')
def handle_dns(data):
    host = validate_target(data.get('host', ''))
    if not host:
        emit('diag_error', {'message_key': 'srv.invalid_target'})
        return
    server = validate_target(data.get('server', ''))
    cmd = ['nslookup', host]
    if server:
        cmd.append(server)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        emit('dns_result', {'output': result.stdout + result.stderr})
    except subprocess.TimeoutExpired:
        emit('diag_error', {'message_key': 'srv.dns_timeout'})
    except Exception as e:
        emit('diag_error', {'message': str(e)})

@socketio.on('stop_diagnostic')
def handle_stop_diagnostic():
    proc = diag_processes.pop(request.sid, None)
    if proc:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            proc.kill()
    emit('diag_stopped', {'message_key': 'srv.stopped_by_user'})

# === Captive Portal Detection ===
@app.route("/generate_204")
@app.route("/gen_204")
@app.route("/hotspot-detect.html")
@app.route("/canonical.html")
@app.route("/connecttest.txt")
@app.route("/redirect")
@app.route("/success.txt")
@app.route("/ncsi.txt")
def captive_redirect():
    return render_template("index.html"), 200

# === Gestion serveurs iperf3 enregistres ===
SERVERS_FILE = os.path.join(os.path.dirname(__file__), 'servers.json')

def load_servers():
    try:
        with open(SERVERS_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return []

def save_servers(servers):
    with open(SERVERS_FILE, 'w') as f:
        json.dump(servers, f, indent=2)

@app.route('/api/servers', methods=['GET'])
def get_servers():
    return jsonify(load_servers())

@app.route('/api/servers', methods=['POST'])
def add_server():
    data = request.get_json()
    name = data.get('name', '').strip()
    host = data.get('host', '').strip()
    port = data.get('port', 5201)
    if not name or not host:
        return jsonify({'error': 'Name and host required', 'message_key': 'srv.server_required'}), 400
    servers = load_servers()
    for s in servers:
        if s['host'] == host and s['port'] == port:
            return jsonify({'error': 'Server already registered', 'message_key': 'srv.already_registered'}), 409
    servers.append({'name': name, 'host': host, 'port': int(port)})
    save_servers(servers)
    return jsonify({'success': True})

@app.route('/api/servers/<int:index>', methods=['DELETE'])
def delete_server(index):
    servers = load_servers()
    if 0 <= index < len(servers):
        servers.pop(index)
        save_servers(servers)
        return jsonify({'success': True})
    return jsonify({'error': 'Invalid index', 'message_key': 'srv.invalid_index'}), 404


# =============================================================================
# FTP / SFTP
# =============================================================================
FTP_CONFIG_FILE = os.path.join(CONFIG_DIR, 'ftp_config.json')


@app.route('/api/servers/<int:index>/favorite', methods=['POST'])
def toggle_favorite(index):
    servers = load_servers()
    if 0 <= index < len(servers):
        servers[index]['favorite'] = not servers[index].get('favorite', False)
        save_servers(servers)
        return jsonify(success=True, favorite=servers[index]['favorite'])
    return jsonify(success=False), 404


@app.route('/api/ftp/config', methods=['GET', 'POST'])
def ftp_config():
    if request.method == 'POST':
        data = request.json
        raw_pass = data.get('password', '') if data.get('save_password', True) else ''
        save_data = {
            'protocol': data.get('protocol', 'ftp'),
            'host': data.get('host', ''),
            'port': data.get('port', 21),
            'username': data.get('username', ''),
            'password_enc': _fernet.encrypt(raw_pass.encode()).decode() if raw_pass else '',
            'remote_path': data.get('remote_path', '/'),
            'tls': data.get('tls', False),
            'save_password': data.get('save_password', True)
        }
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(FTP_CONFIG_FILE, 'w') as f:
            json.dump(save_data, f, indent=2)
        os.chmod(FTP_CONFIG_FILE, 0o600)
        return jsonify({'success': True})
    else:
        if os.path.exists(FTP_CONFIG_FILE):
            with open(FTP_CONFIG_FILE, 'r') as f:
                cfg = json.load(f)
            # Decoder le mot de passe pour le renvoyer au frontend
            if 'password_enc' in cfg:
                cfg['password'] = _fernet.decrypt(cfg['password_enc'].encode()).decode() if cfg['password_enc'] else ''
                del cfg['password_enc']
            elif 'password_b64' in cfg:
                # Migration: anciens mots de passe en base64
                cfg['password'] = base64.b64decode(cfg['password_b64']).decode()
                del cfg['password_b64']
            return jsonify(cfg)
        return jsonify({})

@app.route('/api/ftp/test', methods=['POST'])
def ftp_test():
    data = request.json
    proto = data.get('protocol', 'ftp')
    host = data.get('host', '')
    port = int(data.get('port', 21 if proto == 'ftp' else 22))
    user = data.get('username', '')
    passwd = data.get('password', '')
    remote = data.get('remote_path') or data.get('remote', '/')
    tls = data.get('tls', False)

    if not host or not user:
        return jsonify({'success': False, 'message_key': 'srv.ftp_server_user_required'})

    try:
        if proto in ('sftp', 'scp'):
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.WarningPolicy())
            client.connect(host, port=port, username=user, password=passwd, timeout=10, banner_timeout=10, auth_timeout=10)
            sftp = client.open_sftp()
            try:
                listing = sftp.listdir(remote)
            except Exception:
                listing = []
            sftp.close()
            client.close()
            return jsonify({'success': True, 'message_key': 'srv.sftp_ok', 'message': 'SFTP OK', 'listing': listing[:50]})
        else:
            if tls:
                ftp = ftplib.FTP_TLS()
            else:
                ftp = ftplib.FTP()
            ftp.connect(host, port, timeout=10)
            ftp.login(user, passwd)
            if tls:
                ftp.prot_p()
            try:
                listing = ftp.nlst(remote)
            except Exception:
                listing = []
            ftp.quit()
            return jsonify({'success': True, 'message_key': 'srv.ftp_ok', 'message': 'FTP OK', 'listing': listing[:50]})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/ftp/send', methods=['POST'])
def ftp_send():
    data = request.json
    proto = data.get('protocol', 'ftp')
    host = data.get('host', '')
    port = int(data.get('port', 21 if proto == 'ftp' else 22))
    user = data.get('username', '')
    passwd = data.get('password', '')
    remote = data.get('remote_path') or data.get('remote', '/')
    tls = data.get('tls', False)
    source = data.get('file_source', 'all_results')
    filename = data.get('filename', '').strip()

    if not host or not user:
        return jsonify({'success': False, 'message_key': 'srv.ftp_server_user_required'})

    # Preparer le contenu
    try:
        result_files = sorted(
            [f for f in os.listdir(RESULTS_DIR) if f.endswith('.json')],
            key=lambda x: os.path.getmtime(os.path.join(RESULTS_DIR, x)),
            reverse=True
        )
    except Exception:
        result_files = []

    if not result_files:
        return jsonify({'success': False, 'message_key': 'srv.no_results'})

    if source == 'last_result':
        filepath = os.path.join(RESULTS_DIR, result_files[0])
        with open(filepath, 'r') as f:
            content_data = json.load(f)
    else:
        content_data = []
        for rf in result_files:
            try:
                with open(os.path.join(RESULTS_DIR, rf), 'r') as f:
                    content_data.append(json.load(f))
            except Exception:
                pass

    if not filename:
        hostname = socket.gethostname()
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'speedbox_{hostname}_{ts}.json'
    if not filename.endswith('.json'):
        filename += '.json'

    json_bytes = json.dumps(content_data, indent=2, ensure_ascii=False).encode('utf-8')
    file_obj = io.BytesIO(json_bytes)

    remote_file = remote.rstrip('/') + '/' + filename

    try:
        if proto in ('sftp', 'scp'):
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.WarningPolicy())
            client.connect(host, port=port, username=user, password=passwd, timeout=10, banner_timeout=10, auth_timeout=10)
            sftp = client.open_sftp()
            sftp.putfo(file_obj, remote_file)
            sftp.close()
            client.close()
        else:
            if tls:
                ftp = ftplib.FTP_TLS()
            else:
                ftp = ftplib.FTP()
            ftp.connect(host, port, timeout=10)
            ftp.login(user, passwd)
            if tls:
                ftp.prot_p()
            ftp.storbinary(f'STOR {remote_file}', file_obj)
            ftp.quit()

        nb = len(content_data) if isinstance(content_data, list) else 1
        size_kb = len(json_bytes) / 1024
        return jsonify({'success': True, 'message': f'{filename} ({size_kb:.1f} KB, {nb} result(s))'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Send error: {str(e)}'})


# =============================================================================
# DEMARRAGE
# =============================================================================

@socketio.on('start_quicktest')
def handle_quicktest(data):
    test_name = data.get('test_name', 'QuickTest')
    target_bitrate = float(data.get('target_bitrate', 100))
    quicktest_id = datetime.now().strftime('%Y%m%d_%H%M%S')

    servers = load_servers()
    fav_servers = [s for s in servers if s.get('favorite', False)]

    if not fav_servers:
        emit('quicktest_error', {'message_key': 'srv.no_favorites'})
        return

    # Limiter a 3 favoris max
    fav_servers = fav_servers[:3]

    # Construire la liste des etapes
    steps = []
    for srv in fav_servers:
        srv_name = srv.get('name', srv['host'])
        # Etape MTR avant les tests de debit
        steps.append({
            'type': 'mtr',
            'server': srv,
            'server_name': srv_name,
            'host': srv['host'],
            'cycles': 60,
            'maxhops': 20,
            'label': f'MTR - {srv_name}'
        })
        # Etape UDP au debit cible
        steps.append({
            'type': 'iperf3',
            'server': srv,
            'server_name': srv_name,
            'protocol': 'udp',
            'bitrate': str(int(target_bitrate)) + 'M',
            'duration': 60,
            'streams': 1,
            'label': f'UDP {int(target_bitrate)}M - {srv_name}'
        })
        # Etape TCP 1 stream
        steps.append({
            'type': 'iperf3',
            'server': srv,
            'server_name': srv_name,
            'protocol': 'tcp',
            'bitrate': '0',
            'duration': 60,
            'streams': 1,
            'label': f'TCP x1 - {srv_name}'
        })
        # Etape TCP 4 streams au debit/4
        divided = int(target_bitrate / 4)
        steps.append({
            'type': 'iperf3',
            'server': srv,
            'server_name': srv_name,
            'protocol': 'tcp',
            'bitrate': str(divided) + 'M',
            'duration': 60,
            'streams': 4,
            'label': f'TCP x4 @{divided}M - {srv_name}'
        })

    total_steps = len(steps)
    emit('quicktest_started', {'total_steps': total_steps, 'test_name': test_name})

    session_id = request.sid
    quicktest_stop_flags.discard(session_id)

    for step_idx, step in enumerate(steps):
        if session_id in quicktest_stop_flags:
            break
        step_num = step_idx + 1
        success = False
        attempts = 0
        max_attempts = 1 if step.get('type') == 'mtr' else 3

        while not success and attempts < max_attempts and session_id not in quicktest_stop_flags:
            attempts += 1
            emit('quicktest_step', {
                'step': step_num,
                'total': total_steps,
                'label': step['label'],
                'attempt': attempts,
                'status': 'running'
            })

            srv = step['server']
            host = srv['host']

            try:
                if step.get('type') == 'mtr':
                    # --- Etape MTR ---
                    mtr_cycles = step['cycles']
                    proc = subprocess.Popen(
                        ['mtr', '-j', '-z', '-e', '-b', '-c', str(mtr_cycles), '-m', str(step['maxhops']), host],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                    )
                    quicktest_processes[session_id] = proc
                    elapsed = 0
                    while proc.poll() is None:
                        elapsed += 1
                        cycle = min(elapsed, mtr_cycles)
                        socketio.emit('quicktest_countdown', {
                            'step': step_num, 'total': total_steps,
                            'remaining': f'Cycle {cycle}/{mtr_cycles}',
                            'duration': mtr_cycles,
                            'label': step['label']
                        }, room=session_id)
                        socketio.sleep(1)
                    stdout_mtr = proc.stdout.read()
                    stderr_mtr = proc.stderr.read()
                    quicktest_processes.pop(session_id, None)
                    if proc.returncode != 0:
                        raise Exception(stderr_mtr or 'MTR error')

                    mtr_data = json.loads(stdout_mtr)
                    report = mtr_data.get('report', {})
                    meta = report.get('mtr', {})
                    hubs = parse_mtr_hubs(report.get('hubs', []))
                    last_hub = hubs[-1] if hubs else {}

                    test_result = {
                        'type': 'mtr',
                        'server': host,
                        'server_name': step['server_name'],
                        'test_name': test_name,
                        'quicktest': True,
                        'quicktest_id': quicktest_id,
                        'step': step_num,
                        'total_steps': total_steps,
                        'label': step['label'],
                        'src': meta.get('src', ''),
                        'dst': meta.get('dst', ''),
                        'cycles': meta.get('tests', mtr_cycles),
                        'hops': len(hubs),
                        'last_hop_loss': last_hub.get('loss', 0),
                        'last_hop_avg': last_hub.get('avg', 0),
                        'hubs': hubs
                    }
                    save_result('mtr', test_result, test_name=test_name)

                    emit('quicktest_step', {
                        'step': step_num, 'total': total_steps,
                        'label': step['label'], 'attempt': attempts,
                        'status': 'done',
                        'result': test_result
                    })
                    success = True

                else:
                    # --- Etape iPerf3 ---
                    port = srv.get('port', 5201)
                    cmd = ['iperf3', '-c', host, '-p', str(port), '-t', str(step['duration']), '-J']

                    if step['protocol'] == 'udp':
                        cmd += ['-u', '-b', step['bitrate']]
                    else:
                        if step['streams'] > 1:
                            cmd += ['-P', str(step['streams'])]
                        if step['bitrate'] != '0':
                            cmd += ['-b', step['bitrate']]

                    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    quicktest_processes[session_id] = proc

                    duration = step['duration']
                    for sec in range(duration):
                        if proc.poll() is not None:
                            break
                        remaining = duration - sec
                        socketio.emit('quicktest_countdown', {
                            'step': step_num, 'total': total_steps,
                            'remaining': remaining,
                            'duration': duration,
                            'label': step['label']
                        }, room=session_id)
                        socketio.sleep(1)

                    proc.wait(timeout=30)
                    stdout_iperf = proc.stdout.read().decode()
                    stderr_iperf = proc.stderr.read().decode()
                    quicktest_processes.pop(session_id, None)

                    # Extraire erreur du JSON ou de stderr
                    err_msg = stderr_iperf.strip()
                    try:
                        result = json.loads(stdout_iperf)
                    except json.JSONDecodeError:
                        raise Exception(err_msg or 'iperf3: sortie JSON invalide')

                    if result.get('error'):
                        raise Exception(result['error'])
                    if proc.returncode != 0:
                        raise Exception(err_msg or 'iperf3 returned error')

                    end = result.get('end', {})

                    test_result = {
                        'type': 'iperf3',
                        'protocol': step['protocol'],
                        'duration': step['duration'],
                        'streams': step['streams'],
                        'server': host,
                        'port': port,
                        'server_name': step['server_name'],
                        'direction': 'upload',
                        'test_name': test_name,
                        'quicktest': True,
                        'quicktest_id': quicktest_id,
                        'step': step_num,
                        'total_steps': total_steps,
                        'label': step['label']
                    }

                    if step['protocol'] == 'udp':
                        ss = end.get('sum', {})
                        test_result['sent_mbps'] = round(ss.get('bits_per_second', 0) / 1e6, 2)
                        test_result['received_mbps'] = test_result['sent_mbps']
                        test_result['jitter_ms'] = round(ss.get('jitter_ms', 0), 3)
                        test_result['lost_percent'] = round(ss.get('lost_percent', 0), 3)
                        test_result['lost_packets'] = ss.get('lost_packets', 0)
                        test_result['total_packets'] = ss.get('packets', 0)
                        test_result['sent_bytes'] = ss.get('bytes', 0)
                        test_result['received_bytes'] = ss.get('bytes', 0)
                    else:
                        s_sent = end.get('sum_sent', {})
                        s_recv = end.get('sum_received', {})
                        test_result['sent_mbps'] = round(s_sent.get('bits_per_second', 0) / 1e6, 2)
                        test_result['received_mbps'] = round(s_recv.get('bits_per_second', 0) / 1e6, 2)
                        test_result['sent_bytes'] = s_sent.get('bytes', 0)
                        test_result['received_bytes'] = s_recv.get('bytes', 0)
                        test_result['retransmits'] = s_sent.get('retransmits', 0)

                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    test_result['timestamp'] = datetime.now().isoformat()
                    filename = f"iperf3_{step['protocol']}_{timestamp}_step{step_num}.json"
                    filepath = os.path.join(RESULTS_DIR, filename)
                    with open(filepath, 'w') as rf:
                        json.dump(test_result, rf, indent=2)

                    emit('quicktest_step', {
                        'step': step_num, 'total': total_steps,
                        'label': step['label'], 'attempt': attempts,
                        'status': 'done',
                        'result': test_result
                    })
                    success = True

            except Exception as e:
                emit('quicktest_step', {
                    'step': step_num,
                    'total': total_steps,
                    'label': step['label'],
                    'attempt': attempts,
                    'status': 'error',
                    'error': str(e)
                })
                if attempts < max_attempts and session_id not in quicktest_stop_flags:
                    for r in range(10, 0, -1):
                        if session_id in quicktest_stop_flags:
                            break
                        socketio.emit('quicktest_countdown', {
                            'step': step_num,
                            'total': total_steps,
                            'remaining': r,
                            'duration': 10,
                            'label': f'Retry pause - {step["label"]}'
                        }, room=session_id)
                        socketio.sleep(1)

        # Pause 10s entre les tests
        if step_idx < total_steps - 1 and session_id not in quicktest_stop_flags:
            for r in range(10, 0, -1):
                if session_id in quicktest_stop_flags:
                    break
                socketio.emit('quicktest_countdown', {
                    'step': step_num,
                    'total': total_steps,
                    'remaining': r,
                    'duration': 10,
                    'label': 'Pause entre tests'
                }, room=session_id)
                socketio.sleep(1)

    quicktest_stop_flags.discard(session_id)
    emit('quicktest_complete', {'test_name': test_name, 'total_steps': total_steps})


@socketio.on('stop_quicktest')
def handle_stop_quicktest():
    sid = request.sid
    quicktest_stop_flags.add(sid)
    proc = quicktest_processes.pop(sid, None)
    if proc:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            proc.kill()
    emit('quicktest_stopped', {})


if __name__ == '__main__':
    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(CONFIG_DIR, exist_ok=True)
    print("=" * 50)
    print("  SpeedBOX - http://0.0.0.0:5000")
    print("=" * 50)
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
