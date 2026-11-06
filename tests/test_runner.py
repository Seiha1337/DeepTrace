import subprocess
from types import SimpleNamespace

import pytest

from deeptrace import runner
from deeptrace.models import Status


@pytest.fixture
def windows(monkeypatch):
    monkeypatch.setattr(runner.sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "CREATE_NO_WINDOW", 0, raising=False)


@pytest.mark.parametrize(
    "code,status", [(77, Status.UNAVAILABLE), (78, Status.UNAVAILABLE), (1, Status.ERROR)]
)
def test_access_denied_and_failure(windows, monkeypatch, code, status):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=code, stdout=b"", stderr=b"sensitive error"),
    )
    result = runner.WindowsRunner().collect("windows", 1)
    assert result.status == status
    assert result.return_code == code
    assert "sensitive" not in result.error


def test_timeout(windows, monkeypatch):
    def expire(*a, **k):
        raise subprocess.TimeoutExpired("powershell", 1)

    monkeypatch.setattr(subprocess, "run", expire)
    result = runner.WindowsRunner().collect("windows", 1)
    assert result.status == Status.TIMEOUT and not result.data


def test_command_has_no_shell_or_user_input(windows, monkeypatch):
    def run(args, **kwargs):
        assert args[0].endswith("powershell.exe")
        assert "-NoProfile" in args and "-NonInteractive" in args
        assert "-ExecutionPolicy" not in args and not kwargs.get("shell")
        return SimpleNamespace(returncode=0, stdout=b'{"items":[{"Version":"11"}]}')

    monkeypatch.setattr(subprocess, "run", run)
    result = runner.WindowsRunner().collect("windows", 1)
    assert result.status == Status.OK and result.data == [{"Version": "11"}]


def test_invalid_output(windows, monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout=b"not JSON")
    )
    assert runner.WindowsRunner().collect("windows", 1).status == Status.ERROR


def test_non_windows(monkeypatch):
    monkeypatch.setattr(runner.sys, "platform", "linux")
    assert runner.WindowsRunner().collect("windows", 1).status == Status.UNAVAILABLE
