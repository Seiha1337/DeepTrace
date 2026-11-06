from .models import CollectorSpec

CATALOG = (
    CollectorSpec(
        "windows",
        "Windows",
        "Diagnostic Windows",
        "Identifier la version, la mémoire disponible et le dernier démarrage.",
        "Win32_OperatingSystem",
        (
            "Caption",
            "Version",
            "BuildNumber",
            "OSArchitecture",
            "TotalVisibleMemorySize",
            "FreePhysicalMemory",
            "LastBootUpTime",
        ),
        "Pas de contrôle SFC/DISM, ni de conclusion sur la prise en charge des mises à jour.",
    ),
    CollectorSpec(
        "hardware",
        "Processeur, mémoire et firmware",
        "Inventaire matériel",
        "Recenser les composants annoncés par Windows.",
        "Win32_Processor / PhysicalMemory / VideoController / BaseBoard / BIOS",
        (
            "Kind",
            "Name",
            "Manufacturer",
            "Capacity",
            "Speed",
            "Cores",
            "Threads",
            "DriverVersion",
            "Version",
        ),
        "Pas de mesure thermique, VRAM fiable ou détection de throttling dans cette version.",
    ),
    CollectorSpec(
        "volumes",
        "Espace des volumes",
        "Santé du stockage",
        "Mesurer l'espace libre des volumes fixes.",
        "Win32_LogicalDisk (DriveType=3)",
        ("DeviceID", "Size", "FreeSpace", "FileSystem"),
        "L'espace libre ne mesure pas la santé physique et les volumes réseau sont exclus.",
    ),
    CollectorSpec(
        "disks",
        "État déclaré des disques",
        "Santé du stockage",
        "Lire l'état résumé fourni par le pilote de stockage.",
        "Get-PhysicalDisk",
        ("MediaType", "BusType", "HealthStatus", "OperationalStatus", "Size"),
        "SMART/NVMe détaillé non disponible ; un état Healthy ne garantit pas l'absence de panne.",
    ),
    CollectorSpec(
        "performance",
        "Charge instantanée",
        "Performances",
        "Observer la charge CPU et les cinq processus avec le plus de mémoire résidente.",
        "Win32_Processor.LoadPercentage / Get-Process.WorkingSet64",
        ("Kind", "Name", "LoadPercentage", "WorkingSetBytes"),
        "Instantané : pas de benchmark, CPU par processus, charge GPU ou diagnostic de bottleneck.",
    ),
    CollectorSpec(
        "network",
        "Adaptateurs réseau",
        "Réseau",
        "Recenser l'état des interfaces sans trafic de test ni changement DNS.",
        "Get-NetAdapter",
        ("InterfaceDescription", "Status", "LinkSpeed"),
        "Pas d'IP, MAC, routes ou DNS collectés ; VPN et interfaces "
        "virtuelles ne sont pas anormaux.",
    ),
    CollectorSpec(
        "defender",
        "Protection Microsoft Defender",
        "Sécurité",
        "Lire l'état déclaré des protections Defender.",
        "Get-MpComputerStatus",
        (
            "AMServiceEnabled",
            "AntivirusEnabled",
            "RealTimeProtectionEnabled",
            "AntivirusSignatureLastUpdated",
        ),
        "Un antivirus tiers ou une politique peut expliquer un état "
        "désactivé ; pas de scan antivirus.",
    ),
    CollectorSpec(
        "firewall",
        "Profils du pare-feu",
        "Sécurité",
        "Lire l'activation des profils configurés.",
        "Get-NetFirewallProfile",
        ("Name", "Enabled"),
        "Un profil configuré n'est pas nécessairement le profil réseau actif.",
    ),
    CollectorSpec(
        "events",
        "Événements système récents",
        "Événements et incidents",
        "Lire au plus 50 erreurs/critiques des sept derniers jours.",
        "Get-WinEvent / System",
        ("Id", "ProviderName", "Level", "TimeCreated"),
        "Aucun message libre ni dump collecté. Kernel-Power 41 ne prouve pas une panne matérielle.",
        levels=("approfondie",),
        timeout=40,
    ),
    CollectorSpec(
        "drivers",
        "Pilotes signés déclarés",
        "Pilotes",
        "Lister jusqu'à 300 pilotes PnP et leur signature déclarée.",
        "Win32_PnPSignedDriver",
        ("DeviceName", "Manufacturer", "DriverVersion", "IsSigned"),
        "La signature déclarée ne constitue pas une validation cryptographique ; pas de base CVE.",
        levels=("approfondie",),
        timeout=40,
    ),
    CollectorSpec(
        "software",
        "Logiciels enregistrés",
        "Logiciels installés",
        "Lire jusqu'à 500 entrées de désinstallation sans lancer Windows Installer.",
        "Registre HKLM 64/32 bits et HKCU / Uninstall",
        ("DisplayName", "DisplayVersion", "Publisher"),
        "Liste partielle : applications portables/Store absentes ; aucune "
        "conclusion d'obsolescence.",
        levels=("approfondie",),
    ),
    CollectorSpec(
        "services",
        "Services Windows",
        "Diagnostic Windows",
        "Recenser jusqu'à 500 services, leur état et leur démarrage.",
        "Win32_Service",
        ("Name", "State", "StartMode"),
        "Un service arrêté peut être normal ; aucun chemin, compte ou "
        "argument de service collecté.",
        levels=("approfondie",),
    ),
)
BY_ID = {s.id: s for s in CATALOG}
SYMPTOMS = {
    "Ralentissements": ("windows", "hardware", "volumes", "performance", "services"),
    "BSOD / freeze": ("windows", "hardware", "disks", "events", "drivers"),
    "Crash de jeu": ("windows", "hardware", "performance", "events", "drivers"),
    "Panne réseau": ("network", "firewall", "events"),
    "Démarrage difficile": ("windows", "volumes", "disks", "events", "services"),
}


def select_collectors(level: str, symptom: str = "") -> list[CollectorSpec]:
    if level == "ciblée":
        if symptom not in SYMPTOMS:
            raise ValueError("Symptôme inconnu")
        return [BY_ID[key] for key in SYMPTOMS[symptom]]
    if level not in ("rapide", "approfondie"):
        raise ValueError("Niveau inconnu")
    return [s for s in CATALOG if level in s.levels]
