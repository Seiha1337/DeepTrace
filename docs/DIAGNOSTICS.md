# Diagnostics et règles

Chaque collecteur est décrit exhaustivement dans `src/deeptrace/catalog.py` et son
script se trouve dans `src/deeptrace/scripts/`. Les requêtes sont strictement locales.

| Identifiant | Source | Niveaux | Plafond |
|---|---|---|---|
| windows | Win32_OperatingSystem | rapide, approfondie | 25 s |
| hardware | CPU, PhysicalMemory, VideoController, BaseBoard, BIOS | rapide, approfondie | 25 s |
| volumes | Win32_LogicalDisk, volumes fixes | rapide, approfondie | 25 s |
| disks | Get-PhysicalDisk | rapide, approfondie | 25 s |
| performance | Win32_Processor, Get-Process | rapide, approfondie | 25 s |
| network | Get-NetAdapter | rapide, approfondie | 25 s |
| defender | Get-MpComputerStatus | rapide, approfondie | 25 s |
| firewall | Get-NetFirewallProfile | rapide, approfondie | 25 s |
| events | Get-WinEvent, System, 7 jours, 50 événements | approfondie | 40 s |
| drivers | Win32_PnPSignedDriver, 300 éléments | approfondie | 40 s |
| software | Registre Uninstall, 500 éléments au total | approfondie | 25 s |
| services | Win32_Service, 500 éléments | approfondie | 25 s |

Le délai de session est limité aussi par ce plafond. Les investigations ciblées sélectionnent
une liste explicite dans `SYMPTOMS` ; elles n'exécutent pas un diagnostic issu de texte libre.
Un inventaire matériel échouant sur un fournisseur est marqué en erreur, sans prétendre
que son inventaire partiel est complet.

## Interprétation

- `volume.low_space` : `0 <= FreeSpace <= Size`, `Size > 0`, ratio strictement inférieur à 0,10.
  Confiance élevée sur l'instantané ; volume rempli et panne physique ne sont pas équivalents.
- `memory.pressure` : même seuil sur `FreePhysicalMemory / TotalVisibleMemorySize`.
  Instantané unique ; pas de fuite ou de manque permanent de RAM démontré.
- `disk.reported_warning` : état exact `Warning` ou `Unhealthy`. Vérifier avec le fabricant
  et sauvegarder ; aucune certitude de panne déduite.
- `firewall.disabled_profile` : booléen `Enabled == False`. Ne prouve pas que le profil est actif.
- `defender.realtime_off` : booléen `RealTimeProtectionEnabled == False`.
  Contrôler le fournisseur actif ; un antivirus tiers est une explication possible.

Les seuils de 10 % servent à attirer l'attention, sans prédire une panne ni quantifier un gain.
Pas de règle sur les logiciels obsolètes, vulnérabilités, processus inconnus ou ports ouverts.
Pas de diagnostic matériel sur un ID d'événement isolé. Pas de capteur inventé.

Les résultats distinguent fait, interprétation, hypothèse, gravité, confiance, preuves,
confirmation, recommandation, action facultative, changements, risques, protection,
retour arrière et vérification. « Aucune alerte » reste limité aux règles implémentées.

## Références primaires

- [Qt : QThread et signaux](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QThread.html)
- [Microsoft : Get-PhysicalDisk](https://learn.microsoft.com/en-us/powershell/module/storage/get-physicaldisk)
- [Microsoft : Win32_OperatingSystem](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-operatingsystem)
- [Microsoft : Get-MpComputerStatus](https://learn.microsoft.com/en-us/powershell/module/defender/get-mpcomputerstatus)

Ces sources documentent les APIs, pas les seuils heuristiques de DeepTrace.
