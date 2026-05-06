# Changelog

Toutes les modifications notables de SpeedBox sont documentees ici.

*All notable changes to SpeedBox are documented here.*

---

## v1.2.0 — Test iperf3 bidirectionnel (2026-05-06)

### Nouveau / New

**Test iperf3 bidirectionnel / Bidirectional iperf3 test**
- Nouveau mode "Bidir" dans le selecteur de direction du SpeedTest (utilise `iperf3 --bidir`)
- Test simultane upload + download en une seule execution
- Affichage des resultats adapte : debit montant + descendant + volumes emis/recus
- Logs d'intervalles avec fleches directionnelles (↑/↓) en mode bidir
- Icone de direction ⇅ sur les cartes mobiles dans l'historique
- Support optionnel du parametre `direction` dans les etapes iperf3 du QuickTest (retrocompatible, defaut "upload")

### Ameliorations / Improvements

- Parsing UDP ameliore : utilise `sum_sent` / `sum_received` quand disponibles (necessaire pour le mode bidir)
- Grille de resultats enrichie : affiche toujours les 4 metriques (debit montant, descendant, volume emis, recu)
- i18n : 5 nouvelles cles en FR et EN (`avg_upload`, `avg_download`, `sent_volume`, `recv_volume`, `bidir_done`)

---

## v1.1.0 — DietPi Image + Docker (2026-04-16)

### Nouveau / New

**Image DietPi pré-construite / Pre-built DietPi image**
- Image `.img.gz` prête à flasher, publiée sur GitHub Releases
- Installation 100% automatique au premier boot via `Automation_Custom_Script.sh`
- Durée du premier boot : ~5 minutes

**Point d'accès WiFi / WiFi Access Point**
- SSID : `SpeedBox`, mot de passe : `speedbox`, canal 3, région FR
- IP du Pi sur le réseau WiFi : `192.168.10.1`
- Portail captif : ouverture automatique du navigateur sur iOS, Android et Windows
- Partage de connexion : NAT eth0 → wlan0 (les clients WiFi ont Internet via l'Ethernet du Pi)

**Support Docker / Docker support**
- `Dockerfile` : image Python 3.13 slim avec tous les outils réseau
- `docker-compose.yml` : déploiement one-command
- Build multi-architecture : `linux/amd64` et `linux/arm64`
- Images publiées sur Docker Hub (`seblalanne/speedbox`) et GitHub Container Registry (`ghcr.io/dashand/speedbox`)
- CI/CD GitHub Actions : build et push automatiques sur push `main` et tags `v*.*.*`

### Améliorations / Improvements

- Détection automatique de l'interface réseau principale (`eth0` sur Pi, `ens*` sur VM, configurable via `ETH_INTERFACE`)
- Interface WiFi absente → affiche "Non détecté" / "Not detected" (i18n) au lieu d'une erreur
- README mis à jour avec les 3 options d'installation (image DietPi, Docker, manuel)
- Documentation Docker bilingue (`README.docker.md`)

---

## v1.0.0 -- Initial Open Source Release (2026-04-06)

### Fonctionnalites / Features

**Tests de debit / Speed Tests**
- Tests iperf3 TCP et UDP (upload/download)
- Support multi-stream (jusqu'a N threads paralleles)
- Presets de bande passante (50M, 100M, 500M, 1G, etc.)
- Gestion de serveurs iperf3 personnalises (ajout/suppression/favoris)
- Import automatique des serveurs publics depuis iperf.fr
- Progression en temps reel via WebSocket avec graphique Chart.js

**QuickTest**
- Sequence automatisee par serveur favori (max 3 serveurs)
- 4 etapes par serveur : MTR 60 cycles, UDP au debit cible, TCP mono-stream, TCP 4-streams
- Retry automatique (3 tentatives pour iperf3, 1 pour MTR)
- Countdown en temps reel, arret propre a tout moment
- Sauvegarde individuelle de chaque etape

**Diagnostics reseau / Network Diagnostics**
- Ping avec sortie en temps reel (streaming ligne par ligne)
- MTR avec analyse par hop (classification perte, detection de spikes latence, ASN, MPLS)
- DNS lookup (nslookup avec serveur DNS optionnel)
- Arret propre des diagnostics en cours

**Configuration reseau / Network Configuration**
- Affichage status interfaces (eth0, wlan0) : IP, masque, MAC, vitesse
- Configuration IP statique/DHCP avec persistence (/etc/network/interfaces)
- Gestion VLAN (creation/suppression avec IP optionnelle)
- Backup automatique avant modification de la config reseau

**Export FTP/SFTP**
- Support FTP, FTP+TLS, SFTP, SCP
- Sauvegarde des identifiants (base64, chmod 600)
- Test de connexion avant envoi
- Envoi du dernier resultat ou de tous les resultats

**Historique / History**
- Onglets par type de test (iperf3, MTR, Ping, QuickTest)
- Graphique de tendance (Chart.js)
- Vue tableau desktop + cartes mobile
- Suppression de l'historique

**Interface utilisateur / User Interface**
- Theme dark responsive (desktop + mobile)
- Barre de navigation desktop + barre d'onglets mobile
- Notifications toast
- Sections repliables
- Interface bilingue francais/anglais avec toggle instantane
- Detection de portail captif

**Securite / Security**
- Cle secrete Flask auto-generee (secrets.token_hex, chmod 600)
- Validation des entrees (regex hostname, IP, CIDR, VLAN ID)
- Pas de shell=True dans les appels subprocess
- Mots de passe FTP encodes en base64, fichier chmod 600

**Infrastructure**
- Service systemd avec auto-restart
- gevent pour la concurrence (monkey.patch_all)
- Pas de build step (clone et run)
