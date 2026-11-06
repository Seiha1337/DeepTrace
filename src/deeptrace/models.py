from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Status(StrEnum):
    OK = "terminé"
    UNAVAILABLE = "indisponible"
    ERROR = "erreur"
    TIMEOUT = "délai dépassé"
    CANCELLED = "annulé"


@dataclass(frozen=True)
class CollectorSpec:
    id: str
    title: str
    domain: str
    purpose: str
    source: str
    fields: tuple[str, ...]
    limitations: str
    levels: tuple[str, ...] = ("rapide", "approfondie")
    prerequisites: str = "Windows 11 x64, Windows PowerShell 5.1 et fournisseur disponible"
    privileges: str = "Utilisateur ; certaines informations peuvent être refusées"
    impact: str = "Faible ; requêtes locales en lecture seule"
    timeout: int = 25


@dataclass
class Finding:
    rule: str
    collector_id: str
    title: str
    observed: str
    interpretation: str
    hypothesis: str
    severity: str
    confidence: str
    evidence: dict
    confirmation: str
    recommendation: str
    optional_action: str = "Aucune intervention automatique."
    changes: str = "Aucune modification effectuée."
    risks: str = "Une mesure isolée ne suffit pas à établir une panne."
    protection: str = "Sauvegarder les fichiers importants avant toute réparation ultérieure."
    rollback: str = "Sans objet : contrôle en lecture seule."
    verification: str = "Relancer le contrôle et comparer les mesures dans le même contexte."


@dataclass
class CollectorResult:
    collector_id: str
    status: Status
    started_at: str = field(default_factory=utc_now)
    duration_ms: int = 0
    data: list[dict] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    error: str | None = None
    return_code: int | None = None


@dataclass
class Scan:
    level: str
    symptom: str = ""
    id: str = field(default_factory=lambda: str(uuid4()))
    started_at: str = field(default_factory=utc_now)
    finished_at: str | None = None
    results: list[CollectorResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict) -> "Scan":
        value = dict(value)
        value["results"] = [
            CollectorResult(
                **{k: v for k, v in r.items() if k not in ("status", "findings")},
                status=Status(r["status"]),
                findings=[Finding(**f) for f in r["findings"]],
            )
            for r in value["results"]
        ]
        return cls(**value)
