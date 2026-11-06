"""Export par liste blanche : jamais de données brutes, noms de logiciels ou identifiants."""

import html
import json
from pathlib import Path

from .catalog import BY_ID
from .models import Scan


def public_report(scan: Scan) -> dict:
    return {
        "application": "DeepTrace 0.1.0",
        "format_version": 1,
        "level": scan.level if scan.level in ("rapide", "approfondie", "ciblée") else "inconnu",
        "privacy": "Synthèse filtrée : aucune donnée brute ou identification de machine exportée.",
        "limitations": "Aucune réparation réalisée. Un contrôle terminé ne garantit pas "
        "la santé du PC.",
        "collectors": [
            {
                "id": r.collector_id,
                "title": BY_ID[r.collector_id].title,
                "status": r.status.value,
                "duration_ms": r.duration_ms,
                "row_count": len(r.data),
                "findings": [{"rule": f.rule, "severity": f.severity} for f in r.findings],
                "source": BY_ID[r.collector_id].source,
                "limitations": BY_ID[r.collector_id].limitations,
            }
            for r in scan.results
        ],
    }


def export_report(scan: Scan, path: Path):
    report = public_report(scan)
    if path.suffix.lower() == ".json":
        text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    elif path.suffix.lower() == ".html":
        escape = html.escape
        rows = "".join(
            f"<tr><td>{escape(c['title'])}</td><td>{escape(c['status'])}</td>"
            f"<td>{c['row_count']}</td><td>{len(c['findings'])}</td>"
            f"<td>{escape(c['limitations'])}</td></tr>"
            for c in report["collectors"]
        )
        text = (
            '<!doctype html><html lang="fr"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width">'
            '<meta http-equiv="Content-Security-Policy" '
            "content=\"default-src 'none'; style-src 'unsafe-inline'\">"
            "<title>DeepTrace — Rapport filtré</title>"
            "<style>body{font:16px system-ui;background:#101924;color:#edf3f8;"
            "max-width:1100px;margin:40px auto;padding:24px}table{border-collapse:collapse}"
            "td,th{text-align:left;padding:12px;border-bottom:1px solid #344556}"
            "p{line-height:1.6}h1{color:#57dec4}</style>"
            f"<h1>DeepTrace</h1><p>Analyse {escape(report['level'])}</p>"
            f"<p>{escape(report['privacy'])}</p><p>{escape(report['limitations'])}</p>"
            "<table><caption>Couverture des contrôles et alertes</caption><thead><tr>"
            "<th>Contrôle</th><th>État</th><th>Observations</th><th>Alertes</th><th>Limites</th>"
            f"</tr></thead><tbody>{rows}</tbody></table></html>"
        )
    else:
        raise ValueError("Choisir une extension .json ou .html")
    # L'écrasement doit être confirmé par l'appelant (dialogue natif ou option CLI explicite).
    path.write_text(text, encoding="utf-8")
