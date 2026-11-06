"""Catalogue fermé : aucune chaîne utilisateur n'est injectée dans PowerShell."""

import base64
import json
import os
import subprocess
import sys
from pathlib import Path
from time import monotonic

from .catalog import BY_ID
from .models import CollectorResult, Status

PREFIX = """
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
try {
  $items = @(& {
"""
SUFFIX = """
  })
  ConvertTo-Json -InputObject @{items=$items} -Depth 6 -Compress
} catch {
  if ($_.Exception -is [System.UnauthorizedAccessException] -or
      $_.FullyQualifiedErrorId -match 'AccessDenied|UnauthorizedAccess') { exit 77 }
  if ($_.Exception -is [System.Management.Automation.CommandNotFoundException]) { exit 78 }
  exit 1
}
"""


def script_for(collector_id: str) -> str:
    if collector_id not in BY_ID:
        raise ValueError("Collecteur non autorisé")
    body = (Path(__file__).parent / "scripts" / f"{collector_id}.ps1").read_text("utf-8")
    return PREFIX + body + SUFFIX


def parse_payload(output: str, collector_id: str) -> list[dict]:
    if len(output) > 2_000_000:
        raise ValueError("Réponse trop volumineuse")

    def reject_constant(value):
        raise ValueError("Nombre JSON non fini interdit")

    payload = json.loads(output.lstrip("\ufeff"), parse_constant=reject_constant)
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError("Format de réponse invalide")
    rows = payload["items"]
    if len(rows) > 1500:
        raise ValueError("Trop de résultats")
    allowed = set(BY_ID[collector_id].fields)
    for row in rows:
        if not isinstance(row, dict) or not set(row).issubset(allowed):
            raise ValueError("Champs de réponse inattendus")
        if any(not isinstance(v, (str, int, float, bool, type(None))) for v in row.values()):
            raise ValueError("Valeur de réponse invalide")
    return rows


class WindowsRunner:
    def collect(self, collector_id: str, timeout: int) -> CollectorResult:
        script = script_for(collector_id)
        if not 1 <= timeout <= 120:
            raise ValueError("Le délai doit être compris entre 1 et 120 secondes")
        result = CollectorResult(collector_id, Status.UNAVAILABLE)
        if sys.platform != "win32":
            result.error = "Collecte disponible uniquement sous Windows."
            return result
        started = monotonic()
        # Résolution absolue : pas de recherche de powershell.exe dans le répertoire courant.
        system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        executable = system_root / "System32/WindowsPowerShell/v1.0/powershell.exe"
        encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        try:
            completed = subprocess.run(  # noqa: S603 - script statique issu du catalogue fermé
                [
                    str(executable),
                    "-NoLogo",
                    "-NoProfile",
                    "-NonInteractive",
                    "-EncodedCommand",
                    encoded,
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            result.return_code = completed.returncode
            if completed.returncode:
                result.status = (
                    Status.UNAVAILABLE if completed.returncode in (77, 78) else Status.ERROR
                )
                result.error = {
                    77: "Accès refusé ; aucune élévation automatique.",
                    78: "Commande Windows indisponible.",
                }.get(completed.returncode, "Échec de la requête Windows ; voir le code de retour.")
            else:
                result.data = parse_payload(completed.stdout.decode("utf-8"), collector_id)
                result.status = Status.OK if result.data else Status.UNAVAILABLE
                if not result.data:
                    result.error = (
                        "Aucune donnée retournée ; ce contrôle ne permet pas de conclure."
                    )
                    if collector_id == "events":
                        result.status = Status.OK
                        result.error = None
        except subprocess.TimeoutExpired:
            result.status = Status.TIMEOUT
            result.error = f"Arrêt après {timeout} secondes ; résultat non interprété."
        except (FileNotFoundError, PermissionError):
            result.error = "PowerShell introuvable ou exécution refusée."
        except (ValueError, UnicodeError):
            result.status = Status.ERROR
            result.error = "Réponse Windows invalide ; résultat non interprété."
        except OSError:
            result.status = Status.ERROR
            result.error = "Erreur système pendant la collecte."
        result.duration_ms = round((monotonic() - started) * 1000)
        return result
