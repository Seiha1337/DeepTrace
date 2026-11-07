"""Rapport pédagogique par liste blanche, sans données ou preuves brutes."""

import html
import json
import os
import tempfile
from pathlib import Path

from . import __version__
from .catalog import BY_ID
from .models import CollectorResult, Scan, Status
from .rules import interpret

# Les explications proviennent des mêmes règles que l'interface, sur des entrées fixes.
# Aucune chaîne d'un Finding chargé depuis l'historique n'est copiée dans le rapport.
_EXAMPLES = {
    "volumes": {"DeviceID": "Volume", "Size": 100, "FreeSpace": 5},
    "windows": {"TotalVisibleMemorySize": 100, "FreePhysicalMemory": 5},
    "disks": {"HealthStatus": "Warning"},
    "firewall": {"Enabled": False},
    "defender": {"RealTimeProtectionEnabled": False},
}
_EXPLANATIONS = {
    finding.rule: finding
    for collector, row in _EXAMPLES.items()
    for finding in interpret(CollectorResult(collector, Status.OK, data=[row]))
}
_PUBLIC_FIELDS = {
    "title": "Observation à examiner",
    "interpretation": "Effet possible",
    "hypothesis": "Hypothèse et limites",
    "severity": "Gravité de triage",
    "confidence": "Confiance",
    "confirmation": "Vérifications complémentaires",
    "recommendation": "Action recommandée",
    "optional_action": "Action facultative",
    "changes": "Modifications effectuées",
    "risks": "Risques",
    "protection": "Protection nécessaire",
    "rollback": "Retour arrière",
    "verification": "Vérification après intervention",
}
_STATUS_EXPLANATIONS = {
    Status.OK: "Requête terminée ; cela ne garantit pas l'absence de problème.",
    Status.UNAVAILABLE: "Donnée absente ou accès non disponible ; aucune conclusion possible.",
    Status.ERROR: "Le contrôle a échoué ; ses données ne permettent pas de conclure.",
    Status.TIMEOUT: "Le délai maximal a été dépassé ; aucun résultat partiel interprété.",
    Status.CANCELLED: "Contrôle annulé ; aucune mesure obtenue pour cette étape.",
}


def public_report(scan: Scan) -> dict:
    collectors = []
    for result in scan.results:
        if result.collector_id not in BY_ID:
            continue
        spec = BY_ID[result.collector_id]
        findings = []
        for finding in result.findings:
            explanation = _EXPLANATIONS.get(finding.rule)
            if (
                result.status != Status.OK
                or explanation is None
                or explanation.collector_id != result.collector_id
            ):
                continue
            findings.append(
                {
                    "rule": explanation.rule,
                    **{key: getattr(explanation, key) for key in _PUBLIC_FIELDS},
                }
            )
        collectors.append(
            {
                "id": spec.id,
                "title": spec.title,
                "purpose": spec.purpose,
                "status": result.status.value,
                "status_explanation": _STATUS_EXPLANATIONS[result.status],
                "duration_ms": result.duration_ms,
                "return_code": result.return_code,
                "row_count": len(result.data),
                "findings": findings,
                "omitted_findings": len(result.findings) - len(findings),
                "source": spec.source,
                "limitations": spec.limitations,
            }
        )
    return {
        "application": f"DeepTrace {__version__}",
        "format_version": 2,
        "level": scan.level if scan.level in ("rapide", "approfondie", "ciblée") else "inconnu",
        "privacy": "Synthèse filtrée : aucune donnée brute ou identification de machine exportée. "
        "Les preuves détaillées restent dans l'application locale.",
        "limitations": "Aucune réparation réalisée. Un contrôle terminé ne garantit pas "
        "la santé du PC. Les explications décrivent les règles déclenchées, "
        "sans inclure les valeurs ou noms propres aux mesures.",
        "summary": {
            "collectors": len(collectors),
            "completed": sum(c["status"] == Status.OK.value for c in collectors),
            "incomplete": sum(c["status"] != Status.OK.value for c in collectors),
            "findings": sum(len(c["findings"]) for c in collectors),
            "omitted_collectors": len(scan.results) - len(collectors),
        },
        "collectors": collectors,
    }


