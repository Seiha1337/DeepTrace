"""Historique local, migrations non destructives et préférences validées."""

import json
import math
import sqlite3
from contextlib import contextmanager
from dataclasses import fields
from pathlib import Path

from .catalog import BY_ID, SYMPTOMS
from .models import Finding, Scan

SCHEMA_VERSION = 2
DEFAULT_SETTINGS = {
    "expert": False,
    "remember": True,
    "timeout": 25,
    "level": "rapide",
    "symptom": next(iter(SYMPTOMS)),
    "export_directory": "",
    "check_updates": False,
    "auto_updates": False,
    "updates_consent": False,
}


class HistoryError(sqlite3.DatabaseError):
    """Base incompatible : conserver le fichier et informer l'utilisateur."""


def _validate_setting(key, value):
    if key in ("expert", "remember", "check_updates", "auto_updates", "updates_consent"):
        valid = type(value) is bool
    elif key == "timeout":
        valid = type(value) is int and 1 <= value <= 120
    elif key == "level":
        valid = isinstance(value, str) and value in ("rapide", "approfondie", "ciblée")
    elif key == "symptom":
        valid = isinstance(value, str) and value in SYMPTOMS
    elif key == "export_directory":
        valid = isinstance(value, str) and len(value) <= 4096 and "\0" not in value
    else:
        valid = False
    if not valid:
        raise ValueError("Préférence locale invalide ou non prise en charge.")


def _read_scan(payload: str) -> Scan:
    try:
        value = json.loads(payload)
        scan = Scan.from_dict(value)
        if not isinstance(scan.id, str) or not isinstance(scan.started_at, str):
            raise ValueError
        if scan.finished_at is not None and not isinstance(scan.finished_at, str):
            raise ValueError
        if scan.level not in ("rapide", "approfondie", "ciblée"):
            raise ValueError
        if not isinstance(scan.symptom, str):
            raise ValueError
        seen = set()
        for result in scan.results:
            if result.collector_id not in BY_ID or result.collector_id in seen:
                raise ValueError
            seen.add(result.collector_id)
            if type(result.duration_ms) is not int or result.duration_ms < 0:
                raise ValueError
            if result.return_code is not None and type(result.return_code) is not int:
                raise ValueError
            if result.error is not None and not isinstance(result.error, str):
                raise ValueError
            if not isinstance(result.started_at, str) or not isinstance(result.data, list):
                raise ValueError
            for row in result.data:
                if not isinstance(row, dict) or not set(row).issubset(
                    BY_ID[result.collector_id].fields
                ):
                    raise ValueError
                if any(
                    not isinstance(v, (str, int, float, bool, type(None))) for v in row.values()
                ):
                    raise ValueError
                if any(isinstance(v, float) and not math.isfinite(v) for v in row.values()):
                    raise ValueError
            for finding in result.findings:
                if finding.collector_id != result.collector_id:
                    raise ValueError
                for spec in fields(Finding):
                    item = getattr(finding, spec.name)
                    if spec.name == "evidence":
                        if not isinstance(item, dict):
                            raise ValueError
                    elif not isinstance(item, str):
                        raise ValueError
        return scan
    except (TypeError, KeyError, ValueError, AttributeError):
        raise ValueError(
            "Analyse enregistrée illisible ou incompatible ; fichier conservé."
        ) from None


