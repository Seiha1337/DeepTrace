import importlib.util
from pathlib import Path


def test_publication_guard_rejects_private_files_and_secrets():
    path = Path(__file__).resolve().parents[1] / "tools/check_repository.py"
    spec = importlib.util.spec_from_file_location("publication_guard", path)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    assert guard.problems("local/scan.json", b"{}")
    assert guard.problems("memory.dmp", b"x")
    assert guard.problems(".env", b"x")
    assert guard.problems("code.py", b"ghp_" + b"a" * 40)
    assert not guard.problems("src/deeptrace/models.py", b"class Scan: pass")
