# Architecture de SpeedBox

## 1. Vue d'ensemble du systeme

SpeedBox suit une architecture 3-tiers classique : presentation, logique applicative et couche systeme.

```
+---------------------------------------------+
|              NAVIGATEUR (Client)             |
|  +----------------------------------------+ |
|  | Vanilla JS | Chart.js | Socket.IO CLI  | |
|  | i18n.js    | CSS Dark Theme             | |
|  +------------------+---------------------+ |
|                      |                       |
|          HTTP (REST) | WebSocket (Socket.IO) |
+----------------------+-----------------------+
                       |
+----------------------+-----------------------+
|           SERVEUR FLASK (app.py)             |
|  +----------------------------------------+ |
|  | Flask 3.1 + Flask-SocketIO 5.6         | |
|  | gevent (async_mode)                     | |
|  | Routes REST (25+) | Handlers WS (8)    | |
|  | Validation | Parsing | Gestion process | |
|  +------------------+---------------------+ |
|                      |                       |
+----------------------+-----------------------+
                       |
+----------------------+-----------------------+
|           COUCHE SYSTEME / DONNEES           |
|                                              |
|  Outils:                Fichiers:            |
|  +----------------+    +------------------+  |
|  | iperf3         |    | results/*.json   |  |
|  | mtr            |    | config/          |  |
|  | ping           |    |   .secret_key    |  |
|  | traceroute     |    |   ftp_config.json|  |
|  | nslookup       |    |   public_servers |  |
|  | ip / ethtool   |    | servers.json     |  |
|  +----------------+    +------------------+  |
|                                              |
+----------------------------------------------+
```

### Tier 1 : Presentation (Navigateur)

Le client est entierement compose de fichiers statiques servis par Flask. Aucun framework JavaScript n'est utilise : tout est en vanilla JS. L'interface communique avec le serveur de deux manieres :

- **HTTP REST** : pour les operations CRUD (charger la config, sauvegarder des serveurs, lire l'historique)
- **WebSocket (Socket.IO)** : pour les operations temps reel (tests de debit, ping, MTR, DNS)

### Tier 2 : Logique applicative (Flask)

Le fichier `app.py` centralise toute la logique serveur. Il expose des routes REST classiques et des handlers WebSocket. Il orchestre les appels aux outils systeme via `subprocess.Popen`, parse les resultats, et les retransmet au client.

### Tier 3 : Systeme et donnees

Les tests reseau s'appuient sur des outils systeme standards (iperf3, mtr, ping, etc.). Les resultats sont persistes sous forme de fichiers JSON dans le repertoire `results/`. La configuration utilisateur est stockee dans `config/`.

---

## 2. Stack technique

### Python 3.13 + Flask 3.1

Flask a ete choisi pour sa legerete et sa simplicite. Un seul fichier `app.py` suffit a definir toutes les routes et handlers. Python 3.13 apporte les dernieres optimisations de performance et les fonctionnalites modernes du langage.

### Flask-SocketIO 5.6 avec gevent

Flask-SocketIO ajoute le support WebSocket a Flask. Le mode `async_mode='gevent'` est utilise car il offre un modele de concurrence cooperatif ideal pour les operations d'I/O bloquantes (lecture de subprocess, attente de resultats reseau).

### gevent monkey.patch_all()

L'appel a `monkey.patch_all()` en tout debut de fichier est indispensable. Il remplace les modules standards de Python (socket, threading, time, subprocess, etc.) par des versions cooperatives. Sans ce patch, un appel bloquant comme `subprocess.communicate()` bloquerait l'ensemble du serveur et empecherait les autres clients de communiquer.

Concretement, quand un test iperf3 dure 60 secondes, gevent peut basculer vers d'autres greenlets (connexions WebSocket d'autres clients) pendant les attentes I/O, sans avoir besoin de threads systeme.

### Chart.js (vendored)

Chart.js est inclus directement dans les fichiers statiques (`static/js/`), sans CDN. Ce choix garantit le fonctionnement hors-ligne et evite les dependances externes. Il est utilise pour les graphiques de debit en temps reel (speedtest) et les tendances historiques (history).

### Socket.IO client (vendored)

Le client Socket.IO est egalement inclus localement, coherent avec la philosophie zero-dependance-externe. Il fournit la reconnexion automatique, le fallback HTTP long-polling, et la serialisation des evenements.

### Vanilla JavaScript

Aucun framework (React, Vue, Angular) n'est utilise. Le code JS est directement dans les templates HTML ou dans des fichiers JS dedies. Avantages :

