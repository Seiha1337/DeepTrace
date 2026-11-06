"""Règles déterministes, seuils documentés et preuves conservées."""

from .models import CollectorResult, Finding, Status


def number(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def interpret(result: CollectorResult) -> list[Finding]:
    if result.status != Status.OK:
        return []
    findings = []
    for row in result.data:
        if result.collector_id == "volumes":
            size, free = number(row.get("Size")), number(row.get("FreeSpace"))
            if size and free is not None and 0 <= free <= size and free / size < 0.1:
                findings.append(
                    Finding(
                        "volume.low_space",
                        result.collector_id,
                        "Espace libre inférieur à 10 %",
                        f"{row.get('DeviceID', 'Volume')} : {free / size:.1%} d'espace libre.",
                        "L'espace disponible peut limiter les mises à jour et les "
                        "fichiers temporaires.",
                        "Accumulation de données possible ; la cause n'est pas déterminée.",
                        "attention",
                        "élevée pour la mesure, faible pour la cause",
                        dict(row),
                        "Contrôler la capacité absolue et l'évolution de l'espace disponible.",
                        "Examiner les fichiers avec les paramètres Stockage de Windows.",
                        risks="Ne supprimer aucun fichier sans identifier son usage.",
                    )
                )
        elif result.collector_id == "windows":
            total = number(row.get("TotalVisibleMemorySize"))
            free = number(row.get("FreePhysicalMemory"))
            if total and free is not None and 0 <= free <= total and free / total < 0.1:
                findings.append(
                    Finding(
                        "memory.pressure",
                        result.collector_id,
                        "Mémoire disponible inférieure à 10 %",
                        f"{free / total:.1%} de mémoire physique disponible à cet instant.",
                        "Une faible marge mémoire peut provoquer de la pagination et des "
                        "ralentissements.",
                        "Charge temporaire possible ; aucune fuite mémoire n'est démontrée.",
                        "attention",
                        "moyenne : instantané unique",
                        dict(row),
                        "Répéter la mesure pendant le ralentissement et examiner le "
                        "Gestionnaire des tâches.",
                        "Identifier les applications consommatrices avant de les fermer "
                        "manuellement.",
                    )
                )
        elif result.collector_id == "disks" and row.get("HealthStatus") in ("Warning", "Unhealthy"):
            findings.append(
                Finding(
                    "disk.reported_warning",
                    result.collector_id,
                    "Alerte déclarée par le stockage",
                    f"Le fournisseur Windows annonce {row['HealthStatus']}.",
                    "Le pilote signale une anomalie qui mérite une vérification indépendante.",
                    "Dégradation ou problème du fournisseur possibles ; panne non confirmée.",
                    "importante",
                    "moyenne",
                    dict(row),
                    "Consulter l'outil du fabricant et les journaux avant de conclure.",
                    "Vérifier une sauvegarde indépendante des fichiers importants.",
                )
            )
        elif result.collector_id == "firewall" and row.get("Enabled") is False:
            findings.append(
                Finding(
                    "firewall.disabled_profile",
                    result.collector_id,
                    "Profil du pare-feu désactivé",
                    f"Le profil {row.get('Name', 'inconnu')} est configuré désactivé.",
                    "La protection peut être réduite si ce profil est actif et sans "
                    "protection équivalente.",
                    "Une politique ou un pare-feu tiers peut expliquer cette configuration.",
                    "attention",
                    "élevée pour la configuration, faible pour l'exposition",
                    dict(row),
                    "Vérifier le profil actif et la protection tierce avec l'administrateur.",
                    "Examiner la configuration ; ne pas modifier une politique gérée "
                    "sans validation.",
                )
            )
        elif result.collector_id == "defender" and row.get("RealTimeProtectionEnabled") is False:
            findings.append(
                Finding(
                    "defender.realtime_off",
                    result.collector_id,
                    "Protection temps réel Defender inactive",
                    "Defender annonce une protection temps réel inactive.",
                    "Cette observation seule ne prouve pas l'absence de protection antivirus.",
                    "Antivirus tiers, mode passif ou stratégie possibles.",
                    "attention",
                    "élevée pour l'état Defender, faible pour la cause",
                    dict(row),
                    "Consulter Sécurité Windows et vérifier le fournisseur antivirus actif.",
                    "Vérifier la couverture antivirus ; aucune activation automatique proposée.",
                )
            )
    return findings
