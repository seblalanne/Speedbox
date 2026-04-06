# Reference des fichiers SpeedBox

Ce document decrit chaque fichier du projet SpeedBox, son role, et son contenu principal.

---

## Fichiers serveur

### app.py (~1389 lignes)

**Role** : Application principale Flask. Contient toute la logique serveur : routes HTTP, handlers WebSocket, fonctions utilitaires, gestion des processus.

#### Routes HTTP (GET/POST/DELETE)

| Route | Methode | Description |
|-------|---------|-------------|
| `/` | GET | Page d'accueil (dashboard) |
| `/speedtest` | GET | Page de test de debit |
| `/network` | GET | Page de configuration reseau |
| `/diagnostic` | GET | Page d'outils de diagnostic |
| `/history` | GET | Page d'historique des resultats |
| `/api/status` | GET | Statut systeme (IP, interfaces, uptime) |
| `/api/public-servers` | GET | Liste des serveurs publics iperf3 |
| `/api/public-servers/update` | POST | Rafraichir le cache des serveurs publics depuis iperf.fr |
| `/api/reboot` | POST | Redemarrer le systeme |
| `/api/network/config` | GET | Configuration reseau actuelle (eth0) |
| `/api/network/apply` | POST | Appliquer une nouvelle configuration IP |
| `/api/network/vlan` | POST | Creer un VLAN sur eth0 |
| `/api/network/vlan/delete` | POST | Supprimer un VLAN |
| `/api/ping` | GET | Lancer un ping simple (REST, non WebSocket) |
| `/api/traceroute` | GET | Lancer un traceroute |
| `/api/dns` | GET | Lancer une resolution DNS |
| `/api/history` | GET | Recuperer l'historique des resultats (JSON) |
| `/api/history/clear` | DELETE | Effacer l'historique par type |
| `/api/servers` | GET | Liste des serveurs iperf3 de l'utilisateur |
| `/api/servers` | POST | Ajouter un serveur iperf3 |
| `/api/servers/<index>` | DELETE | Supprimer un serveur par index |
| `/api/servers/<index>/favorite` | POST | Marquer un serveur comme favori |
| `/api/ftp/config` | GET | Recuperer la configuration FTP/SFTP |
| `/api/ftp/config` | POST | Sauvegarder la configuration FTP/SFTP |
| `/api/ftp/test` | POST | Tester la connexion FTP/SFTP |
| `/api/ftp/send` | POST | Envoyer un fichier de resultats via FTP/SFTP |
| Captive portal routes | GET | Detection de portail captif (generate_204, etc.) |

#### Handlers WebSocket

| Evenement | Description |
|-----------|-------------|
| `start_iperf3` | Demarrer un test de debit iperf3 |
| `stop_iperf3` | Arreter le test iperf3 en cours |
| `run_ping` | Lancer un ping avec resultats en temps reel |
| `run_mtr` | Lancer un MTR avec analyse par hop |
| `run_dns` | Lancer une resolution DNS (nslookup) |
| `stop_diagnostic` | Arreter le diagnostic en cours (ping/mtr/dns) |
| `start_quicktest` | Demarrer un QuickTest complet (sequence automatisee) |
| `stop_quicktest` | Arreter le QuickTest en cours |

#### Fonctions utilitaires

| Fonction | Lignes (approx.) | Description |
|----------|-------------------|-------------|
| `validate_target(target)` | ~10 | Valide un hostname/IP via regex |
| `parse_mtr_hubs(mtr_json)` | ~35 | Parse le JSON MTR, classifie perte et latence |
| `parse_ping_summary(output)` | ~15 | Extrait les stats d'un ping (min/avg/max/loss) |
| `get_current_ip()` | ~10 | Retourne l'IP actuelle de eth0 |
| `get_interface_status(iface)` | ~10 | Retourne UP/DOWN pour une interface |
| `get_link_speed(iface)` | ~10 | Retourne la vitesse de lien via ethtool |
| `save_result(type, data)` | ~10 | Sauvegarde un resultat en JSON dans results/ |
| `load_results(type, limit)` | ~20 | Charge les resultats depuis results/ |
| `parse_iperf_servers(html)` | ~20 | Parse la page HTML des serveurs publics iperf.fr |
| `parse_eth0_config()` | ~30 | Parse /etc/network/interfaces pour eth0 |
| `write_eth0_config(config)` | ~25 | Ecrit une nouvelle config eth0 |
| `cidr_to_netmask(cidr)` | ~5 | Convertit /24 en 255.255.255.0 |
| `netmask_to_cidr(netmask)` | ~5 | Convertit 255.255.255.0 en /24 |

---

## Templates HTML

