# Stratégie de test

## Automatique, sans réparation Windows

`pytest` vérifie la sélection du catalogue, les données Windows synthétiques, les seuils
et valeurs manquantes, l'absence d'interprétation d'un contrôle échoué, l'isolation des
échecs, l'annulation, la progression, la persistance SQLite, la comparaison, les simulations,
le filtrage HTML/JSON et les erreurs de droits/timeout simulées du runner.
Les tests Qt utilisent la plateforme `offscreen` ; un timer démontre que la boucle UI
continue pendant un collecteur lent. Les fenêtres sont détruites explicitement avant Qt.

Les appels PowerShell des tests unitaires sont remplacés par des objets simulés.
Aucun stress test, changement de registre, réparation, restauration ou outil privilégié.
Les tests de protections se limitent au plan simulé et à sa journalisation ; aucune
fonction réelle de sauvegarde n'existe encore à tester.

## Vérifications manuelles reproductibles

```powershell
python -m deeptrace --scan approfondie --data-dir local\qualification --output local\qualification.json
python tools\capture_ui.py
python -m build --no-isolation
```

Une analyse réelle est une action explicite en lecture seule ; ses résultats sont ignorés
par Git. Vérifier codes de retour, listes structurées, absence de données privées exportées.
Ne pas interpréter un succès de collecte comme une validation de la santé du poste.

## Qualification initiale du 6 novembre 2026

- Poste Windows réel : les 12 collecteurs ont terminé avec code retour 0 hors bac à sable.
- Dans le bac à sable, CIM et certains fournisseurs sont inaccessibles ; les contrôles
  échouent sans interrompre les suivants. Ce contexte ne valide pas les sources réelles.
- Qt : navigation, analyse en arrière-plan et historique vérifiés automatiquement.
- Un défaut de nettoyage des fenêtres de test causait une erreur à la sortie du processus ;
  la destruction explicite des widgets a corrigé le défaut observé.
- Les totaux définitifs des tests, du lint, du build et de CI figurent dans `STATUS.md`.
- Paquet installé hors mode éditable dans un environnement neuf avec seulement Essentials :
  interface ouverte puis fermée normalement, import confirmé depuis `site-packages`.
- La CI GitHub est configurée mais non exécutée : blocage de facturation/plafond du compte,
  confirmé par l'annotation de l'exécution initiale. Les validations locales ne sont pas
  présentées comme une réussite de CI distante.

## Non qualifié

VM Windows propre, Windows avec fournisseur manquant, compte standard distinct,
Windows géré par domaine, lecteurs d'écran, fort DPI et scénarios multimoniteurs.
La matrice CI Windows/Linux ne remplace pas ces essais. Aucun test de récupération réelle,
capteur thermique, panne physique injectée ni exécutable Windows signé.
Des tests VM seront nécessaires avant toute intervention privilégiée.
