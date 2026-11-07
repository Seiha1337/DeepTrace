import logging
from threading import Event

from .catalog import select_collectors
from .models import CollectorResult, Scan, Status, utc_now
from .rules import interpret
from .runner import WindowsRunner

logger = logging.getLogger(__name__)


class ScanEngine:
    def __init__(self, runner=None):
        self.runner = runner or WindowsRunner()

    def scan(
        self, level="rapide", symptom="", timeout=25, cancel=None, progress=None, started=None
    ) -> Scan:
        if not isinstance(timeout, int) or not 1 <= timeout <= 120:
            raise ValueError("Délai invalide (1–120 secondes)")
        specs = select_collectors(level, symptom)
        cancel = cancel or Event()
        scan = Scan(level, symptom)
        for index, spec in enumerate(specs):
            if cancel.is_set():
                result = CollectorResult(spec.id, Status.CANCELLED, error="Analyse interrompue.")
            else:
                if started:
                    started(index + 1, len(specs), spec.id)
                try:
                    result = self.runner.collect(spec.id, min(timeout, spec.timeout))
                    result.findings = interpret(result)
                except Exception:
                    # Ni données Windows, ni exception brute dans le journal.
                    result = CollectorResult(
                        spec.id, Status.ERROR, error="Échec isolé du collecteur."
                    )
            scan.results.append(result)
            logger.info(
                "collector=%s status=%s duration_ms=%s",
                spec.id,
                result.status.value,
                result.duration_ms,
            )
            if progress:
                progress(index + 1, len(specs), result)
        scan.finished_at = utc_now()
        return scan
