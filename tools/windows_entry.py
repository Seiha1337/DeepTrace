"""Point d'entrée absolu pour PyInstaller ; aucun import relatif au script gelé."""

if __name__ == "__main__":
    try:
        from deeptrace.__main__ import main

        raise SystemExit(main())
    except Exception as error:
        import ctypes

        from deeptrace.bootstrap import record_startup_failure

        log = record_startup_failure(error)
        detail = f"Détails techniques : {log}" if log else "Le journal est inaccessible."
        ctypes.windll.user32.MessageBoxW(
            None,
            "Un composant de DeepTrace n'a pas pu démarrer. Aucun paramètre Windows "
            f"n'a été modifié.\n\n{detail}",
            "DeepTrace — erreur de démarrage",
            0x10,
        )
        raise SystemExit(1) from None
