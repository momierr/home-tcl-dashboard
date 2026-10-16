# Maintenance

Notes pour qui maintient le projet. L'installation et l'organisation du
code sont décrites dans le [README](README.md).

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
