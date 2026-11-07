import argparse
import os
import sqlite3
import sys
from pathlib import Path

from . import __version__
from .bootstrap import configure_logging, install_exception_handler, show_error
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
    parser.add_argument("--apply-update", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.apply_update:
        from .updates import apply_update

        return apply_update(args.apply_update)
    if not 1 <= args.timeout <= 120:
        parser.error("Le délai doit être compris entre 1 et 120 secondes.")
    if args.output and args.output.exists() and not args.overwrite:
        parser.error("Le rapport existe ; utiliser un autre chemin ou --overwrite.")
    if args.output and args.output.suffix.lower() not in (".json", ".html"):
        parser.error("L'export doit porter une extension .json ou .html.")
    try:
        configure_logging(args.data_dir)
    except OSError:
        show_error(
            "Le dossier de données est inaccessible. Choisissez un dossier utilisateur "
            "accessible avec --data-dir. Aucun droit administrateur n'est nécessaire.",
            graphical=not args.scan,
        )
        return 1
    try:
        return run(args, parser)
    except (OSError, sqlite3.Error, ValueError):
        show_error(
            "Impossible de lire ou enregistrer les données locales. "
            "Vérifiez l'espace libre et l'accès au dossier de données. "
            "Si l'historique est endommagé ou issu d'une version plus récente, "
            "conservez-le et utilisez un autre dossier avec --data-dir.",
            graphical=not args.scan,
        )
        return 1


def run(args, parser):
    if args.scan:
        try:
            scan = ScanEngine().scan(args.scan, args.symptom, args.timeout)
        except ValueError as exc:
            parser.error(str(exc))
        if not args.no_history:
            History(args.data_dir / "history.sqlite3").save(scan)
        if args.output:
            export_report(scan, args.output)
        if sys.stdout is not None:
            for result in scan.results:
                print(
                    f"{result.collector_id}: {result.status.value} "
                    f"({len(result.findings)} alerte(s))"
                )
        return 0 if all(r.status.value == "terminé" for r in scan.results) else 2
    from .ui import launch

    install_exception_handler()
    return launch(args.data_dir)


if __name__ == "__main__":
    raise SystemExit(main())
