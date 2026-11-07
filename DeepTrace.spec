# Construction reproductible du seul exécutable portable Windows x64.
from pathlib import Path
import os
import sys

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
)

root = Path(SPECPATH)
version = "0.1.1"
version_tuple = tuple(int(part) for part in version.split(".")) + (0,)
version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=version_tuple, prodvers=version_tuple,
                     mask=0x3F, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0, 0)),
    kids=[
        StringFileInfo([StringTable("040c04b0", [
            StringStruct("FileDescription", "DeepTrace — Diagnostics Windows locaux"),
            StringStruct("FileVersion", version),
            StringStruct("ProductName", "DeepTrace"),
            StringStruct("ProductVersion", version),
            StringStruct("OriginalFilename", "DeepTrace.exe"),
        ])]),
        VarFileInfo([VarStruct("Translation", [0x040c, 1200])]),
    ],
)
a = Analysis(
    [str(root / "tools/windows_entry.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=[(str(root / "src/deeptrace/scripts"), "deeptrace/scripts"),
           (str(root / "src/deeptrace/assets"), "deeptrace/assets"),
           (str(root / "docs/licenses"), "deeptrace/assets/licenses"),
           (str(root / "docs/THIRD_PARTY.md"), "deeptrace/assets/licenses")],
    # Le hook amont teste les métadonnées du méta-paquet PySide6, absent avec Essentials seul.
    # Les opérateurs d'enums Qt importent ce module dynamiquement.
    hiddenimports=["PySide6.support.deprecated"],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=["tkinter", "pytest", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets"],
    noarchive=False,
)
# Aucune bibliothèque native issue d'un logiciel tiers présent sur le poste de build.
trusted_roots = [root.resolve(), Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve(),
                 Path(os.environ.get("SystemRoot", r"C:\Windows")).resolve()]
for destination, source, kind in a.binaries:
    resolved = Path(source).resolve()
    if not any(resolved.is_relative_to(allowed) for allowed in trusted_roots):
        raise RuntimeError(f"Bibliothèque hors des chemins de construction autorisés : {destination}")
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="DeepTrace", debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False,
    icon=str(root / "src/deeptrace/assets/deeptrace.ico"), version=version_info,
)
