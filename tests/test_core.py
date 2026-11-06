import json
from threading import Event

import pytest

from deeptrace.catalog import CATALOG, select_collectors
from deeptrace.engine import ScanEngine
from deeptrace.interventions import simulate
from deeptrace.models import CollectorResult, Scan, Status
from deeptrace.report import export_report, public_report
from deeptrace.rules import interpret
from deeptrace.runner import parse_payload, script_for
from deeptrace.storage import History, compare


class FakeRunner:
    def collect(self, collector_id, timeout):
        return CollectorResult(collector_id, Status.OK, data=[{}])


def test_selection_closed_catalog():
    assert len({s.id for s in CATALOG}) == len(CATALOG)
    assert len(select_collectors("rapide")) == 8
    assert len(select_collectors("approfondie")) == 12
    assert [s.id for s in select_collectors("ciblée", "Panne réseau")] == [
        "network",
        "firewall",
        "events",
    ]
    for call in (
        lambda: select_collectors("inconnu"),
        lambda: select_collectors("ciblée", "'; Remove-Item C:\\"),
        lambda: script_for("../payload"),
    ):
        with pytest.raises(ValueError):
            call()


@pytest.mark.parametrize(
    "payload",
    [
        "null",
        "[]",
        "{}",
        '{"items":{}}',
        '{"items":[{"Password":"secret"}]}',
        '{"items":[{"Caption":[]}]}',
    ],
)
def test_payload_rejects_unexpected_data(payload):
    with pytest.raises(ValueError):
        parse_payload(payload, "windows")


def test_payload_bom_and_empty_events():
    assert parse_payload('\ufeff{"items":[]}', "events") == []
    assert parse_payload('{"items":[{"FreeSpace":null}]}', "volumes") == [{"FreeSpace": None}]
    with pytest.raises(ValueError):
        parse_payload('{"items":[{"Size":NaN}]}', "volumes")


@pytest.mark.parametrize(
    "free,expected", [(9, 1), (10, 0), (11, 0), (0, 1), (None, 0), (-1, 0), (101, 0), (True, 0)]
)
def test_disk_rule_boundary(free, expected):
    result = CollectorResult("volumes", Status.OK, data=[{"Size": 100, "FreeSpace": free}])
    assert len(interpret(result)) == expected


def test_unavailable_not_interpreted():
    result = CollectorResult("firewall", Status.ERROR, data=[{"Enabled": False}])
    assert interpret(result) == []
    result.status = Status.OK
    finding = interpret(result)[0]
    assert finding.evidence == {"Enabled": False}
    assert "profil est actif" in finding.interpretation
    assert finding.rollback


def test_memory_rule_and_ambiguous_events():
    assert (
        len(
            interpret(
                CollectorResult(
                    "windows",
                    Status.OK,
                    data=[{"TotalVisibleMemorySize": 1000, "FreePhysicalMemory": 90}],
                )
            )
        )
        == 1
    )
    assert interpret(CollectorResult("events", Status.OK, data=[{"Id": 41}])) == []


def test_collector_failure_isolated_and_progress_truthful():
    class Broken(FakeRunner):
        def collect(self, collector_id, timeout):
            if collector_id == "hardware":
                raise PermissionError("private path that must not be logged")
            return super().collect(collector_id, timeout)

    progress = []
    scan = ScanEngine(Broken()).scan(progress=lambda n, total, r: progress.append((n, total)))
    assert len(scan.results) == 8
    assert scan.results[1].status == Status.ERROR
    assert "private" not in scan.results[1].error
    assert progress == [(n, 8) for n in range(1, 9)]
    assert scan.finished_at


def test_cancel_preserves_finished_and_marks_remaining():
    event = Event()

    def progress(n, total, result):
        if n == 2:
            event.set()

    scan = ScanEngine(FakeRunner()).scan(cancel=event, progress=progress)
    assert [r.status for r in scan.results[:2]] == [Status.OK, Status.OK]
    assert all(r.status == Status.CANCELLED for r in scan.results[2:])


def test_history_roundtrip_compare_delete_and_sql_injection(tmp_path):
    history = History(tmp_path / "history.sqlite3")
    scan = ScanEngine(FakeRunner()).scan()
    history.save(scan)
    assert history.load(scan.id).to_dict() == scan.to_dict()
    assert len(history.list_scans()) == 1
    with pytest.raises(KeyError):
        history.load("' OR 1=1 --")
    other = Scan.from_dict(scan.to_dict())
    assert compare(scan, other) == []
    other.results[0].data = [{"Version": "new"}]
    assert compare(scan, other)[0]["collector"] == "windows"
    history.delete(scan.id)
    assert history.list_scans() == []


def test_export_never_leaks_raw_values(tmp_path):
    scan = Scan("rapide", symptom="secret symptom")
    scan.results = [
        CollectorResult(
            "hardware",
            Status.OK,
            data=[{"Name": "<script>PRIVATE-PC\\user token-abc 10.0.0.1</script>"}],
        )
    ]
    payload = json.dumps(public_report(scan))
    assert "PRIVATE" not in payload and "secret" not in payload and "token-abc" not in payload
    for extension in ("html", "json"):
        target = tmp_path / f"report.{extension}"
        export_report(scan, target)
        assert "<script>" not in target.read_text("utf-8")
    with pytest.raises(ValueError):
        export_report(scan, tmp_path / "report.exe")


def test_simulation_closed_catalog_and_journal(tmp_path):
    with pytest.raises(KeyError):
        simulate("run arbitrary command", "scan-id")
    with pytest.raises(ValueError):
        simulate("storage_review", None)
    history = History(tmp_path / "history.sqlite3")
    record = simulate("storage_review", "scan-id")
    history.record_simulation(record)
    assert history.simulations()[0] == record
    assert record["state"] == "simulée"
    assert record["state_after"] == "Aucune modification système."


@pytest.mark.parametrize("timeout", [0, -1, 121, "25"])
def test_engine_timeout_validation(timeout):
    with pytest.raises(ValueError):
        ScanEngine(FakeRunner()).scan(timeout=timeout)
