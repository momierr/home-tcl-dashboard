# Contribuer

Notes pour qui développe ou maintient le projet. L'installation pour
l'utiliser est décrite dans le [README](README.md).

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

## Le frontend et Firefox 68

L'écran d'origine est une vieille tablette Android sous Firefox 68. Le
frontend (`src/home_tcl_dashboard/static/`) est donc en JavaScript simple,
sans étape de compilation, et évite la syntaxe et les API récentes : pas de
`?.`, `??`, `replaceChildren`, `:has()`, ni de CSS `min()`/`clamp()`.

## Rafraîchir la démo

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

## Publier une version

Créez une release sur GitHub, avec un tag de la forme `0.3.0` sur `main`. Le
workflow `publish.yml` construit le paquet et le publie sur PyPI : le numéro
de version vient du tag (hatch-vcs).
