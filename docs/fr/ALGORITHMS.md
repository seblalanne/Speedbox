# Algorithmes de SpeedBox

Ce document detaille les algorithmes principaux de SpeedBox avec du pseudo-code et des explications sur les choix d'implementation.

---

## 1. Analyse MTR

**Fichier** : `app.py`, fonction `parse_mtr_hubs()`
**Entree** : JSON brut produit par `mtr --json`
**Sortie** : Liste structuree de hops avec classification

### Pseudo-code

```
fonction parse_mtr_hubs(mtr_json):
    hubs = []
    previous_avg = None

    pour chaque hub dans mtr_json["report"]["hubs"]:
        # Extraction du hostname et de l'IP
        # Le format MTR est "hostname (IP)" ou juste "IP"
        raw_host = hub["host"]
        match = regex("^(.+?)\s*\(([^)]+)\)$", raw_host)
        si match:
            hostname = match.group(1)
            ip = match.group(2)
        sinon:
            hostname = raw_host
            ip = raw_host

        # Recuperation des metriques
        loss = hub["Loss%"]
        avg = hub["Avg"]
        best = hub["Best"]
        worst = hub["Worst"]
        count = hub["Snt"]  # paquets envoyes

        # Classification de la perte de paquets
        si loss == 0.0:
            loss_class = "good"      # Vert : aucune perte
        sinon si loss <= 5.0:
            loss_class = "warn"      # Jaune : perte mineure
        sinon si loss <= 20.0:
            loss_class = "degraded"  # Orange : perte significative
        sinon:
            loss_class = "critical"  # Rouge : perte critique

        # Detection des spikes de latence
        spike = faux
        si previous_avg n'est pas None ET count > 1:
            delta = avg - previous_avg
            si delta > 20.0:
                spike = vrai          # Saut de latence > 20ms
            sinon si previous_avg > 0 ET avg > (3 * previous_avg):
                spike = vrai          # Latence 3x superieure au hop precedent

        # Extraction optionnelle des informations reseau
        asn = hub.get("ASN", None)    # Numero de systeme autonome
        mpls = hub.get("MPLS", None)  # Labels MPLS si presents

        # Construction du hop structure
        hop = {
            "index": hub["count"],
            "hostname": hostname,
            "ip": ip,
            "loss": loss,
            "loss_class": loss_class,
            "avg": avg,
            "best": best,
            "worst": worst,
            "stdev": hub.get("Stdev", 0),
            "spike": spike,
            "asn": asn,
            "mpls": mpls
        }

        hubs.append(hop)
        previous_avg = avg

    retourner hubs
```

### Seuils de classification

| Perte de paquets | Classification | Couleur | Interpretation |
|-----------------|----------------|---------|----------------|
| 0% | `good` | Vert | Hop sain |
| 0.1% - 5% | `warn` | Jaune | Perte mineure, souvent normale sur les routeurs intermediaires |
| 5.1% - 20% | `degraded` | Orange | Probleme potentiel, a surveiller |
| > 20% | `critical` | Rouge | Probleme avere, probablement la source des dysfonctionnements |

### Detection des spikes

La detection des spikes identifie les sauts de latence anormaux entre deux hops consecutifs. Deux criteres sont utilises (OR logique) :

1. **Delta absolu** : la latence moyenne augmente de plus de 20ms par rapport au hop precedent. Ce seuil capture les augmentations significatives meme a haute latence.

2. **Ratio relatif** : la latence moyenne est plus de 3 fois superieure a celle du hop precedent. Ce critere est efficace pour les hops a faible latence (ex: 1ms -> 5ms).

La condition `count > 1` exclut les hops qui n'ont recu qu'un seul paquet, car leur latence n'est pas statistiquement significative.

---

## 2. Orchestration QuickTest

**Fichier** : `app.py`, handler `start_quicktest`
**Objectif** : Executer une batterie de tests automatises sur les serveurs favoris

### Vue d'ensemble

Le QuickTest enchaine 4 types de tests sur chaque serveur favori (maximum 3 serveurs) :

| Etape | Type | Parametres | Objectif |
|-------|------|-----------|----------|
| 1 | MTR | 60 cycles, 20 hops max | Analyser la route reseau |
| 2 | iperf3 UDP | Debit cible, 60s, 1 flux | Mesurer jitter et perte |
| 3 | iperf3 TCP | Sans limite, 60s, 1 flux | Mesurer le debit maximal |
| 4 | iperf3 TCP | Debit/4, 60s, 4 flux | Tester le multi-flux |

