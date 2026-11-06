# État de livraison — 6 novembre 2026

## Décisions et livrables

V0.1.0 : application Qt native en français, 12 collecteurs Windows en lecture seule,
cinq règles, analyses rapide/approfondie/ciblée, historique SQLite et comparaison,
exports filtrés, plan simulé et centre pédagogique de protection. Aucun outil IA.
Les détails fonctionnels et les limites sont dans le README et la roadmap.

## Vérifications acquises

- 37 tests pytest réussis, sortie du processus 0, dont tests Qt hors écran.
- Les 12 collecteurs réels ont terminé avec code retour 0 sur le poste Windows.
- Capture native de l'écran initial vérifiée visuellement, sans donnée de diagnostic.
- Paquets wheel et archive source construits ; scripts PowerShell inclus dans la wheel.
- Aucun changement de configuration Windows, réparation, restauration ou stress test.

Les rapports réels, historiques et journaux restent dans `local/`, exclus du dépôt.
Python du poste : 3.11.0rc2 ; Qt Essentials : 6.12.0. Python stable reste recommandé.

## Qualification restante

VM Windows propre, compte standard distinct, accessibilité assistée, capteurs,
sauvegardes réelles, restauration, helper privilégié et installateur Windows signé.
Les paramètres sont propres à la session ; l'historique n'a pas de purge automatique.
Prochain objectif : qualifier la V0.1 sur une VM Windows puis développer les mesures
temporelles et l'approfondissement diagnostique de V0.2.

## GitHub

La création privée, la CI distante et l'application des protections sont vérifiées
séparément en fin de livraison ; leur résultat est consigné ci-dessous après vérification.
