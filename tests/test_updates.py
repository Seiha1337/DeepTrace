import hashlib
import io
import json
from threading import Event

import pytest

from deeptrace import updates

DATA = b"MZsynthetic-release-bytes"
DIGEST = hashlib.sha256(DATA).hexdigest()
URL = "https://github.com/Seiha1337/DeepTrace/releases/download/v0.2.0/DeepTrace.exe"


def release_payload(**overrides):
    data = {
        "tag_name": "v0.2.0",
        "draft": False,
        "prerelease": False,
        "assets": [
            {
                "name": "DeepTrace.exe",
                "size": len(DATA),
                "browser_download_url": URL,
                "digest": f"sha256:{DIGEST}",
            }
        ],
    }
    return data | overrides


def test_check_uses_fixed_repository_and_version_comparison(monkeypatch):
    calls = []

    def read(url, maximum):
        calls.append(url)
        return json.dumps(release_payload()).encode()

    monkeypatch.setattr(updates, "_read_small", read)
    release = updates.check_latest("0.1.1")
    assert release.version == "0.2.0" and release.sha256 == DIGEST
    assert calls == [updates.API_URL]
    assert updates.check_latest("0.2.0") is None
    assert updates.check_latest("0.3.0") is None


@pytest.mark.parametrize("value", ["1.2", "1.2.3rc1", "1.2.3;cmd", "v01.2.3", "https://evil"])
def test_versions_are_strict(value):
    with pytest.raises(updates.UpdateError):
        updates.version_tuple(value)


@pytest.mark.parametrize(
    "url",
    [
        URL.replace("https:", "http:"),
        URL.replace("github.com", "evil.test"),
        URL.replace("Seiha1337", "other"),
        URL + "?token=private",
        URL.replace("DeepTrace.exe", "other.exe"),
    ],
)
def test_download_location_must_be_exact_official_asset(url):
    with pytest.raises(updates.UpdateError):
        updates._asset_url(url, "0.2.0", "DeepTrace.exe")


def test_prerelease_ignored_and_invalid_metadata_rejected(monkeypatch):
    monkeypatch.setattr(
        updates, "_read_small", lambda *a: json.dumps(release_payload(prerelease=True)).encode()
    )
    assert updates.check_latest("0.1.0") is None
    monkeypatch.setattr(
        updates, "_read_small", lambda *a: json.dumps(release_payload(assets=[])).encode()
    )
    with pytest.raises(updates.UpdateError):
        updates.check_latest("0.1.0")


def test_download_verifies_size_and_hash_and_cancellation(tmp_path, monkeypatch):
    monkeypatch.setattr(updates, "_open", lambda *a: io.BytesIO(DATA))
    release = updates.Release("0.2.0", URL, DIGEST, len(DATA))
    path = updates.download_release(release, tmp_path)
    assert path.read_bytes() == DATA
    wrong = updates.Release("0.2.0", URL, "0" * 64, len(DATA))
    with pytest.raises(updates.UpdateError):
        updates.download_release(wrong, tmp_path)
    assert len(list(tmp_path.glob("update-*"))) == 1
    cancel = Event()
    cancel.set()
    with pytest.raises(updates.UpdateError, match="annulé"):
        updates.download_release(release, tmp_path, cancel=cancel)


def prepare_ticket(tmp_path, monkeypatch):
    stage = tmp_path / "stage"
    stage.mkdir()
    source = stage / "DeepTrace.exe"
    source.write_bytes(DATA)
    helper = stage / "DeepTrace-updater.exe"
    helper.write_bytes(b"MZold-helper")
    installed = tmp_path / "installed"
    installed.mkdir()
    target = installed / "DeepTrace.exe"
    target.write_bytes(b"MZold-version")
    ticket = stage / "update-ticket.json"
    ticket.write_text(
        json.dumps(
            {
                "source": str(source),
                "target": str(target),
                "sha256": DIGEST,
                "old_sha256": updates.file_digest(target),
                "parent_pid": 123456,
            }
        )
    )
    monkeypatch.setattr(updates.sys, "executable", str(helper))
    monkeypatch.setattr(updates, "_wait_for_parent", lambda pid: None)
    monkeypatch.setattr(updates, "_spawn", lambda *args: None)
    return ticket, source, target


def test_helper_replaces_only_after_parent_exit_and_keeps_old_copy(tmp_path, monkeypatch):
    ticket, source, target = prepare_ticket(tmp_path, monkeypatch)
    waited = []
    monkeypatch.setattr(updates, "_wait_for_parent", lambda pid: waited.append(pid))
    assert updates.apply_update(ticket) == 0
    assert waited == [123456]
    assert target.read_bytes() == DATA
    assert next(target.parent.glob("DeepTrace.previous-*.exe")).read_bytes() == b"MZold-version"
    assert not ticket.exists()


def test_restart_failure_restores_previous_version(tmp_path, monkeypatch):
    ticket, source, target = prepare_ticket(tmp_path, monkeypatch)

    def fail(*args):
        raise OSError("synthetic launch failure")

    monkeypatch.setattr(updates, "_spawn", fail)
    assert updates.apply_update(ticket) == 1
    assert target.read_bytes() == b"MZold-version"
    assert source.read_bytes() == DATA


def test_modified_source_or_target_is_never_installed(tmp_path, monkeypatch):
    ticket, source, target = prepare_ticket(tmp_path, monkeypatch)
    source.write_bytes(b"MZchanged")
    assert updates.apply_update(ticket) == 1
    assert target.read_bytes() == b"MZold-version"


def test_source_execution_cannot_launch_installer(tmp_path):
    release = updates.Release("0.2.0", URL, DIGEST, len(DATA))
    with pytest.raises(updates.UpdateError, match="exécutable"):
        updates.launch_installer(tmp_path / "DeepTrace.exe", release)


def test_helper_rejects_non_application_target(tmp_path, monkeypatch):
    ticket, source, target = prepare_ticket(tmp_path, monkeypatch)
    payload = json.loads(ticket.read_text())
    payload["target"] = str(tmp_path / "system-file.dll")
    ticket.write_text(json.dumps(payload))
    assert updates.apply_update(ticket) == 1
    assert target.read_bytes() == b"MZold-version"


def test_helper_keeps_data_directory_and_replaces_from_same_volume(tmp_path, monkeypatch):
    ticket, source, target = prepare_ticket(tmp_path, monkeypatch)
    payload = json.loads(ticket.read_text())
    payload["data_dir"] = str(tmp_path / "custom-data")
    ticket.write_text(json.dumps(payload))
    calls = []
    monkeypatch.setattr(updates, "_spawn", lambda exe, args: calls.append((exe, args)))
    real_replace = updates.os.replace

    def same_volume_replace(src, dst):
        # Une tentative de renommage du staging vers l'autre volume doit échouer.
        if src == source:
            raise OSError("different volumes")
        return real_replace(src, dst)

    monkeypatch.setattr(updates.os, "replace", same_volume_replace)
    assert updates.apply_update(ticket) == 0
    assert calls == [(target, ["--data-dir", payload["data_dir"]])]


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://github.com", "https://evil.test"])
def test_network_opener_rejects_unapproved_hosts_without_network(url):
    with pytest.raises(updates.UpdateError):
        updates._open(url)