class History:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, SCHEMA_VERSION):
                raise HistoryError("Version d'historique incompatible ; fichier conservé.")
            if (
                version == 0
                and db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchone()
            ):
                raise HistoryError("Base existante non reconnue ; fichier conservé.")
            db.execute("BEGIN")
            if version == 0:
                db.execute("""CREATE TABLE scans (
                    id TEXT PRIMARY KEY, started_at TEXT NOT NULL, level TEXT NOT NULL,
                    payload TEXT NOT NULL)""")
                db.execute("""CREATE TABLE simulations (
                    id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, operation TEXT NOT NULL,
                    payload TEXT NOT NULL)""")
            else:
                db.execute("SELECT id,started_at,level,payload FROM scans LIMIT 0")
                db.execute("SELECT id,created_at,operation,payload FROM simulations LIMIT 0")
            if version < SCHEMA_VERSION:
                db.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, payload TEXT NOT NULL)")
                db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            else:
                db.execute("SELECT key,payload FROM settings LIMIT 0")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    def save(self, scan: Scan):
        payload = json.dumps(scan.to_dict(), ensure_ascii=False, allow_nan=False)
        _read_scan(payload)
        with self.connect() as db:
            db.execute(
                "INSERT INTO scans VALUES (?,?,?,?)",
                (
                    scan.id,
                    scan.started_at,
                    scan.level,
                    payload,
                ),
            )

    def list_scans(self) -> list[tuple]:
        with self.connect() as db:
            return db.execute(
                "SELECT id,started_at,level FROM scans ORDER BY started_at DESC LIMIT 200"
            ).fetchall()

    def load(self, scan_id: str) -> Scan:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM scans WHERE id=?", (scan_id,)).fetchone()
        if row is None:
            raise KeyError("Analyse introuvable")
        return _read_scan(row[0])

    def delete(self, scan_id: str):
        with self.connect() as db:
            db.execute("PRAGMA secure_delete=ON")
            db.execute("DELETE FROM scans WHERE id=?", (scan_id,))

    def record_simulation(self, record: dict):
        with self.connect() as db:
            db.execute(
                "INSERT INTO simulations(created_at,operation,payload) VALUES (?,?,?)",
                (
                    record["created_at"],
                    record["operation"],
                    json.dumps(record, ensure_ascii=False, allow_nan=False),
                ),
            )

    def simulations(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT payload FROM simulations ORDER BY id DESC LIMIT 100"
            ).fetchall()
        try:
            records = [json.loads(row[0]) for row in rows]
            required = ("created_at", "operation", "state", "state_after")
            if any(
                not isinstance(r, dict) or any(not isinstance(r.get(k), str) for k in required)
                for r in records
            ):
                raise ValueError
            return records
        except (ValueError, TypeError):
            raise ValueError("Journal des simulations illisible ; fichier conservé.") from None

    def get_settings(self) -> dict:
        settings = dict(DEFAULT_SETTINGS)
        with self.connect() as db:
            rows = db.execute("SELECT key,payload FROM settings").fetchall()
        try:
            for key, payload in rows:
                if key in DEFAULT_SETTINGS:
                    value = json.loads(payload)
                    _validate_setting(key, value)
                    settings[key] = value
        except (ValueError, TypeError):
            raise ValueError("Préférences locales illisibles ; fichier conservé.") from None
        return settings

    def save_settings(self, settings: dict):
        if not isinstance(settings, dict):
            raise ValueError("Préférences locales invalides.")
        for key, value in settings.items():
            _validate_setting(key, value)
        with self.connect() as db:
            db.executemany(
                "INSERT INTO settings(key,payload) VALUES (?,?) "
                "ON CONFLICT(key) DO UPDATE SET payload=excluded.payload",
                [
                    (key, json.dumps(value, ensure_ascii=False, allow_nan=False))
                    for key, value in settings.items()
                ],
            )


def compare(before: Scan, after: Scan) -> list[dict]:
    """Différentiel de faits ; l'ordre des lignes n'est pas une modification."""

    def index(scan):
        return {r.collector_id: r for r in scan.results}

    old, new = index(before), index(after)
    changes = []
    for key in sorted(old.keys() | new.keys()):
        a, b = old.get(key), new.get(key)
        if a is None or b is None:
            changes.append({"collector": key, "change": "Couverture différente ; non comparable"})
        elif a.status != b.status:
            changes.append({"collector": key, "change": f"{a.status.value} → {b.status.value}"})
        elif sorted(json.dumps(r, sort_keys=True) for r in a.data) != sorted(
            json.dumps(r, sort_keys=True) for r in b.data
        ):
            changes.append(
                {"collector": key, "change": "Mesures différentes ; causalité non établie"}
            )
    return changes
