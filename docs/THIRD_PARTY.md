# Composants embarqués

L'exécutable portable V0.1.1 embarque Python 3.13.17, PySide6/Qt Essentials 6.12.0,
shiboken6 et le bootloader PyInstaller 6.22.3. Les bibliothèques Qt sont dynamiques,
extraites dans un dossier temporaire au lancement. Elles ne sont pas modifiées.
Les droits des composants ne sont pas remplacés par ceux du code propre à DeepTrace.

- Python : [licence PSF et notices](licenses/PYTHON.txt).
- Qt/PySide6/shiboken6 : option LGPLv3, avec [LGPLv3](licenses/LGPL-3.0.txt)
  et [GPLv3](licenses/GPL-3.0.txt) à laquelle elle fait référence.
- PyInstaller : [licence et exception de distribution du bootloader](licenses/PYINSTALLER.txt).
- Les composants natifs de Python (notamment SQLite et OpenSSL) et de Qt conservent
  leurs notices tierces respectives : [Python](https://docs.python.org/3.13/license.html),
  [Qt](https://doc.qt.io/qt-6/licenses-used-in-qt.html).

## Sources et remplacement des bibliothèques

Sources amont : [CPython v3.13.17](https://github.com/python/cpython/tree/v3.13.17),
[Qt base v6.12.0](https://code.qt.io/cgit/qt/qtbase.git/?h=v6.12.0),
[Qt for Python v6.12.0](https://code.qt.io/cgit/pyside/pyside-setup.git/?h=v6.12.0).
Les sources de DeepTrace, le fichier `.spec`, les versions de dépendances et le script
de construction sont publiés dans ce dépôt. Pour reconstruire avec des bibliothèques Qt
compatibles modifiées, installer ces bibliothèques dans un environnement Python stable,
puis lancer `tools/build_windows.ps1` avec cet interpréteur. Le script ne réinstalle pas Qt
et ne verrouille pas cryptographiquement la bibliothèque installée. Ne pas remplacer
une bibliothèque par un fichier dont la provenance est inconnue.

Aucune clause propre à DeepTrace ne restreint les droits accordés par les licences
des composants, notamment les modifications et l'analyse nécessaires au débogage de
ces modifications. L'auto-mise à jour est désactivable pour conserver une reconstruction.
