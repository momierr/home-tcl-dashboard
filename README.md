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

Ouvrez ensuite `http://<serveur>:8000` sur n'importe quel appareil du
réseau. Sur une tablette ou un téléphone, « Ajouter à l'écran d'accueil »
l'ouvre en plein écran, comme une application. L'affichage s'adapte à la
taille de l'écran et passe en thème nuit de 20h à 7h.

## Crédits

- Données : SYTRAL Mobilités, via [data.grandlyon.com](https://data.grandlyon.com).
- Cartes : [Leaflet](https://leafletjs.com) et les contributeurs
  d'[OpenStreetMap](https://www.openstreetmap.org/copyright).
- Police : [Inter](https://rsms.me/inter/), licence SIL Open Font License
  (`static/fonts/OFL.txt`).
