"""Aucune API d'exécution d'intervention réelle dans la V0.1."""

from dataclasses import asdict, dataclass

from .models import utc_now


@dataclass(frozen=True)
class Operation:
    id: str
    title: str
    justification: str
    conditions: str
    privileges: str
    resources: str
    changes: str
    risks: str
    side_effects: str
    reboot: str
    prechecks: str
    protection: str
    verification: str
    rollback: str
    limitations: str


OPERATIONS = {
    "storage_review": Operation(
        "storage_review",
        "Préparer une revue de l'espace disque",
        "Une alerte d'espace libre peut justifier une inspection manuelle.",
        "Disposer d'une analyse récente et identifier le volume concerné.",
        "Aucun en simulation ; à réévaluer pour une opération réelle.",
        "Volume à identifier manuellement ; aucun fichier inspecté ou sélectionné.",
        "Simulation uniquement : aucune suppression, aucun changement de configuration.",
        "Une future suppression pourrait entraîner une perte de données.",
        "Aucun effet système dans cette simulation.",
        "Aucun redémarrage.",
        "Confirmer le volume, l'espace libre absolu et l'origine des données.",
        "Sauvegarde indépendante vérifiée nécessaire avant toute suppression ultérieure.",
        "Pour une opération réelle : comparer l'espace libre et contrôler les applications.",
        "Simulation : rien à annuler. Suppression future : restauration de sauvegarde nécessaire.",
        "Ce plan n'identifie aucun fichier supprimable et ne démontre aucune récupérabilité.",
    ),
}


def simulate(operation_id: str, scan_id: str | None) -> dict:
    operation = OPERATIONS[operation_id]
    if not scan_id:
        raise ValueError("Une analyse doit être sélectionnée pour contextualiser la simulation.")
    return {
        "created_at": utc_now(),
        "operation": operation.id,
        "scan_id": scan_id,
        "state_before": "Analyse sélectionnée ; aucun contrôle système supplémentaire.",
        "state": "simulée",
        "state_after": "Aucune modification système.",
        "protections": "Aucune sauvegarde créée ou déclarée vérifiée.",
        "errors": [],
        "plan": asdict(operation),
    }


PROTECTIONS = {
    "Image système complète": (
        "Copie des volumes nécessaires au démarrage. Prévoir un support physique indépendant, "
        "la capacité, un média de récupération et les clés BitLocker conservées hors du PC. "
        "Une image n'est déclarée récupérable qu'après vérification adaptée et, si possible, "
        "un essai de restauration isolé. Création et restauration non implémentées en V0.1."
    ),
    "Point de restauration": (
        "Protège certains fichiers système et configurations ; ne sauvegarde pas les fichiers "
        "personnels et ne remplace pas une image. Disponibilité, quotas et résultat Windows "
        "doivent être vérifiés. Création et restauration non implémentées en V0.1."
    ),
    "Sauvegarde de fichiers": (
        "Copie indépendante de fichiers choisis. Vérifier les empreintes puis tester une lecture "
        "et une restauration dans un dossier isolé. Ne rend pas Windows amorçable. "
        "Assistant de copie et restauration prévu en V0.3."
    ),
    "Sauvegarde de configuration": (
        "Export ciblé avec schéma et procédure inverse validée. Peut contenir des secrets et "
        "nécessite une protection adaptée. Aucune configuration exportée dans cette version."
    ),
    "Journal des interventions": (
        "DeepTrace journalise localement les simulations. Un journal explique ce qui a été "
        "prévu ; il ne sauvegarde ni les fichiers ni le système. Les simulations sont visibles "
        "dans l'historique. Aucune réparation réelle disponible."
    ),
}
