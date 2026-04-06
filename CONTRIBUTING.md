# Contribuer a SpeedBox / Contributing to SpeedBox

Merci de votre interet pour SpeedBox ! Voici les guidelines pour contribuer.

*Thank you for your interest in SpeedBox! Here are the guidelines for contributing.*

---

## Comment contribuer / How to Contribute

1. **Fork** le depot sur GitHub
2. **Creer une branche** pour votre modification : `git checkout -b feature/ma-feature`
3. **Modifier** le code en respectant les conventions ci-dessous
4. **Tester** sur un Raspberry Pi ou systeme Debian equivalent
5. **Commit** avec un message clair et descriptif
6. **Push** votre branche : `git push origin feature/ma-feature`
7. **Ouvrir une Pull Request** avec une description de vos changements

---

## Conventions de code / Code Conventions

### Python (app.py)

- Style **PEP 8**
- Pas de frameworks supplementaires — Flask + Flask-SocketIO uniquement
- Tous les appels `subprocess` utilisent des **listes** (pas `shell=True`)
- Valider les entrees utilisateur avec `validate_target()` ou regex
- Tracker les processus par `request.sid` dans les dicts (`iperf3_processes`, `diag_processes`, etc.)
- Nettoyer les processus dans des blocs `finally`
- Utiliser `except Exception` (pas de `bare except`)
- Les reponses API utilisent `{'success': True/False}` de maniere coherente
- Les messages serveur utilisent `message_key` pour l'i18n cote client

### JavaScript (templates)

- **Vanilla JS** uniquement — pas de jQuery, React, Vue, etc.
- Pas de build step — le code doit fonctionner directement dans le navigateur
- Utiliser `var` pour la compatibilite (pas de `let`/`const` dans les templates inline)
- Pour les strings utilisateur, toujours utiliser `t('key')` (jamais de texte en dur)
- Les handlers WebSocket doivent verifier `data.message_key` avant `data.message`

### CSS (style.css)

- Un seul fichier CSS, pas de preprocesseur
- Respecter la palette de couleurs existante (#0a0e17, #00d4ff, #131a2b)
- Minimum 44px de hauteur pour les elements interactifs (accessibilite tactile)
- Responsive : tester a 768px et 400px

### Internationalisation (i18n.js)

- **Toujours** ajouter les cles dans les deux langues (FR et EN)
- Nommer les cles par section : `nav.*`, `index.*`, `speedtest.*`, `diag.*`, `net.*`, `hist.*`, `srv.*`
- Utiliser `{variable}` pour l'interpolation dans les traductions
- Pour le HTML statique : `data-i18n="key"`
- Pour les placeholders : `data-i18n-placeholder="key"`
- Pour le JS dynamique : `t('key', {param: value})`

---

## Structure du projet / Project Structure

```
/opt/speedbox/
├── app.py                 # Backend Flask (routes + WebSocket)
├── servers.json           # Serveurs iperf3 enregistres
├── config/                # Configuration (secrets gitignored)
├── results/               # Resultats des tests (gitignored)
├── static/
│   ├── css/style.css      # Styles
│   └── js/
│       ├── i18n.js        # Traductions FR/EN
│       ├── chart.umd.min.js
│       └── socket.io.min.js
├── templates/             # Templates Jinja2
├── docs/                  # Documentation FR + EN
├── LICENSE                # AGPL-3.0
└── requirements.txt       # Dependencies Python
```

---

## Signaler un bug / Report a Bug

Ouvrir une **Issue** sur GitHub avec :
- Description du probleme
- Etapes pour reproduire
- Comportement attendu vs observe
- Version de l'OS et de Python
- Logs si disponibles (`journalctl -u speedbox`)

---

## Licence / License

En contribuant, vous acceptez que vos contributions soient sous licence **AGPL-3.0-only**, la meme licence que le projet.

*By contributing, you agree that your contributions will be licensed under **AGPL-3.0-only**, the same license as the project.*
