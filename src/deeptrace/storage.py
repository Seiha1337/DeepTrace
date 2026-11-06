"""Historique local ; connexions courtes, requêtes paramétrées, suppression explicite."""

import json
import sqlite3
from pathlib import Path

from .models import Scan


class History:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS scans (
                id TEXT PRIMARY KEY, started_at TEXT NOT NULL, level TEXT NOT NULL,
                payload TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS simulations (
                id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, operation TEXT NOT NULL,
                payload TEXT NOT NULL)""")
            db.execute("PRAGMA user_version=1")

    def connect(self):
        return sqlite3.connect(self.path, timeout=5)

    def save(self, scan: Scan):
        with self.connect() as db:
            db.execute(
                "INSERT INTO scans VALUES (?,?,?,?)",
                (
                    scan.id,
                    scan.started_at,
                    scan.level,
                    json.dumps(scan.to_dict(), ensure_ascii=False, allow_nan=False),
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
        return Scan.from_dict(json.loads(row[0]))

    def delete(self, scan_id: str):
        with self.connect() as db:
            db.execute("PRAGMA secure_delete=ON")
            db.execute("DELETE FROM scans WHERE id=?", (scan_id,))

    def record_simulation(self, record: dict):
        with self.connect() as db:
            db.execute(
                "INSERT INTO simulations(created_at,operation,payload) VALUES (?,?,?)",
                (record["created_at"], record["operation"], json.dumps(record, ensure_ascii=False)),
            )

    def simulations(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT payload FROM simulations ORDER BY id DESC LIMIT 100"
            ).fetchall()
        return [json.loads(row[0]) for row in rows]


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
