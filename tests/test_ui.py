from time import monotonic, sleep

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QTimer
from PySide6.QtWidgets import QApplication

from deeptrace.engine import ScanEngine
from deeptrace.models import CollectorResult, Scan, Status, utc_now
from deeptrace.rules import interpret
from deeptrace.ui import MainWindow, QFileDialog


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance
    for widget in instance.topLevelWidgets():
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    instance.quit()


def test_window_navigation_scan_responsiveness_and_history(app, tmp_path):
    class SlowRunner:
        def collect(self, collector_id, timeout):
            sleep(0.03)
            return CollectorResult(collector_id, Status.OK, data=[{}])

    window = MainWindow(tmp_path, ScanEngine(SlowRunner()))
    window.resize(1000, 680)
    window.show()
    assert window.scan is None
    assert window.width() == 1000
    for index in range(window.pages.count()):
        window.navigation.setCurrentRow(index)
        assert window.pages.currentIndex() == index
    ticks = []
    timer = QTimer()
    timer.setInterval(5)
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start()
    window.start_scan()
    deadline = monotonic() + 5
    while window.worker is not None and monotonic() < deadline:
        app.processEvents()
        sleep(0.005)
    timer.stop()
    assert window.worker is None
    assert len(ticks) > 5  # La boucle UI a tourné pendant l'analyse.
    assert window.progress_bar.value() == 8
    assert window.results.topLevelItemCount() == 8
    assert window.history_list.count() == 1
    window.expert.setChecked(True)
    assert "ConvertTo-Json" in window.detail.toPlainText()
    assert window.export_button.isEnabled()
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_raw_html_is_escaped(app, tmp_path):
    window = MainWindow(tmp_path)
    result = CollectorResult("hardware", Status.OK, data=[{"Name": "<script>evil</script>"}])
    assert "<script>evil</script>" not in window.result_html(result)
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_dashboard_summary_filter_and_preferences_persist(app, tmp_path):
    window = MainWindow(tmp_path)
    window.scan = Scan("rapide", finished_at=utc_now())
    volume = CollectorResult(
        "volumes", Status.OK, data=[{"DeviceID": "C:", "Size": 100, "FreeSpace": 2}]
    )
    volume.findings = interpret(volume)
    window.scan.results = [
        CollectorResult(
            "windows",
            Status.OK,
            data=[
                {
                    "Caption": "Windows de test",
                    "TotalVisibleMemorySize": 16 * 1024**2,
                }
            ],
        ),
        CollectorResult("hardware", Status.OK, data=[{"Kind": "CPU", "Name": "CPU test"}]),
        volume,
        CollectorResult("network", Status.UNAVAILABLE),
    ]
    window.render()
    assert "Windows de test" in window.system_summary.text()
    assert "CPU test" in window.system_summary.text()
    assert "16.0 Gio" in window.system_summary.text()
    window.result_filter.setCurrentIndex(1)
    visible = [
        window.results.topLevelItem(i)
        for i in range(window.results.topLevelItemCount())
        if not window.results.topLevelItem(i).isHidden()
    ]
    assert len(visible) == 1 and visible[0].text(0) == "Espace des volumes"
    window.result_filter.setCurrentIndex(2)
    assert window.results.currentItem().text(1) == Status.UNAVAILABLE.value
    window.timeout.setValue(12)
    window.level.setCurrentText("ciblée")
    window.symptom.setCurrentText("Panne réseau")
    window.expert.setChecked(True)
    window.remember.setChecked(False)
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    restored = MainWindow(tmp_path)
    assert restored.timeout.value() == 12
    assert restored.level.currentText() == "ciblée"
    assert restored.symptom.currentText() == "Panne réseau"
    assert restored.expert.isChecked()
    assert not restored.remember.isChecked()
    assert restored.analysis_description.text().startswith("3 contrôles")
    restored.close()
    restored.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_export_adds_selected_extension(app, tmp_path, monkeypatch):
    window = MainWindow(tmp_path)
    window.scan = Scan("rapide", finished_at=utc_now())
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args: (str(tmp_path / "rapport"), "Rapport HTML (*.html)"),
    )
    window.export()
    assert (tmp_path / "rapport.html").is_file()
    assert "exportée" in window.state.text()
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_corrupted_history_comparison_is_explained(app, tmp_path, monkeypatch):
    window = MainWindow(tmp_path)
    for _ in range(2):
        window.history.save(Scan("rapide", finished_at=utc_now()))
    window.refresh_history()
    for index in range(2):
        window.history_list.item(index).setSelected(True)

    def corrupt(_scan_id):
        raise ValueError("corrupt synthetic payload")

    monkeypatch.setattr(window.history, "load", corrupt)
    window.compare()
    assert "Comparaison impossible" in window.history_detail.toPlainText()
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_closing_during_scan_waits_and_closes_automatically(app, tmp_path):
    class SlowRunner:
        def collect(self, collector_id, timeout):
            sleep(0.05)
            return CollectorResult(collector_id, Status.OK, data=[{}])

    window = MainWindow(tmp_path, ScanEngine(SlowRunner()))
    window.show()
    window.start_scan()
    app.processEvents()
    window.close()
    assert window.close_when_finished
    deadline = monotonic() + 5
    while window.worker is not None and monotonic() < deadline:
        app.processEvents()
        sleep(0.005)
    assert window.worker is None
    assert not window.isVisible()
    assert any(r.status == Status.CANCELLED for r in window.scan.results)
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_startup_update_consent_is_persisted_and_can_be_disabled(app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    window = MainWindow(tmp_path)
    calls = []
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(window, "start_update_check", lambda: calls.append("check"))
    window.startup_updates()
    assert calls == ["check"]
    settings = window.history.get_settings()
    assert settings["check_updates"] and settings["auto_updates"] and settings["updates_consent"]
    window.check_updates.setChecked(False)
    assert not window.auto_updates.isChecked()
    window.startup_updates()
    assert calls == ["check"]
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_update_waits_for_analysis_and_preserves_data_dir(app, tmp_path, monkeypatch):
    from deeptrace import updates

    window = MainWindow(tmp_path)
    calls = []
    monkeypatch.setattr(updates, "launch_installer", lambda *a, **kw: calls.append((a, kw)))
    window.pending_update = (tmp_path / "staged.exe", "synthetic-release")
    window.update_install_requested = True
    window.worker = object()
    window.apply_pending_update()
    assert not calls
    window.worker = None
    window.apply_pending_update()
    assert calls[0][1] == {"data_dir": tmp_path}
    assert window.pending_update is None
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