def _html_report(report: dict) -> str:
    escape = html.escape
    rows = "".join(
        f"<tr><th scope='row'>{escape(c['title'])}</th><td>{escape(c['status'])}</td>"
        f"<td>{c['row_count']}</td><td>{len(c['findings'])}</td></tr>"
        for c in report["collectors"]
    )
    details = []
    for collector in report["collectors"]:
        details.append(
            f"<section><h2>{escape(collector['title'])}</h2>"
            f"<p>{escape(collector['purpose'])}</p>"
            f"<p><b>{escape(collector['status'])}.</b> "
            f"{escape(collector['status_explanation'])}</p>"
        )
        for finding in collector["findings"]:
            details.append(f"<article><h3>{escape(finding['title'])}</h3><dl>")
            details.extend(
                f"<dt>{escape(title)}</dt><dd>{escape(finding[key])}</dd>"
                for key, title in _PUBLIC_FIELDS.items()
                if key != "title"
            )
            details.append("</dl></article>")
        if not collector["findings"]:
            details.append(
                "<p>Aucune alerte de règle exportée pour ce contrôle. "
                "Consulter aussi ses limites et son état.</p>"
            )
        if collector["omitted_findings"]:
            details.append(
                "<p>Des alertes ont été omises : contrôle incomplet ou règle "
                "non reconnue. Les consulter dans l'application.</p>"
            )
        details.append(
            f"<p><b>Source :</b> {escape(collector['source'])}<br>"
            f"<b>Limites :</b> {escape(collector['limitations'])}</p></section>"
        )
    summary = report["summary"]
    coverage_warning = (
        "<p>Des collecteurs inconnus ont été exclus du rapport. "
        "La couverture complète doit être examinée dans l'application.</p>"
        if summary["omitted_collectors"]
        else ""
    )
    return (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" '
        "content=\"default-src 'none'; style-src 'unsafe-inline'\">"
        "<title>DeepTrace — Rapport filtré</title><style>"
        "body{font:16px system-ui;background:#101924;color:#edf3f8;"
        "max-width:1050px;margin:40px auto;padding:24px;line-height:1.6}"
        "table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:12px;"
        "border-bottom:1px solid #344556}h1{color:#57dec4}h2{font-size:1.4rem}"
        "section{border-top:1px solid #344556;margin-top:28px;padding-top:12px}"
        "article{background:#1b2a3c;padding:16px 22px;border-radius:10px;margin:16px 0}"
        "dt{font-weight:650;margin-top:10px}dd{margin-left:0}caption{text-align:left;"
        "font-size:1.2rem;font-weight:600;padding-bottom:12px}"
        "@media print{body{background:white;color:black;margin:0}h1{color:#17594e}"
        "article{background:#eee}section{break-inside:avoid}}"
        "</style></head><body>"
        f"<h1>{escape(report['application'])}</h1><p>Analyse {escape(report['level'])}</p>"
        f"<p>{escape(report['privacy'])}</p><p>{escape(report['limitations'])}</p>"
        f"<p><b>{summary['completed']}/{summary['collectors']} contrôles terminés · "
        f"{summary['incomplete']} non aboutis · {summary['findings']} alertes à examiner.</b></p>"
        "<table><caption>Couverture des contrôles</caption><thead><tr>"
        "<th>Contrôle</th><th>État</th><th>Observations locales</th><th>Alertes</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>{coverage_warning}"
        f"{''.join(details)}</body></html>"
    )


def export_report(scan: Scan, path: Path):
    report = public_report(scan)
    if path.suffix.lower() == ".json":
        text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    elif path.suffix.lower() == ".html":
        text = _html_report(report)
    else:
        raise ValueError("Choisir une extension .json ou .html")
    # L'écrasement est confirmé par l'appelant. Une écriture interrompue ne tronque pas
    # un rapport préexistant : créer un temporaire voisin puis remplacer atomiquement.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as file:
            temporary = Path(file.name)
            file.write(text)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
