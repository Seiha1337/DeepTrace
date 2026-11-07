import json
import sqlite3

import pytest

from deeptrace import report
from deeptrace.models import CollectorResult, Scan, Status
from deeptrace.rules import interpret
from deeptrace.storage import DEFAULT_SETTINGS, SCHEMA_VERSION, History, HistoryError, compare


def sample_scan():
    scan = Scan("rapide")
    result = CollectorResult(
        "volumes",
        Status.OK,
        data=[
            {
                "DeviceID": "PRIVATE-PC-USER",
                "Size": 100,
                "FreeSpace": 5,
            }
        ],
    )
    result.findings = interpret(result)
    scan.results = [result]
    return scan


def test_report_explains_known_alert_with_only_fixed_rule_text(tmp_path):
    scan = sample_scan()
    finding = scan.results[0].findings[0]
    # Un historique manipulé ne doit pas transformer le texte public en fuite de données.
    for key in ("title", "severity", "observed", "hypothesis", "recommendation", "confidence"):
        setattr(finding, key, "PRIVATE-PC-USER <script>secret-token</script>")
    scan.results[0].error = "private exception path"
    scan.symptom = "private symptom"
    payload = report.public_report(scan)
    exported = payload["collectors"][0]["findings"][0]
    assert exported["title"] == "Espace libre inférieur à 10 %"
    assert exported["recommendation"]
    assert exported["protection"] and exported["rollback"] and exported["verification"]
    assert "observed" not in exported and "evidence" not in exported
    assert payload["summary"]["findings"] == 1
    for extension in ("json", "html"):
        path = tmp_path / f"rapport lisible.{extension}"
        report.export_report(scan, path)
        text = path.read_text("utf-8")
        assert "PRIVATE" not in text and "secret-token" not in text and "private" not in text
        assert "Stockage de Windows" in text
    assert not list(tmp_path.glob("*.tmp"))


def test_report_unknown_collectors_and_rules_are_not_exported():
    scan = sample_scan()
    scan.results[0].findings[0].rule = "private-custom-rule"
    scan.results.append(CollectorResult("private-custom-collector", Status.OK))
    payload = report.public_report(scan)
    assert payload["summary"]["omitted_collectors"] == 1
    assert payload["collectors"][0]["omitted_findings"] == 1
    assert payload["summary"]["findings"] == 0
    assert "private" not in json.dumps(payload)


def test_failed_export_preserves_preexisting_report_and_cleans_temp(tmp_path, monkeypatch):
    path = tmp_path / "rapport.html"
    path.write_text("previous report", "utf-8")

    def refuse(*args):
        raise PermissionError("target locked")

    monkeypatch.setattr(report.os, "replace", refuse)
    with pytest.raises(PermissionError):
        report.export_report(sample_scan(), path)
    assert path.read_text("utf-8") == "previous report"
    assert list(tmp_path.iterdir()) == [path]


def test_v1_history_migration_preserves_existing_analysis(tmp_path):
    path = tmp_path / "history.sqlite3"
    scan = sample_scan()
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE scans(id TEXT PRIMARY KEY, started_at TEXT, level TEXT, payload TEXT)"
        )
        db.execute(
            "CREATE TABLE simulations(id INTEGER PRIMARY KEY,created_at TEXT,operation TEXT,"
            "payload TEXT)"
        )
        db.execute(
            "INSERT INTO scans VALUES (?,?,?,?)",
            (
                scan.id,
                scan.started_at,
                scan.level,
                json.dumps(scan.to_dict()),
            ),
        )
        db.execute("PRAGMA user_version=1")
    history = History(path)
    assert history.load(scan.id).to_dict() == scan.to_dict()
    assert history.get_settings() == DEFAULT_SETTINGS
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


@pytest.mark.parametrize("version", [0, 99])
def test_unrecognized_database_is_preserved(tmp_path, version):
    path = tmp_path / "history.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE precious(value TEXT)")
        db.execute("INSERT INTO precious VALUES ('preserve')")
        db.execute(f"PRAGMA user_version={version}")
    original = path.read_bytes()
    with pytest.raises(HistoryError):
        History(path)
    assert path.read_bytes() == original


def test_corrupt_analysis_is_reported_without_deletion(tmp_path):
    history = History(tmp_path / "history.sqlite3")
    scan = sample_scan()
    history.save(scan)
    with history.connect() as db:
        db.execute("UPDATE scans SET payload=? WHERE id=?", ('{"results":"broken"}', scan.id))
    with pytest.raises(ValueError, match="fichier conservé"):
        history.load(scan.id)
    assert len(history.list_scans()) == 1
    with history.connect() as db:
        assert db.execute("SELECT payload FROM scans").fetchone()[0] == '{"results":"broken"}'


def test_settings_persist_and_invalid_batch_is_atomic(tmp_path):
    path = tmp_path / "history.sqlite3"
    history = History(path)
    settings = {
        "expert": True,
        "remember": False,
        "timeout": 12,
        "level": "ciblée",
        "symptom": "Panne réseau",
        "export_directory": str(tmp_path),
        "check_updates": True,
        "auto_updates": True,
        "updates_consent": True,
    }
    history.save_settings(settings)
    assert History(path).get_settings() == {**DEFAULT_SETTINGS, **settings}
    with pytest.raises(ValueError):
        history.save_settings({"expert": False, "timeout": True})
    assert History(path).get_settings()["expert"] is True
    with pytest.raises(ValueError):
        history.save_settings({"run_command": "arbitrary"})


def test_corrupt_settings_do_not_get_replaced_silently(tmp_path):
    history = History(tmp_path / "history.sqlite3")
    with history.connect() as db:
        db.execute("INSERT INTO settings VALUES (?,?)", ("timeout", "999"))
    with pytest.raises(ValueError, match="fichier conservé"):
        history.get_settings()
    with history.connect() as db:
        assert db.execute("SELECT payload FROM settings WHERE key='timeout'").fetchone()[0] == "999"


def test_comparison_ignores_row_order_and_reports_coverage():
    before = sample_scan()
    before.results[0].data.append({"DeviceID": "D:", "Size": 500, "FreeSpace": 200})
    after = Scan.from_dict(before.to_dict())
    after.results[0].data.reverse()
    assert compare(before, after) == []
    after.results.append(CollectorResult("hardware", Status.OK))
    assert compare(before, after) == [
        {
            "collector": "hardware",
            "change": "Couverture différente ; non comparable",
        }
    ]
