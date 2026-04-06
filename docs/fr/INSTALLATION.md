# Guide d'installation de SpeedBox

## 1. Prerequis

### Materiel

- **Recommande** : Raspberry Pi 5 (4 Go ou 8 Go de RAM)
- **Compatible** : tout systeme ARM ou x86-64 capable d'executer Debian 12+
- Connexion reseau filaire (eth0) recommandee pour des resultats de test fiables
- Connexion Wi-Fi (wlan0) supportee mais les performances seront limitees par le debit radio

### Systeme d'exploitation

- **Recommande** : DietPi (base Debian 12 optimisee pour Raspberry Pi)
- **Compatible** : Raspberry Pi OS, Debian 12+, Ubuntu 22.04+
- Python 3.11 ou superieur (Python 3.13 recommande)

### Acces reseau

- Acces SSH ou console pour l'installation
- Acces root (ou sudo) requis
- Port 5000 accessible depuis le reseau local (ou 80/443 avec reverse proxy)

---

## 2. Installation des paquets systeme

Mettre a jour les depots et installer les dependances systeme :

```bash
sudo apt update
sudo apt install -y iperf3 mtr traceroute ethtool dnsutils python3 python3-venv git
```

### Detail des paquets

| Paquet | Usage dans SpeedBox |
|--------|-------------------|
| `iperf3` | Tests de debit TCP/UDP |
| `mtr` | Traceroute avance avec analyse par hop |
| `traceroute` | Traceroute classique |
| `ethtool` | Informations sur les interfaces reseau (vitesse, duplex) |
| `dnsutils` | Outil `nslookup` pour les resolutions DNS |
| `python3` | Interpreteur Python |
| `python3-venv` | Environnements virtuels Python |
| `git` | Clonage et mise a jour du depot |

---

## 3. Clonage du depot

Cloner le depot SpeedBox dans `/opt/speedbox` :

```bash
sudo git clone https://github.com/OWNER/speedbox.git /opt/speedbox
cd /opt/speedbox
```

> **Note** : Remplacer `OWNER` par le nom d'utilisateur ou l'organisation GitHub qui heberge le projet.

Verifier que les fichiers sont bien presents :

```bash
ls -la /opt/speedbox/
```

Vous devez voir au minimum : `app.py`, `requirements.txt`, `servers.json`, `speedbox.service`, les repertoires `templates/`, `static/`.

---

## 4. Environnement virtuel Python

Creer un environnement virtuel isole pour les dependances Python :

```bash
cd /opt/speedbox
python3 -m venv venv
```

Activer l'environnement et installer les dependances :

```bash
source venv/bin/activate
pip install -r requirements.txt
```

Verifier l'installation :

```bash
python -c "import flask; import flask_socketio; import gevent; print('OK')"
```

> **Note** : L'environnement virtuel est cree dans `/opt/speedbox/venv/`. Le service systemd utilise directement l'interpreteur Python de cet environnement (`/opt/speedbox/venv/bin/python`), il n'est donc pas necessaire de l'activer manuellement en fonctionnement normal.

---

## 5. Configuration initiale

Creer les repertoires necessaires :

```bash
mkdir -p /opt/speedbox/config /opt/speedbox/results
```

### Fichiers generes automatiquement

Les fichiers suivants sont crees automatiquement par SpeedBox au premier demarrage :

- **`config/.secret_key`** : cle secrete Flask generee avec `secrets.token_hex(32)`. Permissions automatiquement definies a `chmod 600`.
- **`config/public_servers.json`** : cache des serveurs publics iperf3 (telecharge depuis iperf.fr a la premiere consultation).

### Fichier servers.json

Le fichier `servers.json` a la racine du projet contient la liste des serveurs iperf3 de l'utilisateur. Il est fourni avec 3 serveurs publics par defaut. Il peut etre modifie via l'interface web ou directement :

```json
[
  {
    "name": "Paris - Bouygues",
    "host": "paris.bouygues.iperf.fr",
    "port": 5201,
    "favorite": true
  },
  {
    "name": "Lyon - Axione",
    "host": "lyon.axione.iperf.fr",
    "port": 5201,
    "favorite": false
  }
]
```

### Configuration FTP/SFTP (optionnel)

Si vous souhaitez utiliser la fonctionnalite d'envoi de resultats par FTP/SFTP, creez le fichier de configuration :

```bash
cp config/ftp_config.json.example config/ftp_config.json
nano config/ftp_config.json
```

Renseigner les champs : type (ftp/sftp), hote, port, identifiants, repertoire distant. La configuration peut aussi etre faite via l'interface web dans la page Reseau.

---

## 6. Service systemd

Installer le service systemd pour que SpeedBox demarre automatiquement :

```bash
sudo cp /opt/speedbox/speedbox.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable speedbox
sudo systemctl start speedbox
```

### Contenu du fichier speedbox.service

