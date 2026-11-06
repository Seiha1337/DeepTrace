from time import monotonic, sleep

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QTimer
from PySide6.QtWidgets import QApplication

from deeptrace.engine import ScanEngine
from deeptrace.models import CollectorResult, Status
from deeptrace.ui import MainWindow


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