### templates/base.html (~115 lignes)

**Role** : Template de base Jinja2 dont heritent toutes les pages.

**Contenu** :
- Structure HTML5 avec meta viewport responsive
- Chargement des CSS et JS (style.css, Chart.js, Socket.IO, i18n.js)
- Barre de navigation desktop avec liens vers les 5 pages principales
- Barre de navigation mobile (bottom bar) avec icones
- Conteneur de toasts (notifications)
- Horloge en temps reel dans la navbar
- Bootstrap i18n : appel a `applyTranslations()` au chargement
- Blocs Jinja2 : `{% block content %}`, `{% block scripts %}`

### templates/index.html (~155 lignes)

**Role** : Page d'accueil / dashboard.

**Contenu** :
- Carte hero QuickTest avec bouton de lancement rapide
- Cartes de statut des interfaces (eth0, wlan0) : IP, vitesse, etat
- Carte de statut systeme : uptime, charge, memoire
- Grille de liens vers les outils (speedtest, diagnostic, reseau, historique)
- Section maintenance avec bouton de redemarrage et confirmation

### templates/speedtest.html (~824 lignes)

**Role** : Page de test de debit iperf3, la plus complexe de l'application.

**Contenu** :
- **Gestion des serveurs** : liste des serveurs personnels, ajout (nom, hote, port), suppression, marquage favori (etoile)
- **Navigateur de serveurs publics** : chargement depuis le cache, filtrage, ajout rapide
- **Parametres de test** : direction (upload/download), protocole (TCP/UDP), debit cible (UDP), duree (1-300s), nombre de flux (1-32)
- **Zone de progression** : barre de progression, graphique Chart.js temps reel (debit par intervalle), statistiques en direct
- **Modal QuickTest** : progression multi-etapes, countdown, resultats par serveur
- **Connexion WebSocket** : emission de start_iperf3, reception de iperf3_interval et iperf3_complete

### templates/diagnostic.html (~293 lignes)

**Role** : Page d'outils de diagnostic reseau.

**Contenu** :
- **Section Ping** (collapsible) : champ cible, nombre de paquets, bouton start/stop, zone de sortie terminal avec resultats en direct
- **Section MTR** (collapsible) : champ cible, cycles, hops max, tableau d'analyse par hop (hostname, IP, perte, latence avg/best/worst, ASN), classification coloree des hops
- **Section DNS** (collapsible) : champ domaine, serveur DNS optionnel, zone de resultats
- Chaque section utilise des WebSockets pour les resultats en temps reel

### templates/network.html (~381 lignes)

**Role** : Page de configuration reseau et transfert de fichiers.

**Contenu** :
- **Statut des interfaces** : eth0 et wlan0 avec IP, masque, passerelle, MAC, vitesse, etat
- **Configuration IP** : bascule DHCP/statique, champs adresse/masque/passerelle/DNS, bouton appliquer
- **VLAN** : creation (ID 1-4094), suppression, liste des VLANs actifs
- **Configuration FTP/SFTP** : type (FTP/SFTP), hote, port, identifiants, repertoire distant, bouton test de connexion
- **Envoi de fichiers** : selection d'un resultat, envoi via FTP/SFTP

### templates/history.html (~720 lignes)

**Role** : Page d'historique et de tendances.

**Contenu** :
- **Barre d'onglets** : iperf3, MTR, ping, QuickTest
- **Graphique de tendances** : Chart.js avec courbe de debit (iperf3), latence (ping/MTR), ou synthese (QuickTest)
- **Tableau desktop** : colonnes triables selon le type (date, serveur, debit, protocole, perte, latence, etc.)
- **Cartes mobiles** : meme contenu dans un format empile pour les ecrans < 768px
- **Bouton effacer** : suppression de l'historique du type selectionne avec confirmation
- **Logique de chargement** : appel REST a `/api/history?type=X`, parsing et affichage dynamique

---

## Fichiers JavaScript

### static/js/i18n.js (~634 lignes)

**Role** : Systeme de traduction francais/anglais entierement cote client.

**Contenu** :
- **TRANSLATIONS** : dictionnaire contenant ~250 cles par langue (fr, en), organisees par section (nav, index, speedtest, qt, diag, net, hist, srv)
- **getLang()** : retourne la langue courante depuis `localStorage` (defaut : 'fr')
- **setLang(lang)** : definit la langue et applique les traductions
- **toggleLang()** : bascule entre 'fr' et 'en'
- **t(key, params)** : fonction de traduction avec interpolation (`{variable}` remplace par la valeur)
- **applyTranslations()** : parcourt le DOM, traduit les elements avec `data-i18n` (textContent) et `data-i18n-placeholder` (placeholder des inputs)
- **getLocale()** : retourne `'fr-FR'` ou `'en-GB'` pour le formatage des dates

