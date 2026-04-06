# Guide de personnalisation de SpeedBox

Ce document explique comment personnaliser SpeedBox : ajouter des langues, modifier le theme, ajouter des outils, changer l'interface reseau, desactiver des fonctionnalites, et executer sans root.

---

## 1. Ajouter une langue

SpeedBox utilise un systeme i18n cote client base sur un dictionnaire JavaScript. Ajouter une langue ne necessite aucune recompilation ni outil externe.

### Etape 1 : Ajouter le dictionnaire

Ouvrir `static/js/i18n.js` et ajouter un nouveau bloc dans l'objet `TRANSLATIONS`. Exemple pour l'allemand :

```javascript
const TRANSLATIONS = {
    fr: {
        'nav.home': 'Accueil',
        'nav.speedtest': 'Test de debit',
        // ...
    },
    en: {
        'nav.home': 'Home',
        'nav.speedtest': 'Speed Test',
        // ...
    },
    de: {
        'nav.home': 'Startseite',
        'nav.speedtest': 'Geschwindigkeitstest',
        'nav.diagnostic': 'Diagnose',
        'nav.network': 'Netzwerk',
        'nav.history': 'Verlauf',
        // ... toutes les ~250 cles doivent etre traduites
    }
};
```

**Important** : Toutes les cles presentes dans le bloc `fr` doivent etre reproduites dans le nouveau bloc. Les cles sont organisees par categorie :

| Prefixe | Section |
|---------|---------|
| `nav.*` | Barre de navigation |
| `index.*` | Page d'accueil / dashboard |
| `speedtest.*` | Page de test de debit |
| `qt.*` | QuickTest (modal et resultats) |
| `diag.*` | Page de diagnostic |
| `net.*` | Page reseau |
| `hist.*` | Page d'historique |
| `srv.*` | Gestion des serveurs |

### Etape 2 : Modifier toggleLang()

La fonction `toggleLang()` doit cycler entre toutes les langues disponibles :

```javascript
// Avant (2 langues)
function toggleLang() {
    setLang(getLang() === 'fr' ? 'en' : 'fr');
}

// Apres (3 langues)
function toggleLang() {
    const langs = ['fr', 'en', 'de'];
    const current = getLang();
    const index = langs.indexOf(current);
    const next = langs[(index + 1) % langs.length];
    setLang(next);
}
```

### Etape 3 : Mettre a jour getLocale()

Ajouter la nouvelle locale pour le formatage des dates et nombres :

```javascript
// Avant
function getLocale() {
    return getLang() === 'fr' ? 'fr-FR' : 'en-GB';
}

// Apres
function getLocale() {
    const locales = {
        'fr': 'fr-FR',
        'en': 'en-GB',
        'de': 'de-DE'
    };
    return locales[getLang()] || 'fr-FR';
}
```

### Etape 4 : Mettre a jour les boutons de langue

Dans `base.html`, le bouton de changement de langue affiche la prochaine langue. Adapter le texte affiche dans `applyTranslations()` ou dans le template si necessaire.

### Verification

1. Recharger la page dans le navigateur
2. Cliquer sur le bouton de langue pour cycler jusqu'a la nouvelle langue
3. Verifier que toutes les pages sont traduites
4. Les cles manquantes s'affichent en francais (fallback) ou comme cle brute

---

## 2. Changer le theme

Le theme de SpeedBox est defini dans `static/css/style.css`. Le theme par defaut est sombre avec un accent bleu cyan.

### Palette de couleurs actuelle

```css
/* Arriere-plans */
body             { background: #0a0e17; }  /* Fond principal, tres sombre */
.card, .navbar   { background: #131a2b; }  /* Cartes et barre de navigation */

/* Accent */
a, .active       { color: #00d4ff; }       /* Bleu cyan */
.btn-primary     { background: #00d4ff; }

/* Texte */
.text-primary    { color: #e0e0e0; }       /* Texte principal, gris clair */
.text-secondary  { color: #8899aa; }       /* Texte secondaire */
.label           { color: #77aacc; }       /* Labels de formulaire */

/* Semantique */
.success         { color: #00ff88; }       /* Vert */
.error           { color: #ff4466; }       /* Rouge */
.warning         { color: #ffdd57; }       /* Jaune */
```