```ini
[Unit]
Description=SpeedBox Network Testing
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/speedbox
ExecStart=/opt/speedbox/venv/bin/python app.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### Commandes utiles

| Commande | Description |
|----------|-------------|
| `sudo systemctl status speedbox` | Voir l'etat du service |
| `sudo systemctl start speedbox` | Demarrer le service |
| `sudo systemctl stop speedbox` | Arreter le service |
| `sudo systemctl restart speedbox` | Redemarrer le service |
| `sudo journalctl -u speedbox -f` | Suivre les logs en temps reel |
| `sudo journalctl -u speedbox --since "1 hour ago"` | Logs de la derniere heure |

---

## 7. Verification

### Verifier le service

```bash
sudo systemctl status speedbox
```

Le service doit afficher `Active: active (running)`. En cas d'erreur, consulter les logs :

```bash
sudo journalctl -u speedbox -n 50
```

### Tester l'API

```bash
curl http://localhost:5000/api/status
```

La reponse doit etre un JSON contenant les informations systeme (IP, interfaces, uptime).

### Acceder a l'interface web

Ouvrir un navigateur et acceder a :

```
http://<adresse_IP_du_Pi>:5000
```

Pour connaitre l'adresse IP :

```bash
hostname -I
```

Vous devez voir le tableau de bord SpeedBox avec les cartes de statut et les liens vers les outils.

---

## 8. Configuration optionnelle

### Reverse proxy nginx

Pour acceder a SpeedBox sur le port 80 (HTTP) ou 443 (HTTPS), configurer nginx comme reverse proxy :

```bash
sudo apt install -y nginx
```

Creer le fichier de configuration :

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
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
```

Activer le site :

```bash
sudo ln -s /etc/nginx/sites-available/speedbox /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

> **Important** : Les directives `proxy_set_header Upgrade` et `Connection "upgrade"` sont indispensables pour le fonctionnement des WebSockets (Socket.IO). Le `proxy_read_timeout 300s` est necessaire pour les tests de longue duree.

### Certificat SSL avec Let's Encrypt

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d speedbox.votre-domaine.fr
```

Certbot modifie automatiquement la configuration nginx pour rediriger HTTP vers HTTPS.

### Firewall

Si un firewall est actif (ufw, iptables), ouvrir les ports necessaires :

```bash
# Sans reverse proxy
sudo ufw allow 5000/tcp

# Avec reverse proxy
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

---

## 9. Mise a jour

Pour mettre a jour SpeedBox vers la derniere version :

```bash
cd /opt/speedbox
sudo git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart speedbox
```

### Verification apres mise a jour

```bash
sudo systemctl status speedbox
curl http://localhost:5000/api/status
```

> **Note** : Les fichiers de configuration (`config/`, `servers.json`) et les resultats (`results/`) sont preserves lors de la mise a jour car ils ne sont pas suivis par Git (via `.gitignore` pour les fichiers sensibles).

---

## 10. Desinstallation

Pour supprimer completement SpeedBox du systeme :

```bash
# Arreter et desactiver le service
sudo systemctl stop speedbox
sudo systemctl disable speedbox

# Supprimer le fichier service
sudo rm /etc/systemd/system/speedbox.service
sudo systemctl daemon-reload

# Supprimer les fichiers de l'application
sudo rm -rf /opt/speedbox

# Optionnel : supprimer la configuration nginx
sudo rm -f /etc/nginx/sites-enabled/speedbox
sudo rm -f /etc/nginx/sites-available/speedbox
sudo systemctl reload nginx
```

> **Note** : Cette operation supprime definitivement tous les resultats de tests et la configuration. Effectuer une sauvegarde des repertoires `config/` et `results/` avant la desinstallation si necessaire.

---

## Depannage

### Le service ne demarre pas

```bash
sudo journalctl -u speedbox -n 100
```

Causes frequentes :
- Python ou un paquet manquant : verifier `pip install -r requirements.txt`
- Port 5000 deja utilise : `sudo lsof -i :5000`
- Erreur de permission : le service doit tourner en root

### L'interface web est inaccessible

- Verifier que le service tourne : `sudo systemctl status speedbox`
- Verifier le firewall : `sudo ufw status`
- Tester localement : `curl http://localhost:5000`
- Verifier l'adresse IP : `hostname -I`

### Les tests iperf3 echouent

- Verifier qu'iperf3 est installe : `iperf3 --version`
- Tester la connectivite au serveur : `ping serveur.iperf.fr`
- Tester iperf3 manuellement : `iperf3 -c serveur.iperf.fr -p 5201`
- Le serveur distant peut etre occupe : reessayer apres quelques minutes

### Les WebSockets ne fonctionnent pas derriere un reverse proxy

- Verifier les headers Upgrade dans la configuration nginx (voir section 8)
- Verifier que `proxy_read_timeout` est suffisant
- Verifier les logs nginx : `sudo tail -f /var/log/nginx/error.log`
