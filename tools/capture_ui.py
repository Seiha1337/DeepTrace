"""Capture authentique de l'écran initial, sans collecte ni données utilisateur."""

import os
import sys
from pathlib import Path

if sys.platform != "win32":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from deeptrace.ui import MainWindow  # noqa: E402


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / "docs/assets/overview.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    window = MainWindow(root / "local/screenshot")
    window.show()
    app.processEvents()
    if not window.grab().save(str(output)):
        raise OSError("Capture impossible")
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    print("Capture initiale enregistrée : docs/assets/overview.png")


if __name__ == "__main__":
    main()
