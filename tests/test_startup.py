from deeptrace.engine import ScanEngine
from deeptrace.models import CollectorResult, Status


def test_stage_starts_before_collection_and_progress_after():
    events = []

    class Runner:
        def collect(self, collector_id, timeout):
            events.append(("collect", collector_id))
            return CollectorResult(collector_id, Status.OK)

    scan = ScanEngine(Runner()).scan(
        started=lambda n, total, key: events.append(("start", key)),
        progress=lambda n, total, result: events.append(("done", result.collector_id)),
    )
    assert len(events) == 3 * len(scan.results)
    for index, result in enumerate(scan.results):
        assert events[index * 3 : index * 3 + 3] == [
            ("start", result.collector_id),
            ("collect", result.collector_id),
            ("done", result.collector_id),
        ]


def test_cli_inaccessible_directory_is_reported(tmp_path, monkeypatch, capsys):
    from deeptrace.__main__ import main

    invalid = tmp_path / "file-not-directory"
    invalid.write_text("keep", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["deeptrace", "--scan", "rapide", "--data-dir", str(invalid)])
    assert main() == 1
    assert "inaccessible" in capsys.readouterr().err
    assert invalid.read_text("utf-8") == "keep"
