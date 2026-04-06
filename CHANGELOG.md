# Changelog

Toutes les modifications notables de SpeedBox sont documentees ici.

*All notable changes to SpeedBox are documented here.*

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
