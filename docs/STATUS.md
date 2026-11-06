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
- Wheel réinstallée dans un environnement neuf avec uniquement Qt Essentials et shiboken6 :
  import depuis `site-packages`, ouverture des 14 vues, fermeture normale avec code 0.
- Ruff (lint et format), contrôle de publication et `git diff --check` réussis.
- 52 fichiers initiaux contrôlés avant publication, aucun motif bloquant ni rapport privé suivi.
- Aucun changement de configuration Windows, réparation, restauration ou stress test.

Les rapports réels, historiques et journaux restent dans `local/`, exclus du dépôt.
Python du poste : 3.11.0rc2 ; Qt Essentials : 6.12.0. Python stable reste recommandé.

## Qualification restante

VM Windows propre, compte standard distinct, accessibilité assistée, capteurs,
sauvegardes réelles, restauration, helper privilégié et installateur Windows signé.
Les paramètres sont propres à la session ; l'historique n'a pas de purge automatique.
Prochain objectif : qualifier la V0.1 sur une VM Windows puis développer les mesures
temporelles et l'approfondissement diagnostique de V0.2.

## GitHub : état vérifié

- Dépôt privé : https://github.com/Seiha1337/DeepTrace ; branche principale `master`.
- Commit fondateur : `4c469d26e94bbc36a7bff18cdfa5e02898fcb36f`.
- Workflow CI Windows/Linux publié et reconnu par GitHub.
- [Exécution initiale](https://github.com/Seiha1337/DeepTrace/actions/runs/42271009425) :
  `startup_failure`, aucun job exécuté. L'annotation de l'interface GitHub indique :
  “The job was not started because recent account payments have failed or your spending
  limit needs to be increased.” Aucune modification de facturation effectuée.
- Protection de `master` : API refusée avec HTTP 403, “Upgrade to GitHub Pro or make
  this repository public to enable this feature.” Le dépôt reste privé, sans protection
  de branche native ; l'offre du compte doit permettre cette fonction avant son activation.
- Secret scanning et push protection natifs : API refusée avec HTTP 422,
  “Secret scanning is not available for this repository.” Contrôle local/CI maintenu,
  sans le présenter comme équivalent à la protection native de GitHub.
- Suppression automatique des branches après fusion activée.

La branche `dev/validation-v0.1` conserve le bilan de qualification et les ajustements
de livraison : nettoyage explicite des widgets à la fermeture de l'application et rejet
des nombres JSON non finis, y compris les exposants débordants. Ces changements sont
vérifiés localement. Aucune fusion de cette branche avant disponibilité et réussite de la CI.
Après résolution du blocage du compte : relancer la CI, vérifier Windows/Linux,
puis appliquer les protections si l'offre le permet et traiter la PR de validation.
