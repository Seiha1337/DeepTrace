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

- 79 tests locaux réussis sous Python stable 3.13.17, sortie normale du processus.
- Ruff lint et format réussis.
- Tests de consentement/persistance, sources réseau autorisées, taille/empreinte,
  annulation, remplacement, conservation de l'ancien binaire et retour arrière simulés.
- Cas de staging et programme sur deux disques différents couvert par le remplacement
  depuis un temporaire situé dans le dossier du programme.
- Les douze collecteurs ont été vérifiés en lecture seule sur le poste lors de V0.1.
- Historique Git avant publication : 80 versions de fichiers vérifiées, aucun motif bloquant.
- Rapports réels, historiques, journaux et outils téléchargés restent dans local/, ignoré.

Optimisation : les vues masquées sont calculées à leur ouverture et les vues inchangées
sont réutilisées. Sur ce poste, dix rafraîchissements avec 1 300 lignes synthétiques
passent de 782,7 ms à 71,0 ms. Ce microbenchmark mesure le coût du rafraîchissement,
pas un gain global garanti. Aucun sondage permanent de capteurs n'est lancé au repos.

L'analyse rapide du premier exécutable a terminé ses huit collecteurs avec code 0.
Un import interne Qt manquant au démarrage graphique a été identifié dans le hook
PyInstaller avec Essentials seul ; il est désormais explicitement inclus. Un journal
de démarrage sans message d'exception privé a également été ajouté. La validation
graphique finale porte sur le binaire reconstruit après cette correction.

Le diagnostic d'empaquetage a également révélé une DLL ICU d'un outil tiers collectée via
le `PATH` du poste. La construction isole désormais ce chemin, nettoie le cache dans le
projet et refuse les DLL hors des racines approuvées. Les tests de la source seuls ne
remplacent donc pas la vérification du binaire final.

Le binaire final de 39 473 806 octets a été ouvert et fermé normalement. Le helper réel
a remplacé et relancé une copie isolée du même binaire, avec sauvegarde de l'ancien
fichier et conservation du dossier de données. Ce test valide le mécanisme de remplacement,
sans prétendre simuler toutes les migrations entre versions futures.

Mesure au repos sur ce poste, analyse et vérification réseau désactivées : fenêtre prête
en 2 506 ms ; 0,0000 seconde CPU relevée sur dix secondes ; 55,5 Mio de mémoire privée
et 132,5 Mio de jeux résidents cumulés pour les deux processus du mode mono-fichier.
Les jeux résidents peuvent compter des pages partagées ; la mémoire privée est une
mesure différente. Ces chiffres sont ponctuels et ne garantissent pas une consommation
identique sur une autre machine ou pendant une analyse.

SHA-256 du binaire livré :
`c679e228236481433ba49e063fd31ffa9c190eba389fd84cadbad9f96c4bdae8`.

Qualification VM Windows propre, compte standard distinct,
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

La CI reste bloquée malgré le passage en public : “The job was not started because
your account is locked due to a billing issue.” Les deux jobs n'ont exécuté aucune étape.
Les protections restent actives : la PR demeure sans fusion jusqu'au déblocage de CI.
Un binaire construit et vérifié localement peut être livré avec cette limite indiquée.
