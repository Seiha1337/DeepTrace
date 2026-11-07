# État de livraison — 7 novembre 2026

## V0.1.1

Exécutable portable Windows x64, Python stable 3.13.17 et Qt Essentials 6.12.0 embarqués.
Aucun Python à installer, aucun droit administrateur demandé. Diagnostics en lecture
seule, sans réparation ni restauration réelle.

Améliorations : résumé du PC, filtres alertes/contrôles non aboutis, recherche dans
les observations, début de chaque contrôle affiché, fermeture différée pendant une
analyse, préférences SQLite persistantes, historique validé et migration non destructive,
rapports pédagogiques filtrés avec écriture atomique.

## Mises à jour

Après consentement initial, recherche au démarrage dans les Releases publiques officielles,
téléchargement en arrière-plan, vérification SHA-256, attente des analyses et redémarrage.
Option désactivable, fonctionnement du diagnostic toujours local et hors connexion.
Le helper conserve l'ancien exécutable et annule un remplacement ou lancement échoué.
Il ne détecte pas un crash ultérieur. Les binaires ne sont pas signés Authenticode.

## Vérifications acquises

- 77 tests locaux réussis sous Python stable 3.13.17, sortie normale du processus.
- Ruff lint et format réussis.
- Tests de consentement/persistance, sources réseau autorisées, taille/empreinte,
  annulation, remplacement, conservation de l'ancien binaire et retour arrière simulés.
- Cas de staging et programme sur deux disques différents couvert par le remplacement
  depuis un temporaire situé dans le dossier du programme.
- Les douze collecteurs ont été vérifiés en lecture seule sur le poste lors de V0.1.
- Historique Git avant publication : 80 versions de fichiers vérifiées, aucun motif bloquant.
- Rapports réels, historiques, journaux et outils téléchargés restent dans local/, ignoré.

La construction finale, la vérification de l'exécutable et la CI de cette livraison sont
consignées après leur exécution. Qualification VM Windows propre, compte standard distinct,
accessibilité assistée, installateur signé et sauvegardes réelles restent à réaliser.

## GitHub

[DeepTrace](https://github.com/Seiha1337/DeepTrace) est public avec l'historique existant,
conformément à la confirmation de l'utilisateur. Branche principale : master.
Les protections imposent une PR, les deux validations Windows/Linux à jour, la résolution
des discussions, l'interdiction du force-push/suppression et s'appliquent aux administrateurs.
Secret scanning et push protection natifs sont désormais activés.

La livraison est préparée sur dev/windows-executable à partir des fondations V0.1 et
des corrections de dev/validation-v0.1. La CI construit et conserve les binaires Windows.
Un tag vX.Y.Z, après validation, publie une Release contenant DeepTrace.exe et
SHA256SUMS.txt. Aucun nouveau binaire n'est publié sur la simple ouverture d'une PR.