### Creer un theme clair

Pour passer a un theme clair, inverser les couleurs de fond et de texte :

```css
/* Theme clair - remplacements principaux */
body {
    background: #f5f7fa;
    color: #1a1a2e;
}

.card, .navbar {
    background: #ffffff;
    border-color: #e0e0e0;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

/* Adapter l'accent pour un fond clair */
a, .active {
    color: #0095cc;  /* Version plus sombre du cyan */
}

/* Texte */
.text-primary { color: #1a1a2e; }
.text-secondary { color: #666680; }
.label { color: #336688; }

/* Terminal : conserver un fond sombre */
.terminal {
    background: #1e1e2e;
    color: #e0e0e0;
}
```

### Modifier la carte hero

La carte hero de la page d'accueil utilise un gradient :

```css
.hero-card {
    background: linear-gradient(135deg, #0a1628 0%, #1a2a4a 50%, #0a1628 100%);
    border: 1px solid #00d4ff33;
}
```

Pour un theme clair :

```css
.hero-card {
    background: linear-gradient(135deg, #e8f4fd 0%, #d0e8f7 50%, #e8f4fd 100%);
    border: 1px solid #0095cc33;
}
```

### Couleurs des toasts

Les toasts de notification ont leurs propres couleurs :

```css
.toast.success { background: #0a2a1a; border-left: 4px solid #00ff88; }
.toast.error   { background: #2a0a1a; border-left: 4px solid #ff4466; }
.toast.info    { background: #0a1a2a; border-left: 4px solid #00d4ff; }
```

Pour un theme clair :

```css
.toast.success { background: #e8f8ef; border-left: 4px solid #00cc66; }
.toast.error   { background: #fde8ec; border-left: 4px solid #cc3355; }
.toast.info    { background: #e8f0f8; border-left: 4px solid #0095cc; }
```

### Conseils

- Modifier un fichier CSS a la fois et recharger le navigateur pour voir les changements
- Utiliser les DevTools du navigateur (F12) pour tester les couleurs en direct
- Les graphiques Chart.js utilisent des couleurs definies dans le JavaScript des templates — les modifier dans les scripts des templates concernes

---

## 3. Ajouter un outil de diagnostic

Pour ajouter un nouvel outil de diagnostic (par exemple `whois`), suivre ce pattern en trois etapes.

### Etape A : Backend (app.py)

Ajouter un handler WebSocket dans `app.py` :

```python
@socketio.on('run_whois')
def handle_whois(data):
    """Executer une requete WHOIS sur un domaine."""
    target = data.get('target', '').strip()

    # Valider l'entree
    if not validate_target(target):
        emit('whois_error', {'error': 'Cible invalide'})
        return

    try:
        # Executer la commande
        proc = subprocess.Popen(
            ['whois', target],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        # Tracker le processus
        diag_processes[request.sid] = proc

        stdout, stderr = proc.communicate(timeout=30)

        if proc.returncode == 0:
            emit('whois_result', {
                'target': target,
                'output': stdout.decode('utf-8', errors='replace')
            })
        else:
            emit('whois_error', {
                'error': stderr.decode('utf-8', errors='replace')
            })

    except subprocess.TimeoutExpired:
        proc.kill()
        emit('whois_error', {'error': 'Timeout apres 30 secondes'})

    except Exception as e:
        emit('whois_error', {'error': str(e)})

    finally:
        # Toujours nettoyer
        diag_processes.pop(request.sid, None)
```

Ne pas oublier d'installer le paquet systeme si necessaire :

```bash
sudo apt install -y whois
```

### Etape B : Frontend (diagnostic.html)

