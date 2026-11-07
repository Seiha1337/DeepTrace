"""Point d'entrée absolu pour PyInstaller ; aucun import relatif au script gelé."""

from deeptrace.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
