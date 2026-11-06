# Sécurité et confidentialité

## Frontières de confiance

L'utilisateur choisit un niveau, un symptôme prédéfini et un délai entier. Ces valeurs
ne sont jamais interpolées dans les scripts. Le runner résout PowerShell dans System32,
utilise une liste d'arguments sans shell, `-NoProfile`, `-NonInteractive` et un script fixe
encodé en UTF-16LE. L'encodage assure le transport, pas une protection cryptographique.
La politique d'exécution Windows n'est pas modifiée. Le programme n'élève pas ses droits.

Les scripts sont un élément de confiance du paquet ; toute modification locale doit
être examinée comme une modification de code. Un attaquant ayant les droits d'écriture
sur l'installation peut altérer ce code ; aucun confinement supplémentaire n'est promis.
Les commandes WMI/Storage peuvent solliciter Windows malgré leur nature en lecture seule.

## Données

Ne pas ajouter de collecte de secrets, argument de processus, message d'événement,
chemin utilisateur, numéro de série, IP ou MAC sans nouvelle revue de confidentialité.
Les erreurs Windows brutes sont volontairement écartées, le code de retour reste visible.
Les sorties JSON sont bornées après réception et validées par liste blanche de champs.
Les collecteurs plafonnent leurs listes. Le processus PowerShell n'est pas isolé en mémoire
par un Job Object ; la limite de taille JSON n'est pas une limite d'allocation du processus.

Le stockage local dépend des permissions du dossier et de Windows ; pas de chiffrement
applicatif. Ne pas choisir un dossier partagé pour `--data-dir`. DeepTrace n'ajuste pas
automatiquement les ACL. Aucun trafic réseau n'est initié par le code applicatif ; les
fournisseurs Windows peuvent conserver leur propre comportement de service.

Les exports excluent les données brutes, horodatages et identifiants d'analyse. Une synthèse
révèle cependant des domaines contrôlés et des alertes : examiner aussi cette information
avant partage. HTML échappé, aucune ressource distante, scripts interdits par CSP.
L'historique utilise des requêtes paramétrées et ne sert pas de source de code exécutable.

## Interventions et protections

Aucune restauration, réparation, suppression système, désactivation de protection,
installation de pilote ou configuration réseau n'est implémentée. La seule API publique
d'intervention s'appelle `simulate` et n'appelle ni shell ni outil système.
Le centre de protection ne prétend créer aucune sauvegarde.

## Dépôt et signalement

Le contrôle `tools/check_repository.py` bloque les principaux formats privés et motifs
de secrets dans les fichiers suivis. C'est une défense complémentaire, pas une garantie
d'absence de secret. Les bases, rapports, logs, dumps, clés et sauvegardes sont ignorés.
La CI utilise des permissions `contents: read`, vérifie les dépendances verrouillées,
les tests et le code. Les protections GitHub dépendent des fonctionnalités du compte ;
leur état réel doit figurer dans le bilan de livraison et non être supposé.

Signaler une vulnérabilité par le canal privé du dépôt si disponible. Ne jamais poster
de secrets, base SQLite, log privé ou dump dans une issue. Retirer/révoquer un secret
exposé avant de discuter de son remplacement.