### Pseudo-code

```
handler start_quicktest(data):
    sid = request.sid

    # Charger les serveurs favoris (max 3)
    serveurs = charger_servers_json()
    favoris = [s pour s dans serveurs si s["favorite"]][:3]

    si len(favoris) == 0:
        emettre('quicktest_error', "Aucun serveur favori")
        retourner

    # Definir les etapes pour chaque serveur
    etapes = []
    pour chaque serveur dans favoris:
        etapes.append({type: "mtr",      serveur, params: {cycles: 60, maxhops: 20}})
        etapes.append({type: "udp",      serveur, params: {duration: 60, streams: 1, bandwidth: data.bandwidth}})
        etapes.append({type: "tcp",      serveur, params: {duration: 60, streams: 1, bandwidth: None}})
        etapes.append({type: "tcp_multi", serveur, params: {duration: 60, streams: 4, bandwidth: data.bandwidth / 4}})

    emettre('quicktest_started', {total_etapes: len(etapes), serveurs: favoris})

    pour i, etape dans enumerate(etapes):

        # ---- Verification du stop flag ----
        si sid dans quicktest_stop_flags:
            quicktest_stop_flags.retirer(sid)
            emettre('quicktest_stopped')
            retourner

        max_tentatives = 1 si etape.type == "mtr" sinon 3
        tentative = 0
        succes = faux

        tant que !succes ET tentative < max_tentatives ET sid pas dans quicktest_stop_flags:
            tentative += 1

            # Notifier le client de l'etape en cours
            emettre('quicktest_step', {
                etape: i + 1,
                total: len(etapes),
                type: etape.type,
                serveur: etape.serveur.name,
                status: "running",
                tentative: tentative
            })

            # Construire et executer la commande
            si etape.type == "mtr":
                cmd = ['mtr', '--json', '-c', '60', '-m', '20', etape.serveur.host]
            sinon:
                cmd = construire_cmd_iperf3(etape)

            essayer:
                proc = subprocess.Popen(cmd, stdout=PIPE, stderr=PIPE)
                quicktest_processes[sid] = proc

                # Countdown : emettre chaque seconde le temps restant
                duree = etape.params.duration ou 60
                pour seconde dans range(duree, 0, -1):
                    si sid dans quicktest_stop_flags:
                        proc.terminate()
                        sortir de la boucle
                    emettre('quicktest_countdown', {remaining: seconde})
                    sleep(1)

                stdout, stderr = proc.communicate(timeout=10)

                si proc.returncode == 0:
                    resultat = json.loads(stdout)
                    succes = vrai
                    emettre('quicktest_step', {status: "complete", result: resultat})
                sinon:
                    emettre('quicktest_step', {status: "error", error: stderr})
                    si tentative < max_tentatives:
                        # Pause avant retry avec countdown
                        pour s dans range(10, 0, -1):
                            si sid dans quicktest_stop_flags:
                                sortir
                            emettre('quicktest_retry_countdown', {remaining: s})
                            sleep(1)

            finalement:
                quicktest_processes.pop(sid, None)

        # Sauvegarder le resultat de cette etape
        si succes:
            save_result("quicktest", {
                serveur: etape.serveur,
                type: etape.type,
                result: resultat,
                timestamp: now()
            })

        # Pause entre les etapes (interruptible)
        si i < len(etapes) - 1:
            pour s dans range(10, 0, -1):
                si sid dans quicktest_stop_flags:
                    sortir
                emettre('quicktest_pause', {remaining: s})
                sleep(1)

    # Fin du QuickTest
    quicktest_stop_flags.discard(sid)
    emettre('quicktest_complete', {resultats: tous_les_resultats})
```

### Mecanisme de retry

Les tests iperf3 peuvent echouer pour diverses raisons (serveur occupe, timeout reseau, etc.). Le QuickTest implemente un mecanisme de retry :

- **MTR** : 1 seule tentative (MTR est tres fiable)
- **iperf3** : jusqu'a 3 tentatives
- **Pause entre retries** : 10 secondes avec countdown visible par l'utilisateur
- **Interruptible** : le stop_flag est verifie avant chaque tentative et pendant les pauses

### Interruption propre

L'interruption du QuickTest est un processus en plusieurs niveaux :

