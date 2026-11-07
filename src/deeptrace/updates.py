"""Mises à jour volontaires depuis les seules Releases du dépôt officiel.

SHA-256 protège l'intégrité du transfert ; la confiance d'éditeur repose sur HTTPS
et les droits de publication du dépôt, pas sur une signature Authenticode.
"""

import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from time import monotonic, sleep
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from . import __version__

REPOSITORY = "Seiha1337/DeepTrace"
API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
MAX_DOWNLOAD = 250_000_000
NETWORK_TIMEOUT = 10
REDIRECT_HOSTS = {
    "github.com",
    "api.github.com",
    "release-assets.githubusercontent.com",
    "objects.githubusercontent.com",
}


class UpdateError(Exception):
    """Erreur prévue, affichable sans donnée réseau privée."""


@dataclass(frozen=True)
class Release:
    version: str
    url: str
    sha256: str
    size: int


def version_tuple(version: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", version)
    if not match:
        raise UpdateError("Version de mise à jour invalide.")
    return tuple(int(part) for part in match.groups())


def _asset_url(url: str, version: str, filename: str) -> str:
    parts = urlsplit(url)
    expected = f"/{REPOSITORY}/releases/download/v{version}/{filename}"
    if (
        parts.scheme != "https"
        or parts.netloc != "github.com"
        or parts.path != expected
        or parts.query
        or parts.fragment
    ):
        raise UpdateError("Adresse de téléchargement non autorisée.")
    return url


class _SafeRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parts = urlsplit(newurl)
        if parts.scheme != "https" or parts.netloc not in REDIRECT_HOSTS:
            raise UpdateError("Redirection de mise à jour non autorisée.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open(url):
    # Aucune authentification, identité machine ou donnée de diagnostic envoyée.
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.netloc not in REDIRECT_HOSTS:
        raise UpdateError("Adresse réseau de mise à jour non autorisée.")
    request = Request(  # noqa: S310 - schéma HTTPS et hôtes contrôlés ci-dessus
        url,
        headers={"User-Agent": f"DeepTrace/{__version__}", "Accept": "application/vnd.github+json"},
    )
    return build_opener(_SafeRedirects()).open(request, timeout=NETWORK_TIMEOUT)  # noqa: S310


def _read_small(url: str, maximum: int) -> bytes:
    with _open(url) as response:
        data = response.read(maximum + 1)
    if len(data) > maximum:
        raise UpdateError("Réponse de mise à jour trop volumineuse.")
    return data


def _digest(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", value):
        raise UpdateError("Empreinte SHA-256 absente ou invalide.")
    return value.lower()


def check_latest(current: str = __version__) -> Release | None:
    """À appeler dans un thread ; None signifie aucune version stable plus récente."""
    try:
        payload = json.loads(_read_small(API_URL, 1_000_000))
        if not isinstance(payload, dict) or payload.get("draft") or payload.get("prerelease"):
            return None
        tag = payload.get("tag_name", "")
        version_tuple(tag)
        version = tag.removeprefix("v")
        if tag != f"v{version}" or version_tuple(version) <= version_tuple(current):
            return None
        assets = payload.get("assets")
        if not isinstance(assets, list):
            raise UpdateError("Publication sans fichiers de mise à jour.")
        executables = [
            a for a in assets if isinstance(a, dict) and a.get("name") == "DeepTrace.exe"
        ]
        if len(executables) != 1:
            raise UpdateError("La publication doit contenir un unique DeepTrace.exe.")
        asset = executables[0]
        size = asset.get("size")
        if isinstance(size, bool) or not isinstance(size, int) or not 0 < size <= MAX_DOWNLOAD:
            raise UpdateError("Taille de mise à jour invalide.")
        url = _asset_url(asset.get("browser_download_url", ""), version, "DeepTrace.exe")
        digest = asset.get("digest")
        if isinstance(digest, str) and digest.startswith("sha256:"):
            digest = _digest(digest[7:])
        else:
            manifests = [
                a for a in assets if isinstance(a, dict) and a.get("name") == "SHA256SUMS.txt"
            ]
            if len(manifests) != 1:
                raise UpdateError("Publication dépourvue d'empreinte SHA-256.")
            manifest_url = _asset_url(
                manifests[0].get("browser_download_url", ""), version, "SHA256SUMS.txt"
            )
            lines = _read_small(manifest_url, 16_384).decode("ascii").splitlines()
            matches = [line.split() for line in lines if line.strip()]
            matches = [
                parts[0]
                for parts in matches
                if len(parts) == 2 and parts[1] in ("DeepTrace.exe", "*DeepTrace.exe")
            ]
            if len(matches) != 1:
                raise UpdateError("Manifeste SHA-256 incohérent.")
            digest = _digest(matches[0])
        return Release(version, url, digest, size)
    except HTTPError as exc:
        if exc.code == 404:
            return None
        if exc.code in (403, 429):
            raise UpdateError("GitHub limite les requêtes ; réessayez plus tard.") from None
        raise UpdateError("La recherche de mise à jour est indisponible.") from None
    except (URLError, OSError, ValueError, TypeError, AttributeError):
        raise UpdateError(
            "Impossible de vérifier les mises à jour. Le logiciel reste utilisable."
        ) from None


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download_release(
    release: Release, updates_dir: Path, progress=None, cancel: Event | None = None
) -> Path:
    """Télécharge vers un dossier unique ; retourne seulement un exécutable vérifié."""
    version_tuple(release.version)
    _asset_url(release.url, release.version, "DeepTrace.exe")
    expected = _digest(release.sha256)
    if isinstance(release.size, bool) or not 0 < release.size <= MAX_DOWNLOAD:
        raise UpdateError("Taille de mise à jour invalide.")
    directory = None
    staged = None
    try:
        updates_dir.mkdir(parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix="update-", dir=updates_dir))
        staged = directory / "DeepTrace.exe"
        digest, received = hashlib.sha256(), 0
        started = monotonic()
        with _open(release.url) as response, staged.open("xb") as output:
            while True:
                if cancel is not None and cancel.is_set():
                    raise UpdateError("Téléchargement annulé.")
                if monotonic() - started > 180:
                    raise UpdateError("Délai de téléchargement dépassé.")
                block = response.read(1024 * 256)
                if not block:
                    break
                received += len(block)
                if received > release.size or received > MAX_DOWNLOAD:
                    raise UpdateError("Téléchargement plus volumineux que prévu.")
                output.write(block)
                digest.update(block)
                if progress:
                    progress(received, release.size)
        if received != release.size or digest.hexdigest() != expected:
            raise UpdateError("L'empreinte du téléchargement ne correspond pas : fichier rejeté.")
        with staged.open("rb") as stream:
            executable_header = stream.read(2)
        if executable_header != b"MZ":
            raise UpdateError("Le fichier téléchargé n'est pas un exécutable Windows.")
        return staged
    except (OSError, URLError):
        raise UpdateError(
            "Téléchargement impossible ; la version actuelle est conservée."
        ) from None
    finally:
        if staged is not None and directory is not None and sys.exc_info()[0] is not None:
            staged.unlink(missing_ok=True)
            directory.rmdir()


def _spawn(executable: Path, arguments: list[str]):
    environment = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")
    return subprocess.Popen(  # noqa: S603 - exécutable local contrôlé, sans shell
        [str(executable), *arguments],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        env=environment,
        cwd=executable.parent,
    )


def launch_installer(
    staged: Path, release: Release, target: Path | None = None, data_dir: Path | None = None
):
    """L'UI doit ensuite se fermer ; le helper attend sa sortie sans la forcer."""
    if not getattr(sys, "frozen", False):
        raise UpdateError("La mise à jour automatique est réservée à l'exécutable Windows.")
    target = (target or Path(sys.executable)).resolve()
    staged = staged.resolve()
    if (
        target != Path(sys.executable).resolve()
        or target.name.lower() != "deeptrace.exe"
        or staged.name != "DeepTrace.exe"
        or staged.parent == target.parent
        or target.is_symlink()
        or staged.is_symlink()
    ):
        raise UpdateError("Emplacement de mise à jour non autorisé.")
    expected = _digest(release.sha256)
    if staged.stat().st_size != release.size or file_digest(staged) != expected:
        raise UpdateError("Le fichier de mise à jour n'est plus conforme.")
    helper = staged.parent / "DeepTrace-updater.exe"
    ticket_path = staged.parent / "update-ticket.json"
    if helper.exists() or ticket_path.exists():
        raise UpdateError("Une installation est déjà préparée dans ce dossier.")
    shutil.copy2(target, helper)
    ticket = {
        "target": str(target),
        "source": str(staged),
        "sha256": expected,
        "old_sha256": file_digest(target),
        "parent_pid": os.getpid(),
        "data_dir": str(data_dir.resolve()) if data_dir is not None else None,
    }
    ticket_path.write_text(json.dumps(ticket), encoding="utf-8")
    return _spawn(helper, ["--apply-update", str(ticket_path)])


def _wait_for_parent(pid: int) -> None:
    if sys.platform != "win32":
        raise UpdateError("L'installation automatique nécessite Windows.")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x00100000, False, pid)
    if not handle:
        if ctypes.get_last_error() == 87:  # Processus déjà terminé.
            return
        raise UpdateError("Impossible de vérifier la fermeture de l'application.")
    try:
        if kernel.WaitForSingleObject(handle, 180_000) != 0:
            raise UpdateError("L'application est encore ouverte ; mise à jour reportée.")
    finally:
        kernel.CloseHandle(handle)


def apply_update(ticket_path: Path) -> int:
    """Entrée réservée à la copie helper de DeepTrace, jamais appelée par l'analyse."""
    ticket_path = ticket_path.resolve()
    target = source = backup = candidate = None
    swapped = False
    try:
        if ticket_path.name != "update-ticket.json" or ticket_path.stat().st_size > 4096:
            raise UpdateError("Ticket de mise à jour invalide.")
        if Path(sys.executable).resolve() != ticket_path.parent / "DeepTrace-updater.exe":
            raise UpdateError("Ce ticket doit être ouvert par son assistant de mise à jour.")
        ticket = json.loads(ticket_path.read_text("utf-8"))
        source, target = Path(ticket["source"]), Path(ticket["target"])
        old_digest, new_digest = _digest(ticket["old_sha256"]), _digest(ticket["sha256"])
        pid = ticket["parent_pid"]
        data_dir = ticket.get("data_dir")
        if data_dir is not None and (
            not isinstance(data_dir, str) or not Path(data_dir).is_absolute() or "\0" in data_dir
        ):
            raise UpdateError("Dossier de données invalide.")
        if (
            not isinstance(pid, int)
            or isinstance(pid, bool)
            or pid <= 0
            or pid == os.getpid()
            or source != ticket_path.parent / "DeepTrace.exe"
            or source.is_symlink()
            or not target.is_absolute()
            or target.name.lower() != "deeptrace.exe"
            or target.parent == source.parent
            or target.is_symlink()
            or source.resolve() != source
            or target.resolve() != target
        ):
            raise UpdateError("Ressources de mise à jour non autorisées.")
        if file_digest(source) != new_digest or file_digest(target) != old_digest:
            raise UpdateError("Les fichiers ont changé depuis la préparation.")
        backup = target.with_name(f"DeepTrace.previous-{old_digest[:12]}.exe")
        if backup.exists():
            raise UpdateError(
                "Une sauvegarde de cette version existe déjà ; installation reportée."
            )
        _wait_for_parent(pid)
        # AppData et le programme portable peuvent résider sur deux disques différents.
        # Copier dans le dossier cible permet ensuite un remplacement atomique local.
        descriptor, candidate_name = tempfile.mkstemp(
            prefix=".DeepTrace-install-", suffix=".exe", dir=target.parent
        )
        os.close(descriptor)
        candidate = Path(candidate_name)
        shutil.copyfile(source, candidate)
        if file_digest(candidate) != new_digest:
            raise UpdateError("La mise à jour a changé pendant la préparation.")
        # Le bootloader onefile peut libérer le fichier peu après la fin du processus Qt.
        deadline = monotonic() + 15
        while True:
            try:
                if file_digest(target) != old_digest:
                    raise UpdateError("La version installée a changé ; installation annulée.")
                os.replace(target, backup)
                break
            except PermissionError:
                if monotonic() >= deadline:
                    raise UpdateError(
                        "Le programme est encore verrouillé ; version conservée."
                    ) from None
                sleep(0.25)
        try:
            os.replace(candidate, target)
            swapped = True
            arguments = ["--data-dir", data_dir] if data_dir is not None else []
            _spawn(target, arguments)
        except OSError:
            if swapped:
                os.replace(target, candidate)
            os.replace(backup, target)
            raise UpdateError("Installation interrompue ; ancienne version restaurée.") from None
        ticket_path.unlink(missing_ok=True)
        return 0
    except (OSError, ValueError, KeyError, TypeError, UpdateError):
        # Échec local : conserver les fichiers de staging pour le diagnostic, sans effacement.
        return 1
    finally:
        if candidate is not None:
            try:
                candidate.unlink(missing_ok=True)
            except OSError:
                # Ne pas compromettre le retour arrière si le temporaire est verrouillé.
                pass
