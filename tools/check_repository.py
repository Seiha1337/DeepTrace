"""Contrôle local et CI des fichiers suivis, sans afficher le contenu des secrets."""

import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PARTS = {"local", "reports", "backups", ".venv", "__pycache__"}
FORBIDDEN_EXTENSIONS = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".log",
    ".dmp",
    ".dump",
    ".pem",
    ".key",
    ".bak",
    ".iso",
    ".vhd",
    ".vhdx",
}
PATTERNS = [
    re.compile(rb"gh[pousr]_" + rb"[A-Za-z0-9]{30,}"),
    re.compile(rb"github_pat_" + rb"[A-Za-z0-9_]{40,}"),
    re.compile(rb"AKIA" + rb"[A-Z0-9]{16}"),
    re.compile(rb"-----BEGIN " + rb"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


def problems(relative: str, content: bytes) -> list[str]:
    path = Path(relative)
    errors = []
    if (
        set(path.parts) & FORBIDDEN_PARTS
        or path.suffix.lower() in FORBIDDEN_EXTENSIONS
        or path.name.startswith(".env")
    ):
        errors.append("format privé interdit")
    if len(content) > 2_000_000:
        errors.append("fichier supérieur à 2 Mo : revue nécessaire")
    if any(pattern.search(content) for pattern in PATTERNS):
        errors.append("motif de secret détecté")
    return errors


def main() -> int:
    git = shutil.which("git")
    if not git:
        raise RuntimeError("Git introuvable")
    completed = subprocess.run(  # noqa: S603 - commande git fixe, aucun shell
        [git, "ls-files", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=True,  # noqa: S607
    )
    files = [p for p in completed.stdout.decode("utf-8").split("\0") if p]
    if not files:
        print("Aucun fichier suivi : préparer l'index Git avant ce contrôle.")
        return 1
    errors = []
    for relative in files:
        path = ROOT / relative
        if path.is_file():
            errors.extend(
                f"{relative} : {error}" for error in problems(relative, path.read_bytes())
            )
    if errors:
        print("\n".join(errors))
        return 1
    print(f"Publication : {len(files)} fichiers suivis contrôlés, aucun motif bloquant.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