1. Le client emet `stop_quicktest`
2. Le handler ajoute `sid` dans `quicktest_stop_flags`
3. Si un subprocess est en cours, il est aussi `terminate()`
4. La boucle principale verifie le flag avant chaque etape
5. Les boucles de countdown verifient le flag chaque seconde
6. Le flag est retire a la sortie

---

## 3. Parsing iperf3

**Fichier** : `app.py`, handler `start_iperf3`
**Entree** : Parametres utilisateur (serveur, port, direction, protocole, debit, duree, flux)
**Sortie** : Resultats en temps reel (intervalles) puis resultat final

### Construction de la commande

```
fonction construire_commande_iperf3(params):
    cmd = ['iperf3', '-c', params.server, '-p', str(params.port)]
    cmd += ['-t', str(params.duration)]
    cmd += ['-J']  # Sortie JSON obligatoire

    si params.direction == "download":
        cmd += ['-R']  # Mode reverse : le serveur envoie

    si params.protocol == "udp":
        cmd += ['-u']               # Mode UDP
        cmd += ['-b', params.bandwidth]  # Debit cible (ex: "100M")

    si params.threads > 1:
        cmd += ['-P', str(params.threads)]  # Flux paralleles

    retourner cmd
```

### Pseudo-code du handler

```
handler start_iperf3(data):
    sid = request.sid

    # Validation des entrees
    si non validate_target(data.server):
        emettre('iperf3_error', "Serveur invalide")
        retourner

    port = int(data.port)
    si port < 1 ou port > 65535:
        emettre('iperf3_error', "Port invalide")
        retourner

    duration = int(data.duration)
    si duration < 1 ou duration > 300:
        emettre('iperf3_error', "Duree invalide")
        retourner

    # Construire la commande
    cmd = construire_commande_iperf3(data)

    essayer:
        # Lancer le processus
        proc = subprocess.Popen(cmd, stdout=PIPE, stderr=PIPE)
        iperf3_processes[sid] = proc

        # Attendre la fin et recuperer le JSON complet
        stdout, stderr = proc.communicate()

        si proc.returncode != 0:
            emettre('iperf3_error', stderr.decode())
            retourner

        result = json.loads(stdout.decode())

        # Emettre les intervalles un par un
        pour interval dans result.get("intervals", []):
            si data.protocol == "tcp":
                stream_data = {
                    "bits_per_second": interval["sum"]["bits_per_second"],
                    "bytes": interval["sum"]["bytes"],
                    "retransmits": interval["sum"].get("retransmits", 0),
                    "seconds": interval["sum"]["seconds"]
                }
            sinon:  # UDP
                stream_data = {
                    "bits_per_second": interval["sum"]["bits_per_second"],
                    "bytes": interval["sum"]["bytes"],
                    "jitter_ms": interval["sum"].get("jitter_ms", 0),
                    "lost_packets": interval["sum"].get("lost_packets", 0),
                    "packets": interval["sum"].get("packets", 0),
                    "seconds": interval["sum"]["seconds"]
                }

            emettre('iperf3_interval', stream_data)
            sleep(0.05)  # Petit delai pour ne pas saturer le WebSocket

        # Resultats finaux
        si data.protocol == "tcp":
            end = result["end"]
            final = {
                "sent": {
                    "bytes": end["sum_sent"]["bytes"],
                    "bits_per_second": end["sum_sent"]["bits_per_second"],
                    "retransmits": end["sum_sent"].get("retransmits", 0)
                },
                "received": {
                    "bytes": end["sum_received"]["bytes"],
                    "bits_per_second": end["sum_received"]["bits_per_second"]
                }
            }
        sinon:  # UDP
            end = result["end"]["sum"]
            final = {
                "bits_per_second": end["bits_per_second"],
                "jitter_ms": end["jitter_ms"],
                "lost_packets": end["lost_packets"],
                "packets": end["packets"],
                "lost_percent": end["lost_percent"]
            }

        emettre('iperf3_complete', final)

        # Sauvegarder le resultat
        save_result("iperf3", {
            "server": data.server,
            "port": data.port,
            "protocol": data.protocol,
            "direction": data.direction,
            "duration": data.duration,
            "result": final,
            "intervals": result.get("intervals", []),
            "timestamp": now()
        })

    finalement:
        iperf3_processes.pop(sid, None)
```