- Aucune etape de build (pas de webpack, vite, etc.)
- Demarrage instantane, pas de hydration
- Taille minimale des assets
- Maintenance simple : chaque page est autonome

### Systeme i18n personnalise

Plutot que d'utiliser Flask-Babel (qui necessite des fichiers .po/.mo, la compilation des traductions, et une configuration serveur), SpeedBox utilise un systeme i18n entierement cote client :

- Un dictionnaire JS (`TRANSLATIONS`) contient toutes les cles en francais et en anglais (~250 cles par langue)
- La fonction `t(key, params)` retourne la traduction avec interpolation de variables
- `applyTranslations()` met a jour le DOM via les attributs `data-i18n`
- La preference de langue est stockee dans `localStorage`

Ce choix simplifie le deploiement (pas de compilation de traductions) et permet le changement de langue instantane sans rechargement de page.

---

## 3. Flux d'un test de debit

Voici le parcours complet d'un test iperf3, de l'action utilisateur au resultat affiche :

```
1. L'utilisateur selectionne un serveur, configure les parametres
   (direction, protocole, debit, duree, flux) et clique "Demarrer"

2. Le JavaScript emet l'evenement WebSocket 'start_iperf3' avec les
   parametres :
   { server, port, duration, protocol, direction, bandwidth, threads }

3. Le handler Flask @socketio.on('start_iperf3') recoit l'evenement

4. Validation des entrees :
   - server : regex ^[a-zA-Z0-9.\-:]+$
   - port : entier 1-65535
   - duration : entier 1-300
   - bandwidth : format valide (ex: "100M")
   - threads : entier 1-32

5. Construction de la commande iperf3 :
   cmd = ['iperf3', '-c', server, '-p', port, '-t', duration, '-J']
   Si download : cmd += ['-R']         # reverse mode
   Si UDP      : cmd += ['-u', '-b', bandwidth]
   Si multi    : cmd += ['-P', threads]

6. Execution via subprocess.Popen(cmd, stdout=PIPE, stderr=PIPE)
   Le PID est stocke dans iperf3_processes[request.sid]

7. Lecture du stdout (JSON complet via communicate())

8. Parsing du JSON iperf3 :
   Pour chaque intervalle dans result['intervals']:
     Extraire bits_per_second, bytes, retransmits (TCP) ou
     jitter_ms, lost_packets, packets (UDP)
     Emettre 'iperf3_interval' vers le client

9. Emission de 'iperf3_complete' avec les resultats finaux :
   TCP : sum_sent, sum_received du bloc 'end'
   UDP : jitter, perte, debit du bloc 'end'

10. Cote client :
    - Chart.js met a jour le graphique en temps reel a chaque intervalle
    - Les statistiques finales sont affichees (debit moyen, max, jitter)
    - Le resultat complet est affiche dans la zone de resultats

11. Sauvegarde du resultat dans results/iperf3_{timestamp}.json

12. Nettoyage : suppression du PID de iperf3_processes[request.sid]
```

---

## 4. Gestion des processus

SpeedBox execute des commandes systeme potentiellement longues (un test iperf3 peut durer 300 secondes). La gestion rigoureuse des processus est critique pour eviter les fuites de ressources.

### Dictionnaires de suivi par session

Trois dictionnaires globaux tracent les processus actifs, indexes par l'identifiant de session Socket.IO (`request.sid`) :

```python
iperf3_processes = {}      # Tests iperf3 en cours
diag_processes = {}        # Ping, MTR, DNS en cours
quicktest_processes = {}   # Sous-processus QuickTest en cours
quicktest_stop_flags = set()  # SIDs dont le QuickTest doit s'arreter
```

L'utilisation de `request.sid` comme cle garantit qu'un client ne peut avoir qu'un seul processus de chaque type a la fois, et permet de retrouver le processus a arreter.

### Cycle de vie d'un processus

```
1. Creation     : proc = subprocess.Popen(cmd, ...)
2. Enregistrement : iperf3_processes[request.sid] = proc
3. Execution    : communicate() ou readline() en boucle
4. Nettoyage    : dans un bloc finally:
                    proc.terminate()  # si toujours actif
                    iperf3_processes.pop(request.sid, None)
```

### Arret propre (stop handlers)

Quand l'utilisateur clique "Arreter", le client emet un evenement stop (ex: `stop_iperf3`). Le handler serveur :

```python
@socketio.on('stop_iperf3')
def handle_stop_iperf3():
    proc = iperf3_processes.get(request.sid)
    if proc:
        proc.terminate()           # Envoyer SIGTERM
        try:
            proc.wait(timeout=3)   # Attendre 3 secondes
        except subprocess.TimeoutExpired:
            proc.kill()            # Forcer SIGKILL si necessaire
```