Ajouter une section collapsible dans `templates/diagnostic.html` :

```html
<!-- Section WHOIS -->
<div class="card section-collapse">
    <div class="section-header" onclick="toggleSection('whois')">
        <h3 data-i18n="diag.whois">WHOIS</h3>
        <span class="collapse-icon" id="whois-icon">+</span>
    </div>
    <div class="section-body" id="whois-body" style="display:none;">
        <div class="form-group">
            <label data-i18n="diag.whois.target">Domaine</label>
            <input type="text" id="whois-target" class="form-input"
                   data-i18n-placeholder="diag.whois.placeholder"
                   placeholder="exemple.fr">
        </div>
        <button class="btn btn-primary" onclick="runWhois()"
                data-i18n="diag.whois.run">Lancer</button>
        <div class="terminal" id="whois-output" style="display:none;"></div>
    </div>
</div>
```

Ajouter le code JavaScript correspondant dans le bloc `<script>` :

```javascript
function runWhois() {
    const target = document.getElementById('whois-target').value.trim();
    if (!target) return;

    const output = document.getElementById('whois-output');
    output.style.display = 'block';
    output.textContent = t('diag.whois.running');

    socket.emit('run_whois', { target: target });
}

socket.on('whois_result', function(data) {
    const output = document.getElementById('whois-output');
    output.textContent = data.output;
});

socket.on('whois_error', function(data) {
    const output = document.getElementById('whois-output');
    output.textContent = t('diag.error') + ': ' + data.error;
    output.classList.add('error');
});
```

### Etape C : Traductions (i18n.js)

Ajouter les cles de traduction dans `static/js/i18n.js` :

```javascript
// Dans le bloc 'fr'
'diag.whois': 'WHOIS',
'diag.whois.target': 'Domaine ou IP',
'diag.whois.placeholder': 'exemple.fr',
'diag.whois.run': 'Rechercher',
'diag.whois.running': 'Recherche en cours...',

// Dans le bloc 'en'
'diag.whois': 'WHOIS',
'diag.whois.target': 'Domain or IP',
'diag.whois.placeholder': 'example.com',
'diag.whois.run': 'Lookup',
'diag.whois.running': 'Looking up...',
```

### Resume du pattern

Pour tout nouvel outil, la structure est identique :

1. **Backend** : handler `@socketio.on()` avec validation, subprocess, tracking, nettoyage
2. **Frontend** : section collapsible, formulaire, zone de resultat, code WebSocket
3. **i18n** : cles FR + EN pour chaque element de texte

---

## 4. Changer l'interface reseau par defaut

Par defaut, SpeedBox est configure pour utiliser `eth0` comme interface reseau principale. Pour utiliser une autre interface (par exemple `enp0s3` sur un PC, ou `end0` sur certains systemes ARM), les modifications suivantes sont necessaires.

### Fonctions a modifier dans app.py

Les fonctions suivantes contiennent des references a `eth0` :

| Fonction | Usage |
|----------|-------|
| `get_current_ip()` | Recupere l'adresse IP de l'interface |
| `get_interface_status(iface)` | Verifie si l'interface est UP/DOWN |
| `get_link_speed(iface)` | Lit la vitesse de liaison via ethtool |
| `get_mac_address(iface)` | Recupere l'adresse MAC |
| `parse_eth0_config()` | Parse /etc/network/interfaces pour eth0 |
| `write_eth0_config(config)` | Ecrit la configuration de eth0 |

### Option 1 : Remplacement direct

Rechercher et remplacer toutes les occurrences de `'eth0'` par le nom de votre interface :

```bash
cd /opt/speedbox
grep -n "eth0" app.py
```

Remplacer dans chaque occurrence. Attention : certaines references sont dans des appels `subprocess` (ex: `['ip', 'addr', 'show', 'eth0']`), d'autres dans des regex (ex: pour parser `/etc/network/interfaces`).

### Option 2 : Variable de configuration