### Structure du JSON iperf3

Le JSON produit par `iperf3 -J` a la structure suivante :

```json
{
  "start": { "connecting_to": {...}, "test_start": {...} },
  "intervals": [
    {
      "streams": [{ "socket": 5, "start": 0, "end": 1, ... }],
      "sum": {
        "start": 0, "end": 1,
        "seconds": 1.0,
        "bytes": 125000000,
        "bits_per_second": 1000000000,
        "retransmits": 0
      }
    }
  ],
  "end": {
    "sum_sent": { "bytes": ..., "bits_per_second": ..., "retransmits": ... },
    "sum_received": { "bytes": ..., "bits_per_second": ... }
  }
}
```

---

## 4. Reecriture de la configuration reseau

**Fichier** : `app.py`, fonction `write_eth0_config()`
**Entree** : Configuration souhaitee (DHCP ou statique avec adresse, masque, passerelle, DNS)
**Sortie** : Fichier `/etc/network/interfaces` mis a jour et configuration appliquee

### Pseudo-code

```
fonction write_eth0_config(config):
    fichier = "/etc/network/interfaces"

    # Etape 1 : Backup
    copier(fichier, fichier + ".bak")

    # Etape 2 : Lire le contenu actuel
    contenu = lire_fichier(fichier)

    # Etape 3 : Construire le nouveau bloc eth0
    si config.mode == "dhcp":
        nouveau_bloc = """
allow-hotplug eth0
iface eth0 inet dhcp
"""
    sinon:  # statique
        netmask = cidr_to_netmask(config.cidr)
        nouveau_bloc = """
allow-hotplug eth0
iface eth0 inet static
    address {config.address}
    netmask {netmask}
    gateway {config.gateway}
    dns-nameservers {config.dns}
"""

    # Etape 4 : Remplacer le bloc eth0 existant
    # Regex qui capture tout le bloc eth0 :
    # De "allow-hotplug eth0" ou "auto eth0"
    # jusqu'au prochain bloc "allow-hotplug" ou "auto" ou fin de fichier
    pattern = r"(allow-hotplug|auto)\s+eth0\b.*?(?=\n(allow-hotplug|auto)\s|\Z)"
    nouveau_contenu = regex.sub(pattern, nouveau_bloc.strip(), contenu, flags=DOTALL)

    # Etape 5 : Ecrire le nouveau contenu
    ecrire_fichier(fichier, nouveau_contenu)

    # Etape 6 : Appliquer immediatement
    essayer:
        # Vider la configuration actuelle
        executer(['ip', 'addr', 'flush', 'dev', 'eth0'])

        si config.mode == "dhcp":
            # Relancer DHCP
            executer(['ifdown', 'eth0'])
            executer(['ifup', 'eth0'])
        sinon:
            # Appliquer manuellement
            executer(['ip', 'addr', 'add',
                      config.address + '/' + str(config.cidr),
                      'dev', 'eth0'])
            executer(['ip', 'route', 'add', 'default',
                      'via', config.gateway])

    attraper Exception:
        # En cas d'erreur, restaurer le backup
        copier(fichier + ".bak", fichier)
        lever l'exception
```

### Conversion CIDR <-> Masque

```
fonction cidr_to_netmask(cidr):
    # cidr = 24 -> netmask = "255.255.255.0"
    bits = (0xFFFFFFFF << (32 - cidr)) & 0xFFFFFFFF
    octets = [
        (bits >> 24) & 0xFF,
        (bits >> 16) & 0xFF,
        (bits >> 8) & 0xFF,
        bits & 0xFF
    ]
    retourner ".".join(str(o) pour o dans octets)

fonction netmask_to_cidr(netmask):
    # netmask = "255.255.255.0" -> cidr = 24
    octets = netmask.split(".")
    bits = 0
    pour octet dans octets:
        bits = (bits << 8) | int(octet)
    cidr = bin(bits).count("1")
    retourner cidr
```

### Precautions

- Le backup est toujours cree avant modification
- Le regex preserve les autres interfaces (lo, wlan0, etc.)
- L'application immediate permet de voir le resultat sans redemarrage
- En cas d'echec de l'application, le backup est restaure
- Le CIDR est valide entre 1 et 32 avant la conversion

---

## 5. Systeme d'internationalisation (i18n)

**Fichier** : `static/js/i18n.js`
**Objectif** : Traduction francais/anglais sans rechargement de page