---

## Fichiers CSS

### static/css/style.css (~264+ lignes)

**Role** : Feuille de style unique, theme sombre par defaut.

**Contenu** :
- **Couleurs principales** :
  - Background : `#0a0e17` (body), `#131a2b` (cartes, navbar)
  - Accent : `#00d4ff` (liens, bordures actives, hover)
  - Texte : `#e0e0e0` (principal), `#8899aa` (secondaire), `#77aacc` (labels)
  - Semantiques : `#00ff88` (succes), `#ff4466` (erreur), `#ffdd57` (warning)
- **Responsive** : breakpoint a 768px, bascule navbar desktop / bottom-bar mobile
- **Composants** :
  - `.navbar` / `.bottom-bar` : navigation desktop/mobile
  - `.card` : conteneur generique avec bordure et ombre
  - `.hero-card` : carte mise en avant avec gradient
  - `.btn`, `.btn-primary`, `.btn-danger` : boutons
  - `.form-group`, `.form-input`, `.form-select` : formulaires
  - `.data-table` : tableaux responsives
  - `.progress-bar` : barre de progression animee
  - `.toast`, `.toast.success`, `.toast.error`, `.toast.info` : notifications
  - `.terminal` : zone de sortie type console (fond tres sombre, police monospace)
  - `.tabs`, `.tab-btn` : barre d'onglets
  - `.stat-grid`, `.stat-item` : grille de statistiques
  - `.section-collapse` : sections repliables

---

## Fichiers de configuration

### servers.json

**Role** : Liste des serveurs iperf3 de l'utilisateur.

**Format** :
```json
[
  {
    "name": "Serveur Paris",
    "host": "paris.iperf.fr",
    "port": 5201,
    "favorite": true
  }
]
```

Contient 3 serveurs publics par defaut. Modifie via l'interface web (`/api/servers`).

### config/public_servers.json

**Role** : Cache local des serveurs publics iperf3 recuperes depuis iperf.fr.

Mis a jour via `/api/public-servers/update`. Evite de requeter le site externe a chaque consultation.

### config/.secret_key

**Role** : Cle secrete Flask generee automatiquement avec `secrets.token_hex(32)`.

- Permissions : `chmod 600`
- Exclue du depot Git via `.gitignore`
- Generee au premier demarrage, reutilisee ensuite
- Sa suppression force la regeneration (et invalide les sessions existantes)

### config/ftp_config.json

**Role** : Identifiants de connexion FTP/SFTP pour l'envoi de resultats.

**Format** :
```json
{
  "type": "sftp",
  "host": "ftp.example.com",
  "port": 22,
  "username": "user",
  "password": "base64_encoded_password",
  "remote_dir": "/uploads/"
}
```

- Permissions : `chmod 600`
- Exclue du depot Git via `.gitignore`
- Le mot de passe est encode en base64

---

## Fichiers systeme

### speedbox.service

**Role** : Fichier unite systemd pour executer SpeedBox comme service.

**Contenu typique** :
```ini
[Unit]
Description=SpeedBox Network Testing
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/speedbox
ExecStart=/opt/speedbox/venv/bin/python app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### requirements.txt

**Role** : Dependances Python du projet.

**Dependances principales** :
- `Flask` (3.1.x) : framework web
- `Flask-SocketIO` (5.6.x) : support WebSocket
- `gevent` : serveur async et monkey-patching
- `gevent-websocket` : transport WebSocket natif pour gevent
- Autres dependances indirectes (Werkzeug, Jinja2, MarkupSafe, etc.)

---

## Repertoires

### results/

Contient les fichiers JSON de resultats. Cree automatiquement si absent. Chaque fichier suit la convention `{type}_{timestamp}.json`. Limite a 200 fichiers lus par `load_results()`.

### config/

Contient les fichiers de configuration sensibles. Cree automatiquement si absent. Les fichiers sensibles (`.secret_key`, `ftp_config.json`) sont en `chmod 600` et exclus de Git.

### static/

Fichiers statiques servis par Flask :
- `static/css/style.css` : feuille de style
- `static/js/i18n.js` : systeme de traduction
- `static/js/chart.js` : bibliotheque Chart.js (vendored)
- `static/js/socket.io.min.js` : client Socket.IO (vendored)

### templates/

Templates Jinja2 :
- `base.html` : layout commun
- `index.html` : dashboard
- `speedtest.html` : test de debit
- `diagnostic.html` : outils de diagnostic
- `network.html` : configuration reseau
- `history.html` : historique