### QuickTest et stop_flags

Le QuickTest est une sequence de plusieurs tests. Un simple `terminate()` ne suffit pas car il faut interrompre la boucle entre les tests. Le mecanisme `quicktest_stop_flags` resout ce probleme :

- `stop_quicktest` : ajoute `request.sid` dans `quicktest_stop_flags`
- Avant chaque etape, le handler verifie `if sid in quicktest_stop_flags`
- Si le flag est present, la boucle s'arrete proprement et le flag est retire

---

## 5. Flux de donnees

### Stockage des resultats

Les resultats sont sauvegardes sous forme de fichiers JSON dans le repertoire `results/`. La convention de nommage est :

```
results/{type}_{timestamp}.json
```

- `type` : `iperf3`, `mtr`, `ping`, ou `quicktest`
- `timestamp` : format ISO ou epoch pour un tri chronologique naturel

Exemples :
```
results/iperf3_1712345678.json
results/mtr_1712345690.json
results/ping_1712345700.json
results/quicktest_1712345750.json
```

### Chargement des resultats

La fonction `load_results()` :

1. Liste tous les fichiers `*.json` dans `results/`
2. Filtre par type si specifie
3. Trie par date de modification (plus recent en premier)
4. Limite a 200 resultats maximum pour eviter la surcharge memoire
5. Parse chaque fichier JSON et retourne une liste de dictionnaires

### Affichage dans l'historique

La page historique (`/history`) presente les resultats de la maniere suivante :

- **Barre d'onglets** : un onglet par type de test (iperf3, MTR, ping, QuickTest)
- **Graphique tendance** : Chart.js trace l'evolution du debit, de la latence ou de la perte dans le temps
- **Tableau desktop** : vue tabulaire avec colonnes triables
- **Cartes mobiles** : meme information dans un format adapte aux petits ecrans
- **Bouton "Effacer"** : supprime tous les resultats du type selectionne via `DELETE /api/history/clear`

---

## 6. Modele de securite

### Cle secrete Flask

La cle secrete utilisee pour signer les sessions Flask est generee automatiquement au premier demarrage :

```python
secret_key = secrets.token_hex(32)  # 64 caracteres hexadecimaux
```

Elle est stockee dans `config/.secret_key` avec des permissions restrictives (`chmod 600`). Si le fichier existe deja, la cle est relue. Ce mecanisme evite la rotation involontaire de la cle (qui invaliderait toutes les sessions) lors d'un redemarrage.

### Identifiants FTP/SFTP

Les mots de passe FTP/SFTP sont encodes en base64 avant d'etre stockes dans `config/ftp_config.json` (egalement `chmod 600`). L'encodage base64 n'est pas un chiffrement : il offre une protection minimale contre la lecture accidentelle, pas contre un acces malveillant au fichier. Le fichier est exclu du depot Git via `.gitignore`.

### Validation des entrees

Toutes les entrees utilisateur sont validees avant utilisation dans les commandes systeme :

| Champ | Validation | Regex / Plage |
|-------|-----------|---------------|
| Hostname/IP | Regex | `^[a-zA-Z0-9.\-:]+$` |
| Port | Entier | 1-65535 |
| CIDR | Entier | 1-32 |
| VLAN ID | Entier | 1-4094 |
| Duree | Entier | 1-300 |
| Streams | Entier | 1-32 |

### Protection contre l'injection de commandes

Tous les appels `subprocess` utilisent la forme liste (array) des arguments :

```python
# Correct : chaque argument est un element separe
subprocess.Popen(['iperf3', '-c', server, '-p', str(port)])

# Jamais : shell=True avec concatenation de strings
subprocess.Popen(f'iperf3 -c {server} -p {port}', shell=True)  # DANGEREUX
```

La forme liste empeche l'injection de commandes car le shell n'interprete pas les metacaracteres (`;`, `|`, `&&`, etc.).

### Privileges root

SpeedBox s'execute en tant que root car plusieurs commandes systeme l'exigent :

- `ip addr`, `ip link`, `ip route` : configuration reseau
- `ethtool` : informations sur l'interface
- `ifup` / `ifdown` : activation/desactivation d'interfaces
- `reboot` : redemarrage du systeme

C'est un compromis necessaire pour un outil d'administration reseau. Les risques sont mitiges par la validation stricte des entrees et l'absence de `shell=True`.

### CORS

CORS est configure avec `origins='*'` pour permettre l'acces derriere un reverse proxy (nginx, Traefik, etc.) qui pourrait changer l'origine des requetes. Dans un environnement de production, il est recommande de restreindre les origines autorisees.
