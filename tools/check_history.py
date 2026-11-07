"""Vérifier tous les blobs Git avant changement de visibilité du dépôt."""

import shutil
import subprocess

from check_repository import ROOT, problems


def main():
    git = shutil.which("git")
    if not git:
        raise RuntimeError("Git introuvable")

    def command(*args):
        return subprocess.check_output([git, *args], cwd=ROOT)  # noqa: S603

    lines = command("rev-list", "--objects", "--all").decode("utf-8").splitlines()
    count = 0
    for line in lines:
        sha, _, path = line.partition(" ")
        if not path or command("cat-file", "-t", sha).strip() != b"blob":
            continue
        errors = problems(path, command("cat-file", "blob", sha))
        if errors:
            print(f"Historique : contenu à examiner dans {path} ({sha[:12]})")
            return 1
        count += 1
    print(f"Historique : {count} versions de fichiers contrôlées, aucun motif bloquant.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
