# home-tcl-dashboard

Un tableau de bord mural des prochains départs TCL (transports en commun de
Lyon) pour les arrêts que vous utilisez, servi par un serveur à la maison et
affiché en plein écran sur une tablette.

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

## Prérequis

- [pixi](https://pixi.sh)
- Un compte gratuit [data.grandlyon.com](https://data.grandlyon.com) avec
  accès aux jeux de données TCL (le temps réel et les alertes demandent un
  identifiant).

## Installation

```sh
pixi install
cp .env.example .env   # puis remplir GDL_USER et GDL_PWD
pixi run serve         # http://localhost:8000
```

Lancez le serveur depuis la racine du dépôt : il range ses données dans
`data/` (ignoré par git) :

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

```sh
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

Plus de détails dans [docs/architecture.md](docs/architecture.md).

## Crédits

- Données : SYTRAL Mobilités, via [data.grandlyon.com](https://data.grandlyon.com).
- Cartes : [Leaflet](https://leafletjs.com) et les contributeurs
  d'[OpenStreetMap](https://www.openstreetmap.org/copyright).
- Police : [Inter](https://rsms.me/inter/), licence SIL Open Font License
  (`static/fonts/OFL.txt`).
