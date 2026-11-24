"""JSON permission regressions without bitcoind or browser fixtures."""

import json
import os
import stat
from pathlib import Path
import pytest

from cryptoadvance.specter.persistence import (
    _write_json_file,
    ensure_private_directory,
    secure_json_files,
)


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
def test_specter_data_folder_is_private_even_if_it_already_exists(tmp_path):
    data_folder = tmp_path / "specter"
    data_folder.mkdir(mode=0o777)
    data_folder.chmod(0o777)

    ensure_private_directory(str(data_folder))

    assert stat.S_IMODE(data_folder.stat().st_mode) == 0o700


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
def test_json_and_backup_permissions_are_private_with_permissive_umask(tmp_path):
    folder = tmp_path / "devices"
    folder.mkdir()
    folder.chmod(0o777)
    path = folder / "device.json"
    old_umask = os.umask(0)
    try:
        _write_json_file({"blinding_key": "secret"}, str(path))
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        _write_json_file({"blinding_key": "new-secret"}, str(path))
    finally:
        os.umask(old_umask)

    # Generic JSON writes must not change pre-existing shared directories.
    assert stat.S_IMODE(folder.stat().st_mode) == 0o777
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(Path(str(path) + ".bkp").stat().st_mode) == 0o600


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
def test_existing_json_is_restricted_without_touching_logs_or_symlinks(tmp_path):
    data = tmp_path / "specter"
    wallets = data / "wallets" / "liquid"
    wallets.mkdir(parents=True)
    wallet = wallets / "wallet.json"
    backup = wallets / "wallet.json.bkp"
    log = data / "specter.log"
    outside = tmp_path / "outside.json"
    for path in (wallet, backup, log, outside):
        path.write_text("private")
        path.chmod(0o666)
    (wallets / "link.json").symlink_to(outside)
    data.chmod(0o777)
    wallets.chmod(0o777)

    secure_json_files(str(data))

    for path in (data, wallets, wallets.parent):
        assert stat.S_IMODE(path.stat().st_mode) == 0o700
    for path in (wallet, backup):
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(log.stat().st_mode) == 0o666
    assert stat.S_IMODE(outside.stat().st_mode) == 0o666


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
def test_relative_json_path_is_private(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_json_file({"blinding_key": "secret"}, "device.json")
    assert stat.S_IMODE((tmp_path / "device.json").stat().st_mode) == 0o600


@pytest.mark.skipif(os.name != "posix", reason="POSIX symlinks")
def test_json_writer_refuses_symlink_without_chmodding_external_target(tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text("unchanged")
    outside.chmod(0o666)
    link = tmp_path / "device.json"
    link.symlink_to(outside)
    with pytest.raises(ValueError, match=str(link)) as error:
        _write_json_file({"secret": "value"}, str(link))
    assert "symbolic links are not supported" in str(error.value)
    assert outside.read_text() == "unchanged"
    assert stat.S_IMODE(outside.stat().st_mode) == 0o666


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
def test_non_admin_wallet_and_device_files_are_restricted(tmp_path):
    data = tmp_path / "specter"
    wallet_dir = data / "wallets_alice" / "node" / "liquid"
    device_dir = data / "devices_alice"
    wallet_dir.mkdir(parents=True)
    device_dir.mkdir()
    wallet = wallet_dir / "secret.json"
    device = device_dir / "device.json"
    for path in (wallet, device):
        path.write_text("secret")
        path.chmod(0o666)
    for folder in (wallet_dir, wallet_dir.parent, wallet_dir.parent.parent, device_dir):
        folder.chmod(0o777)
    secure_json_files(str(data))
    for path in (wallet, device):
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    for folder in (wallet_dir, wallet_dir.parent, wallet_dir.parent.parent, device_dir):
        assert stat.S_IMODE(folder.stat().st_mode) == 0o700


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
def test_failed_write_restores_backup_privately_even_with_permissive_umask(tmp_path):
    from cryptoadvance.specter.specter_error import SpecterError

    path = tmp_path / "secret.json"
    _write_json_file({"old": "secret"}, str(path))
    old_umask = os.umask(0)
    try:
        with pytest.raises(SpecterError):
            _write_json_file({"new": object()}, str(path))
    finally:
        os.umask(old_umask)
    assert json.loads(path.read_text()) == {"old": "secret"}
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    backup = Path(str(path) + ".bkp")
    assert json.loads(backup.read_text()) == {"old": "secret"}
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600
    with pytest.raises(SpecterError):
        _write_json_file({"another": object()}, str(path))
    assert json.loads(path.read_text()) == {"old": "secret"}
    assert backup.exists()


@pytest.mark.skipif(os.name != "posix", reason="POSIX ownership")
def test_startup_skips_unowned_data_paths_without_chmod(tmp_path, monkeypatch, caplog):
    data = tmp_path / "specter"
    wallet = data / "wallets_alice" / "node" / "liquid"
    wallet.mkdir(parents=True)
    secret = wallet / "wallet.json"
    secret.write_text("private")
    for path in (data, wallet.parent.parent, wallet.parent, wallet, secret):
        path.chmod(0o777 if path.is_dir() else 0o666)
    # Simulate files on a group-accessible mount owned by another uid.
    monkeypatch.setattr(os, "getuid", lambda: -1)

    def forbid_chmod(*args):
        raise AssertionError("must not chmod someone else's data")

    monkeypatch.setattr(os, "chmod", forbid_chmod)
    ensure_private_directory(str(data))
    secure_json_files(str(data))
    assert str(secret) in caplog.text
    assert "not owned by this user" in caplog.text
    assert stat.S_IMODE(secret.stat().st_mode) == 0o666


@pytest.mark.skipif(os.name != "posix", reason="POSIX ownership")
def test_startup_chmod_permission_denied_warns_and_continues(
    tmp_path, monkeypatch, caplog
):
    data = tmp_path / "specter"
    data.mkdir()
    secret = data / "config.json"
    secret.write_text("private")

    def deny_chmod(*args):
        raise PermissionError()

    monkeypatch.setattr(os, "chmod", deny_chmod)
    ensure_private_directory(str(data))
    secure_json_files(str(data))
    assert "permission denied" in caplog.text
    assert str(secret) in caplog.text


@pytest.mark.skipif(os.name != "posix", reason="POSIX ownership")
@pytest.mark.parametrize("write_fails", [False, True])
def test_existing_nonowned_json_can_be_backed_up_and_replaced(
    tmp_path, monkeypatch, caplog, write_fails
):
    from cryptoadvance.specter.specter_error import SpecterError

    path = tmp_path / "secret.json"
    backup = tmp_path / "secret.json.bkp"
    path.write_text('{"old": "secret"}')
    path.chmod(0o666)
    backup.write_text('{"stale": true}')
    old_inode = path.stat().st_ino
    # Model a writable shared directory with a pre-existing file owned by
    # another uid, without requiring root or changing actual file ownership.
    monkeypatch.setattr(os, "getuid", lambda: -1)
    real_chmod = os.chmod

    def deny_existing_chmod(target, mode):
        if os.fspath(target) == str(path):
            raise PermissionError("cannot chmod non-owned file")
        return real_chmod(target, mode)

    monkeypatch.setattr(os, "chmod", deny_existing_chmod)
    if write_fails:
        with pytest.raises(SpecterError, match="old version has been restored"):
            _write_json_file({"new": object()}, str(path))
        assert json.loads(path.read_text()) == {"old": "secret"}
    else:
        _write_json_file({"new": "secret"}, str(path))
        assert json.loads(path.read_text()) == {"new": "secret"}
    assert backup.stat().st_ino == old_inode
    assert json.loads(backup.read_text()) == {"old": "secret"}
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert "not owned by this user" in caplog.text