Ajouter une constante en haut de `app.py` pour centraliser le nom de l'interface :

```python
# Configuration
PRIMARY_INTERFACE = 'eth0'  # Modifier selon votre systeme
```

Puis remplacer les references directes :

```python
# Avant
def get_current_ip():
    result = subprocess.run(['ip', 'addr', 'show', 'eth0'], ...)

# Apres
def get_current_ip():
    result = subprocess.run(['ip', 'addr', 'show', PRIMARY_INTERFACE], ...)
```

### Parsing de /etc/network/interfaces

La fonction `parse_eth0_config()` utilise un regex pour trouver le bloc de configuration de eth0 dans `/etc/network/interfaces`. Le regex ressemble a :

```python
pattern = r'(allow-hotplug|auto)\s+eth0\b.*?(?=\n(allow-hotplug|auto)\s|\Z)'
```

Si vous changez d'interface, adapter le regex :

```python
pattern = rf'(allow-hotplug|auto)\s+{PRIMARY_INTERFACE}\b.*?(?=\n(allow-hotplug|auto)\s|\Z)'
```

### Interface Wi-Fi (wlan0)

La page d'accueil affiche egalement le statut de `wlan0`. Si votre systeme utilise un autre nom pour le Wi-Fi (ex: `wlp2s0`), modifier les references correspondantes dans `app.py` et dans `templates/index.html`.

---

## 5. Desactiver des fonctionnalites

SpeedBox est modulaire : chaque fonctionnalite peut etre desactivee en supprimant les routes backend et les sections frontend correspondantes.

### Desactiver FTP/SFTP

**Backend** (`app.py`) : supprimer les routes suivantes :
- `@app.route('/api/ftp/config', methods=['GET'])`
- `@app.route('/api/ftp/config', methods=['POST'])`
- `@app.route('/api/ftp/test', methods=['POST'])`
- `@app.route('/api/ftp/send', methods=['POST'])`

**Frontend** (`templates/network.html`) : supprimer la section FTP/SFTP (formulaire de configuration, bouton test, bouton envoi).

**i18n** (`static/js/i18n.js`) : les cles `net.ftp.*` peuvent etre supprimees mais ce n'est pas obligatoire (les cles inutilisees n'ont pas d'impact).

### Desactiver la configuration reseau

**Backend** (`app.py`) : supprimer les routes :
- `@app.route('/api/network/config', methods=['GET'])`
- `@app.route('/api/network/apply', methods=['POST'])`
- `@app.route('/api/network/vlan', methods=['POST'])`
- `@app.route('/api/network/vlan/delete', methods=['POST'])`

**Frontend** (`templates/network.html`) : supprimer les sections de configuration IP et VLAN. Conserver uniquement l'affichage du statut des interfaces si souhaite.

> **Note** : Desactiver la configuration reseau est recommande si SpeedBox est utilise uniquement pour les tests de debit sans besoin d'administration reseau.

### Desactiver le QuickTest

**Backend** (`app.py`) : supprimer les handlers :
- `@socketio.on('start_quicktest')`
- `@socketio.on('stop_quicktest')`
- Les variables globales `quicktest_processes` et `quicktest_stop_flags`

**Frontend** (`templates/speedtest.html`) : supprimer le modal QuickTest et le bouton de lancement.

**Frontend** (`templates/index.html`) : supprimer la carte hero QuickTest ou la remplacer par un autre element.

### Desactiver le redemarrage

**Backend** (`app.py`) : supprimer la route :
- `@app.route('/api/reboot', methods=['POST'])`

**Frontend** (`templates/index.html`) : supprimer la section maintenance avec le bouton de redemarrage.

> **Important** : Desactiver le redemarrage est recommande dans les environnements multi-utilisateurs ou quand SpeedBox est accessible depuis un reseau non fiable.

---

## 6. Executer sans les droits root

