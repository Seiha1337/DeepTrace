"""Démarrage graphique et erreurs maîtrisées, y compris sans console Windows."""

import logging
import os
import re
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        data_dir / "deeptrace.log", maxBytes=256_000, backupCount=2, encoding="utf-8"
    )
    logging.basicConfig(
        level=logging.INFO,
        handlers=[handler],
        force=True,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def show_error(message: str, *, graphical: bool) -> None:
    if not graphical:
        if sys.stderr is not None:
            print(message, file=sys.stderr)
        return
    from PySide6.QtWidgets import QApplication, QMessageBox

    app = QApplication.instance() or QApplication([])
    QMessageBox.critical(None, "DeepTrace — démarrage impossible", message)
    # Garder QApplication vivante pendant le dialogue natif.
    app.processEvents()


def install_exception_handler() -> None:
    def handle(exception_type, exception, traceback):
        # Aucune exception brute ni variable locale dans le journal de diagnostic.
        logging.error("unhandled_error type=%s", exception_type.__name__)
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.warning(
            None,
            "DeepTrace — opération interrompue",
            "Cette opération a échoué. Aucune correction système n'a été effectuée. "
            "Vous pouvez réessayer ou fermer l'application. "
            "Le journal technique local indique le type d'erreur.",
        )

    sys.excepthook = handle


def record_startup_failure(error: Exception) -> Path | None:
    """Dernier recours sans Qt, sans contenu d'exception ni chemin de source privé."""
    directory = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "DeepTrace"
    if "--data-dir" in sys.argv:
        index = sys.argv.index("--data-dir") + 1
        if index < len(sys.argv):
            directory = Path(sys.argv[index])
    lines = [f"type={type(error).__name__}"]
    module = getattr(error, "name", None)
    if isinstance(module, str) and re.fullmatch(r"[A-Za-z0-9_.]+", module):
        lines.append(f"module={module}")
    lines.extend(
        f"{Path(frame.filename).name}:{frame.lineno} {frame.name}"
        for frame in traceback.extract_tb(error.__traceback__)[-12:]
    )
    try:
        directory.mkdir(parents=True, exist_ok=True)
        output = directory / "startup-error.log"
        output.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return output
    except OSError:
        return None
