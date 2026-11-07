# Développement

Installer comme indiqué dans le README. Pour une application sans outils de développement,
`pip install .` installe seulement Qt Essentials et ses dépendances. Le fichier verrouillé
sert à reproduire les contrôles du dépôt. Python stable recommandé ; le poste initial
dispose de Python 3.11.0rc2, ce qui reste une limite de qualification.

## Branches et versions

Branche principale `master`. Avant chaque travail : `git fetch origin`, vérifier l'état
local, partir du `origin/master` le plus récent sans écraser les modifications existantes.
Branches `dev/...`, `feat/...` ou `fix/...`, PR avec tests réussis. Pas de force-push sur master.
SemVer : `0.x` pour les versions préalables à la stabilité, changelog à chaque livraison.
Une version modifiée de collecteur requiert une revue de sa portée et des données collectées.

## Ajouter un collecteur

1. Décrire son contrat et ses limitations dans `catalog.py`.
2. Ajouter un script fixe en lecture seule avec projections de champs minimales.
3. Définir les données mesurées et les indisponibilités sans remplacer les absences par zéro.
4. Ajouter des fixtures synthétiques, tests d'échec, de droits et de délai pertinents.
5. Ajouter une règle uniquement si elle dispose d'une justification et de preuves.
6. Vérifier le filtrage des exports et mettre à jour la documentation.

Ne pas utiliser `Win32_Product` pour inventorier les logiciels (effets Windows Installer).
Ne pas accepter une commande libre, un chemin de script ou une réparation générée.
Ne jamais ajouter de test qui répare Windows ou modifie les protections du poste.

## Packaging

`python -m build --no-isolation` produit wheel et archive source. Les scripts `.ps1`
font partie des données du paquet. Vérifier le paquet dans un environnement neuf,
pas seulement l'installation éditable. L'exécutable portable et les mises à jour via
Releases sont implémentés en V0.1.1. Signature Authenticode et installateur restent à développer.

Pour construire `DeepTrace.exe` avec un Python Windows x64 **stable** :

```powershell
python -m pip install -r requirements-windows-build.lock
./tools/build_windows.ps1 -Python (Get-Command python).Source
```

Le script produit aussi `SHA256SUMS.txt`. Un tag `vX.Y.Z` correspondant à la version
du code déclenche les validations Windows/Linux, la construction et la Release GitHub.

Le script isole `PATH`, utilise un cache local nettoyé et le `.spec` refuse les bibliothèques
natives hors du runtime Python, du projet et de Windows. Cette isolation évite de collecter
une DLL incompatible d'un autre logiciel installé sur le poste de construction.
`PySide6.support.deprecated` est inclus explicitement car le hook amont teste les
métadonnées du méta-paquet PySide6, absent quand Essentials seul est installé.

`python tools/capture_ui.py` capture l'écran initial réel sans exécuter de diagnostic.
`python tools/check_repository.py` vérifie les fichiers suivis avant publication.
Les résultats de qualification restent dans `docs/TESTING.md` et le résumé `docs/STATUS.md`.
