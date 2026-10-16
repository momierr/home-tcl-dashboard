# home-tcl-dashboard

Un tableau de bord mural des prochains départs TCL (transports en commun de
Lyon) pour les arrêts que vous utilisez, servi par un serveur à la maison et
affiché en plein écran sur une tablette.

**[Essayer la démo](https://momierr.github.io/home-tcl-dashboard/)**, sans
rien installer : des horaires enregistrés un soir de semaine, rejoués en
direct, et des favoris gardés dans votre navigateur.

![L'accueil : six arrêts favoris au plus, avec leurs prochains départs](https://raw.githubusercontent.com/momierr/home-tcl-dashboard/main/.github/screenshots/home.png)

- **Accueil** : jusqu'à 6 arrêts favoris, avec les comptes à rebours, en
  temps réel ou d'après l'horaire prévu, et un bandeau pour les alertes
  trafic sur vos lignes.
- **Détail d'un arrêt** : les prochains départs et les arrêts suivants de la
  ligne.
- **Alertes** : les alertes trafic sur vos lignes, ou sur tout le réseau.
- **Gérer mes arrêts** : ajouter, réordonner et retirer des favoris, depuis
  n'importe quel appareil du réseau. Les favoris sont partagés : une seule
  liste pour toute la maison.
- **Parcourir** : n'importe quelle ligne sur une carte, avec les départs de
  chacun de ses arrêts.

Le métro et le funiculaire n'ont pas de temps réel : leurs départs viennent
de l'horaire GTFS. Les trams et les bus utilisent le temps réel.

| Détail d'un arrêt | Parcourir les lignes |
|---|---|
| ![Détail d'un arrêt](https://raw.githubusercontent.com/momierr/home-tcl-dashboard/main/.github/screenshots/stop.png) | ![Parcourir les lignes](https://raw.githubusercontent.com/momierr/home-tcl-dashboard/main/.github/screenshots/browse.png) |
| **Thème nuit, de 20h à 7h** | **Sur un téléphone** |
| ![Thème nuit](https://raw.githubusercontent.com/momierr/home-tcl-dashboard/main/.github/screenshots/home-night.png) | <img src="https://raw.githubusercontent.com/momierr/home-tcl-dashboard/main/.github/screenshots/phone.png" alt="Sur un téléphone" width="240"> |

## Prérequis

- Python 3.14 ou plus récent.
- Un compte gratuit [data.grandlyon.com](https://data.grandlyon.com) avec
  accès aux jeux de données TCL (le temps réel et les alertes demandent un
  identifiant).

## Installation

Avec pip, depuis [PyPI](https://pypi.org/project/home-tcl-dashboard/) :

```sh
pip install home-tcl-dashboard
```

Dans le dossier d'où vous lancerez le serveur, créez un fichier `.env` avec
vos identifiants Grand Lyon :

```sh
GDL_USER=votre-identifiant
GDL_PWD=votre-mot-de-passe
```

Puis lancez :

```sh
home-tcl-dashboard     # http://localhost:8000, sur toutes les interfaces
```

Le serveur range ses données dans `data/`, dans le dossier courant, ou dans
le dossier donné par la variable d'environnement `TCL_DATA_DIR` :

| Fichier                | Contenu                                         |
|------------------------|-------------------------------------------------|
| `data/GTFS_TCL.ZIP`    | l'horaire (~24 Mo), téléchargé une fois par jour |
| `data/pictos/`         | les pictogrammes officiels des lignes, téléchargés une fois |
| `data/favourites.json` | les arrêts favoris                              |

Le premier démarrage télécharge l'horaire et les pictogrammes, il prend donc
un moment. Si Grand Lyon est en panne ensuite, le serveur continue avec ce
qu'il a déjà.

## La tablette

La cible est une vieille tablette Android avec **Firefox 68**. Ouvrez
`http://<serveur>:8000`, puis « Ajouter à l'écran d'accueil » pour avoir une
application en plein écran. L'affichage s'adapte à toutes les tailles
(conçu pour 1024x768, avec une mise en page portrait) et passe en thème nuit
de 20h à 7h.

À cause de Firefox 68, le frontend (`src/home_tcl_dashboard/static/`) est
en JavaScript simple, sans étape de compilation, et évite la syntaxe et les
API récentes : pas de `?.`, `??`, `replaceChildren`, `:has()`, ni de CSS
`min()`/`clamp()`.

## Développement

Le projet utilise [pixi](https://pixi.sh). Depuis la racine du dépôt :

```sh
pixi install
cp .env.example .env   # puis remplir GDL_USER et GDL_PWD
pixi run serve         # http://localhost:8000, rechargé à chaque modification
pixi run test          # pytest
pixi run lint          # ruff check
pixi run format-check  # ruff format --check
pixi run typecheck     # mypy
pre-commit install     # lance ruff à chaque commit
```

Organisation de `src/home_tcl_dashboard/` :

| Module          | Rôle                                                       |
|-----------------|------------------------------------------------------------|
| `app.py`        | l'application FastAPI : démarrage, routes `/api/*` (une ligne chacune), fichiers statiques |
| `dashboard.py`  | la classe `Dashboard` : l'état (réseau, horaire, caches, favoris) et ce que montre chaque écran |
| `grandlyon.py`  | la classe `GrandLyon` : le client de data.grandlyon.com (WFS, temps réel, alertes, GTFS, pictogrammes) |
| `network.py`    | lignes, quais, tracés et leur lecture                      |
| `gtfs.py`       | départs prévus et ordre des arrêts, tirés du GTFS          |
| `realtime.py`   | départs en temps réel                                      |
| `alerts.py`     | alertes trafic                                             |
| `board.py`      | les cartes et le bandeau de l'accueil                      |
| `cache.py`      | réutilise les réponses récentes de Grand Lyon, et les sert en cas de panne |
| `favourites.py` | lecture, écriture et validation des favoris                |
| `static/`       | le frontend                                                |

Trois couches :

- `app.py` ne parle que HTTP : il traduit les requêtes en appels au
  `Dashboard`, et ses exceptions (`NotFound`, `InvalidFavourites`) en
  erreurs 404 et 422.
- `Dashboard` ne connaît pas HTTP. Il reçoit l'heure (`now`) et le client
  Grand Lyon en paramètres, ce qui permet de le tester sans serveur ni
  réseau, avec un faux client (`tests/fakes.py`).
- Les autres modules sont des fonctions pures, que le `Dashboard` appelle.

### La démo

La démo est le même frontend, qui lit des réponses enregistrées dans `demo/`
au lieu d'appeler le serveur. Pour la rafraîchir, de préférence à une heure
de pointe :

```sh
pixi run python scripts/snapshot_demo.py   # quelques minutes
```

puis commitez `demo/`. Le workflow `pages.yml` republie la démo à chaque
fusion dans `main`. Elle n'utilise pas les pictogrammes officiels, dont la
licence de réutilisation n'est pas confirmée : elle dessine des badges qui
leur ressemblent.

### Publier une version

Créez une release sur GitHub, avec un tag de la forme `0.3.0` sur `main`. Le
workflow `publish.yml` construit le paquet et le publie sur PyPI : le numéro
de version vient du tag (hatch-vcs).

## Crédits

- Données : SYTRAL Mobilités, via [data.grandlyon.com](https://data.grandlyon.com).
- Cartes : [Leaflet](https://leafletjs.com) et les contributeurs
  d'[OpenStreetMap](https://www.openstreetmap.org/copyright).
- Police : [Inter](https://rsms.me/inter/), licence SIL Open Font License
  (`static/fonts/OFL.txt`).
