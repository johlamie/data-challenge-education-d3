# Tableau de bord « Salles & Maîtres » — défi 3 (code de l'application)

Équipe **EduPrioriteBurkina_MelissaJohn** · Data Challenge Éducation Burkina Faso 2026 · défi 3 :
« Comment mieux répartir les salles de classe et les enseignants ? »

Ce dossier contient le code de l'application en ligne sur https://ecoles2030.unicalabs.bf
(accès par code, communiqué au jury) et les **données fictives** qui permettent de la lancer
sans base de données. Il ne contient aucune donnée du concours, aucun secret, aucun code d'accès.

Le code source complet (scripts Python de nettoyage et de transformation, équivalents des recettes
Dataiku DSS, analyse, application) est publié sur le dépôt public :
https://github.com/johlamie/data-challenge-education-d3

## Lancer en local sur les données fictives

Python 3.12. Depuis ce dossier :

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
DC_EDU_DEMO=1 DC_EDU_AUTH=0 .venv/bin/python -c \
  "from d3dash.app import creer_app_production as c; c().server.run(host='127.0.0.1', port=8796)"
```

Puis ouvrir http://127.0.0.1:8796. Un bandeau rouge « Données fictives » reste affiché : en mode
démonstration, tous les noms de province et tous les chiffres sont inventés (`d3dash/demo.py`) ;
seuls les contours de la carte sont réels (limites administratives publiques COD-AB,
`d3dash/demo_geo.json`). La page `/_kit` (galerie des composants) n'existe qu'en démonstration.

## Lancer les tests

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

237 tests, sur les données fictives uniquement. Un test échoue dans ce dossier, et c'est attendu :
`tests/test_page_methode.py::test_portraits_ronds_et_repli_sans_fichier` suppose la présence des
portraits de l'équipe, qui ne sont pas fournis ici (la page « À propos » s'affiche alors sans
portrait). Le test de conservation des totaux nationaux entre l'ancien découpage (45 provinces) et
celui de 2025 (47 provinces) est `tests/test_decoupage_2025.py`.

## Structure

| Chemin | Rôle |
|---|---|
| `wsgi.py` | point d'entrée (gunicorn `wsgi:server`) |
| `d3dash/app.py` | création de l'application Dash, routage, bandeaux |
| `d3dash/config.py` | configuration lue dans l'environnement (voir `.env.example`, sans valeur) |
| `d3dash/auth.py` | accès par code, limitation des essais, en-têtes de sécurité |
| `d3dash/db.py` | lecture seule des vues et tables d'analyse (PostgreSQL), cache mémoire |
| `d3dash/demo.py`, `d3dash/demo_geo.json` | jeu de données fictif du mode démonstration |
| `d3dash/calculs.py` | chiffres clés, classement, besoins 2030 (méthode de l'analyse) |
| `d3dash/decoupage.py` | passage des besoins 2030 au découpage de 2025, totaux conservés |
| `d3dash/composants.py`, `d3dash/figures.py` | kit d'interface et figures (cartes, graphiques) |
| `d3dash/pages/` | les six pages : vue d'ensemble, classement, fiche province, besoins 2030, implantation, à propos |
| `assets/` | feuilles de style, scripts et icônes servis localement (aucune ressource externe) |
| `outils/` | contrôle navigateur (`verifier_d3.py`, demande Playwright) et contrôle sur la base d'analyse |
| `tests/` | tests automatiques |

## Ce qui n'est pas dans ce dossier

Données du concours, base de données, fichiers d'environnement, codes d'accès, configuration du
serveur (nginx, systemd, scripts d'installation), portraits de l'équipe, documents de conception
internes. Les adresses réseau du serveur ont été remplacées par une adresse de documentation
(192.0.2.10).
