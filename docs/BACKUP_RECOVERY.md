# Protection et récupération

État V0.1 : centre pédagogique et simulation uniquement. Aucun bouton ne crée de
sauvegarde ni ne restaure le système. Aucune sauvegarde de la machine de développement
n'a été créée ou déclarée récupérable par DeepTrace.

| Mécanisme | Ce qu'il protège | Ce qu'il ne démontre pas |
|---|---|---|
| Image système | Volumes système sélectionnés et état capturé | Démarrage possible sans essai adapté |
| Point de restauration | Certains fichiers système et configurations | Conservation des fichiers personnels |
| Copie de fichiers | Fichiers explicitement sélectionnés | Récupération de Windows |
| Export de configuration | Paramètres ciblés et versionnés | Restauration correcte sans procédure testée |
| Journal d'intervention | Traçabilité des plans et résultats | Existence d'une copie des données |

## Exigences pour V0.3

1. Identifier source et cible, vérifier la capacité et l'indépendance physique du support.
2. Expliquer périmètre, exclusions, chiffrement et conservation avant consentement.
3. Employer un outil explicitement pris en charge et vérifier son code retour.
4. Vérifier les fichiers/manifeste et la cohérence des empreintes lorsque applicable.
5. Préparer un média de récupération et documenter les clés de chiffrement nécessaires.
6. Tester une récupération dans un dossier isolé ou une VM adaptée, sans écraser la source.
7. Distinguer « créée », « vérifiée » et « restauration testée » ; ne pas les fusionner.

Pour les points de restauration : contrôler configuration, disponibilité, quotas et
limitations Windows ; vérifier le point après création. L'échec doit empêcher toute
opération dont cette protection est un préalable obligatoire.

## Retour arrière futur

Chaque opération devra définir ses ressources exactes, sauvegardes, vérifications,
effets secondaires, redémarrage et limites de réversibilité. Une restauration nécessite
une confirmation explicite portant sur la source et la destination concrètes.
Les tests automatiques de restauration ne devront viser que des données synthétiques
dans un espace isolé. Une sauvegarde non testée ne sera jamais annoncée récupérable.