### Structure du dictionnaire

```javascript
const TRANSLATIONS = {
    fr: {
        // Navigation
        'nav.home': 'Accueil',
        'nav.speedtest': 'Test de debit',
        'nav.diagnostic': 'Diagnostic',
        'nav.network': 'Reseau',
        'nav.history': 'Historique',

        // Index / Dashboard
        'index.title': 'Tableau de bord',
        'index.quicktest': 'Test rapide',
        // ...

        // Speedtest
        'speedtest.server': 'Serveur',
        'speedtest.start': 'Demarrer',
        // ...

        // QuickTest
        'qt.running': 'Test en cours...',
        'qt.step': 'Etape {current} / {total}',
        // ...

        // Diagnostic
        'diag.ping': 'Ping',
        'diag.mtr': 'MTR',
        // ...

        // Network
        'net.config': 'Configuration reseau',
        // ...

        // History
        'hist.title': 'Historique',
        // ...

        // Server management
        'srv.add': 'Ajouter un serveur',
        // ...
    },
    en: {
        'nav.home': 'Home',
        'nav.speedtest': 'Speed Test',
        // ... (meme structure, textes en anglais)
    }
};
```

### Fonction de traduction t()

```
fonction t(key, params = null):
    lang = getLang()  # 'fr' ou 'en'

    # Recherche dans la langue courante
    valeur = TRANSLATIONS[lang][key]

    # Fallback vers le francais si la cle n'existe pas dans la langue
    si valeur est undefined:
        valeur = TRANSLATIONS['fr'][key]

    # Fallback vers la cle brute si elle n'existe nulle part
    si valeur est undefined:
        retourner key

    # Interpolation des parametres
    si params n'est pas null:
        pour chaque (nom, val) dans params:
            valeur = valeur.remplacer("{" + nom + "}", val)

    retourner valeur
```

**Exemples d'utilisation** :

```javascript
// Simple
t('nav.home')                    // "Accueil" (fr) ou "Home" (en)

// Avec interpolation
t('qt.step', {current: 3, total: 12})  // "Etape 3 / 12"

// Cle manquante
t('cle.inexistante')             // "cle.inexistante" (retournee telle quelle)
```

### Application au DOM : applyTranslations()

```
fonction applyTranslations():
    # Traduire les elements avec data-i18n
    pour chaque element avec attribut [data-i18n]:
        key = element.getAttribute("data-i18n")
        si element est un INPUT:
            element.placeholder = t(key)
        sinon:
            element.textContent = t(key)

    # Traduire les placeholders specifiques
    pour chaque element avec attribut [data-i18n-placeholder]:
        key = element.getAttribute("data-i18n-placeholder")
        element.placeholder = t(key)

    # Mettre a jour les boutons de langue
    pour chaque bouton .lang-toggle:
        lang = getLang()
        bouton.textContent = lang == 'fr' ? 'EN' : 'FR'

    # Mettre a jour l'attribut lang du document
    document.documentElement.lang = getLang()
```

**Utilisation dans le HTML** :

```html
<!-- Texte traduit automatiquement -->
<h1 data-i18n="index.title"></h1>

<!-- Placeholder traduit -->
<input type="text" data-i18n-placeholder="diag.ping.target">

<!-- Texte dynamique en JS -->
<script>
    document.getElementById('status').textContent = t('speedtest.running');
</script>
```

### Persistance et locale

```
fonction getLang():
    retourner localStorage.getItem('speedbox_lang') ou 'fr'

fonction setLang(lang):
    localStorage.setItem('speedbox_lang', lang)
    applyTranslations()

fonction toggleLang():
    lang = getLang()
    si lang == 'fr':
        setLang('en')
    sinon:
        setLang('fr')

fonction getLocale():
    lang = getLang()
    si lang == 'fr':
        retourner 'fr-FR'
    sinon:
        retourner 'en-GB'
```

La fonction `getLocale()` est utilisee pour formater les dates et nombres selon la convention locale :

```javascript
// Formatage d'une date
new Date(timestamp).toLocaleString(getLocale())
// fr-FR : "06/04/2026 14:30:00"
// en-GB : "06/04/2026, 14:30:00"

// Formatage d'un nombre
(1234567.89).toLocaleString(getLocale())
// fr-FR : "1 234 567,89"
// en-GB : "1,234,567.89"
```
