import argparse
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import __version__
from .engine import ScanEngine
from .report import export_report
from .storage import History


def main():
    parser = argparse.ArgumentParser(description="DeepTrace — Diagnostics locaux en lecture seule")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(os.environ.get("LOCALAPPDATA", Path.home())) / "DeepTrace",
    )
    parser.add_argument("--scan", choices=["rapide", "approfondie", "ciblée"])
    parser.add_argument("--symptom", default="")
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--no-history", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.timeout <= 120:
        parser.error("Le délai doit être compris entre 1 et 120 secondes.")
    if args.output and args.output.exists() and not args.overwrite:
        parser.error("Le rapport existe ; utiliser un autre chemin ou --overwrite.")
    if args.output and args.output.suffix.lower() not in (".json", ".html"):
        parser.error("L'export doit porter une extension .json ou .html.")
    args.data_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        args.data_dir / "deeptrace.log", maxBytes=256_000, backupCount=2, encoding="utf-8"
    )
    logging.basicConfig(
        level=logging.INFO, handlers=[handler], format="%(asctime)s %(levelname)s %(message)s"
    )
    if args.scan:
        try:
            scan = ScanEngine().scan(args.scan, args.symptom, args.timeout)
        except ValueError as exc:
            parser.error(str(exc))
        if not args.no_history:
            History(args.data_dir / "history.sqlite3").save(scan)
        if args.output:
            export_report(scan, args.output)
        for result in scan.results:
            print(
                f"{result.collector_id}: {result.status.value} ({len(result.findings)} alerte(s))"
            )
        return 0 if all(r.status.value == "terminé" for r in scan.results) else 2
    from .ui import launch

    return launch(args.data_dir)


if __name__ == "__main__":
    raise SystemExit(main())