SpeedBox s'execute par defaut en tant que root car plusieurs commandes systeme l'exigent. Il est possible de le configurer pour utiliser un utilisateur dedie avec des droits sudo cibles.

### Commandes necessitant root

| Commande | Usage | Necessaire ? |
|----------|-------|-------------|
| `ip addr show` | Lire la configuration IP | Non (lisible par tous) |
| `ip addr add/del` | Modifier la configuration IP | Oui |
| `ip addr flush` | Vider la configuration IP | Oui |
| `ip link set` | Activer/desactiver une interface | Oui |
| `ip route` | Modifier les routes | Oui |
| `ethtool` | Lire la vitesse de liaison | Oui |
| `ifup` / `ifdown` | Activer/desactiver une interface | Oui |
| `reboot` | Redemarrer le systeme | Oui |

> **Note** : `iperf3`, `mtr`, `ping`, `traceroute`, `nslookup` n'ont pas besoin de root.

### Etape 1 : Creer un utilisateur dedie

```bash
sudo useradd -r -s /bin/false -d /opt/speedbox speedbox
sudo chown -R speedbox:speedbox /opt/speedbox
```

### Etape 2 : Configurer sudo

Creer un fichier sudoers dedie :

```bash
sudo visudo -f /etc/sudoers.d/speedbox
```

Contenu :

```
speedbox ALL=(ALL) NOPASSWD: /sbin/ip
speedbox ALL=(ALL) NOPASSWD: /usr/sbin/ethtool
speedbox ALL=(ALL) NOPASSWD: /sbin/ifup
speedbox ALL=(ALL) NOPASSWD: /sbin/ifdown
speedbox ALL=(ALL) NOPASSWD: /sbin/reboot
```

> **Note** : Les chemins des commandes peuvent varier selon la distribution. Utiliser `which ip`, `which ethtool`, etc. pour verifier.

### Etape 3 : Modifier les appels subprocess dans app.py

Pour chaque commande necessitant root, ajouter `'sudo'` en debut de liste :

```python
# Avant
subprocess.run(['ip', 'addr', 'flush', 'dev', 'eth0'], ...)
subprocess.run(['ethtool', 'eth0'], ...)
subprocess.run(['reboot'], ...)

# Apres
subprocess.run(['sudo', 'ip', 'addr', 'flush', 'dev', 'eth0'], ...)
subprocess.run(['sudo', 'ethtool', 'eth0'], ...)
subprocess.run(['sudo', 'reboot'], ...)
```

Pour faciliter la maintenance, creer une fonction utilitaire :

```python
def run_privileged(cmd, **kwargs):
    """Execute une commande avec sudo si necessaire."""
    return subprocess.run(['sudo'] + cmd, **kwargs)
```

### Etape 4 : Modifier le service systemd

Dans `speedbox.service`, changer l'utilisateur :

```ini
[Service]
User=speedbox
Group=speedbox
```

### Etape 5 : Gerer les permissions des fichiers

L'utilisateur `speedbox` doit pouvoir ecrire dans les repertoires de donnees :

```bash
sudo chown -R speedbox:speedbox /opt/speedbox/config
sudo chown -R speedbox:speedbox /opt/speedbox/results
sudo chmod 700 /opt/speedbox/config
sudo chmod 700 /opt/speedbox/results
```

### Etape 6 : Redemarrer le service

```bash
sudo systemctl daemon-reload
sudo systemctl restart speedbox
```

### Verification

```bash
# Verifier que le service tourne sous l'utilisateur speedbox
ps aux | grep app.py

# Verifier les permissions
ls -la /opt/speedbox/config/
ls -la /opt/speedbox/results/
```

### Compromis

Executer sans root :
- **Avantage** : meilleure securite, principe du moindre privilege
- **Inconvenient** : configuration supplementaire, risque de permissions manquantes
- **Recommandation** : utiliser le mode root pour une installation personnelle sur un reseau de confiance, le mode utilisateur dedie pour un deploiement accessible depuis un reseau etendu
