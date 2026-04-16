# SpeedBox - Déploiement sur image DietPi

Ce dossier contient les outils pour déployer SpeedBox sur un Raspberry Pi via une image DietPi.

## Méthode 1 : Automation DietPi (recommandée)

Cette méthode configure une image DietPi vierge pour installer SpeedBox automatiquement au premier démarrage.

### Prérequis

- Image DietPi officielle pour Raspberry Pi 5 : https://dietpi.com/#download
- Une carte SD (16 Go minimum)
- Logiciel de flash : [balenaEtcher](https://etcher.balena.io/) ou `dd`

### Étapes

**1. Flasher l'image DietPi** sur la carte SD avec balenaEtcher ou `dd`

**2. Ouvrir la partition boot** de la carte SD (appelée `bootfs`) — accessible depuis Windows, Mac ou Linux

**3. Copier `Automation_Custom_Script.sh`** à la racine de la partition boot

**4. Modifier `dietpi.txt`** avec un éditeur de texte (Notepad sur Windows) — une seule ligne à changer :
   ```
   AUTO_SETUP_AUTOMATED=1
   ```

**5. Éjecter la carte SD**, l'insérer dans le Raspberry Pi et **connecter l'Ethernet**

**6. Démarrer le Pi** et attendre ~5-10 minutes

SpeedBox est accessible sur `http://<IP-du-Pi>:5000`

> **Sur Linux/Mac**, vous pouvez utiliser `apply-config.sh` pour automatiser les étapes 3 et 4 :
> ```bash
> bash apply-config.sh /media/user/bootfs
> ```

> **Mot de passe SSH par défaut** : `dietpi` — à changer après installation avec `passwd`

---

## Méthode 2 : Créer une image .img pré-construite

Cette méthode clone une installation existante et fonctionnelle pour créer une image prête à flasher.

### Prérequis

- Un Raspberry Pi 5 avec SpeedBox installé et fonctionnel
- Un PC Linux (ou un 2e Pi) avec `pishrink.sh`
- Un lecteur de carte SD USB

### Étape 1 : Préparer le Pi source

Nettoyer l'installation avant de cloner :

```bash
# Supprimer les résultats de test
rm -f /opt/speedbox/results/*.json

# Supprimer les secrets (seront régénérés au prochain boot)
rm -f /opt/speedbox/config/.secret_key
rm -f /opt/speedbox/config/.fernet_key
rm -f /opt/speedbox/config/ftp_config.json

# Vider les logs
journalctl --rotate && journalctl --vacuum-time=1s
rm -f /var/tmp/dietpi/logs/*.log

# Vider l'historique bash
> /root/.bash_history
> /home/dietpi/.bash_history

# Arrêter proprement
sudo shutdown -h now
```

### Étape 2 : Cloner la carte SD

Sur un PC Linux, insérer la carte SD du Pi et la cloner :

```bash
# Identifier le device (ex: /dev/sdb)
lsblk

# Cloner la carte SD (ATTENTION au device !)
sudo dd if=/dev/sdb of=speedbox-v1.0.0.img bs=4M status=progress
```

### Étape 3 : Réduire l'image avec PiShrink

```bash
# Installer pishrink si pas déjà fait
wget https://raw.githubusercontent.com/Drewsif/PiShrink/master/pishrink.sh
chmod +x pishrink.sh
sudo mv pishrink.sh /usr/local/bin/

# Réduire l'image (supprime l'espace vide, active l'expansion auto au boot)
sudo pishrink.sh -z speedbox-v1.0.0.img
```

Résultat : `speedbox-v1.0.0.img.gz` (~1-2 Go au lieu de 16-32 Go)

### Étape 4 : Flasher l'image

```bash
# Avec dd
gunzip -c speedbox-v1.0.0.img.gz | sudo dd of=/dev/sdX bs=4M status=progress

# Ou avec balenaEtcher (interface graphique)
```

### Étape 5 : Premier démarrage

Au premier boot :
- La partition s'étend automatiquement (grâce à PiShrink)
- Les clés secrètes Flask et Fernet sont régénérées automatiquement
- SpeedBox est immédiatement accessible sur `http://<IP>:5000`

---

## Notes importantes

### Sécurité
- **Changer le mot de passe** après le premier boot : `passwd`
- Les clés secrètes Flask et Fernet sont générées automatiquement, uniques par installation
- Les identifiants FTP ne sont jamais inclus dans l'image

### Réseau
- Par défaut, le Pi utilise **DHCP sur eth0**
- L'IP peut être configurée via l'interface SpeedBox (page Réseau)
- Le hostname par défaut est `SpeedBox`

### Mises à jour
Pour mettre à jour SpeedBox sur une installation déployée :
```bash
cd /opt/speedbox
git pull
venv/bin/pip install -r requirements.txt
sudo systemctl restart speedbox
```
