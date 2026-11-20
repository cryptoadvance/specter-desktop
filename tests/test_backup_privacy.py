"""Backup privacy regressions without bitcoind, elementsd or browser fixtures."""

import os
import stat
from pathlib import Path
import pytest
from jinja2 import Environment, FileSystemLoader

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

    assert stat.S_IMODE(folder.stat().st_mode) == 0o700
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


def test_liquid_multisig_warning_only_on_creation_flow():
    templates = (
        Path(__file__).resolve().parents[1] / "src/cryptoadvance/specter/templates"
    )
    env = Environment(loader=FileSystemLoader(str(templates)))
    # Render the actual keys step without the browser or Flask app.
    source = env.loader.get_source(env, "wallet/new_wallet/new_wallet_keys.jinja")[0]
    warning_block = source.split("<!-- Liquid multisig privacy warning -->")[1].split(
        "<!-- End Liquid multisig privacy warning -->"
    )[0]
    template = env.from_string(warning_block)
    liquid = template.render(
        wallet_type="multisig", specter=type("S", (), {"is_liquid": True})(), _=str
    )
    bitcoin = template.render(
        wallet_type="multisig", specter=type("S", (), {"is_liquid": False})(), _=str
    )
    single = template.render(
        wallet_type="simple", specter=type("S", (), {"is_liquid": True})(), _=str
    )
    assert "cosigners" in liquid.lower()
    assert "descriptor" in liquid.lower()
    assert "amounts" in liquid.lower()
    assert not bitcoin.strip()
    assert not single.strip()


def test_backup_warning_names_plaintext_secrets():
    templates = (
        Path(__file__).resolve().parents[1] / "src/cryptoadvance/specter/templates"
    )
    source = (templates / "settings/general_settings.jinja").read_text()
    backup_section = source.split('_("Backup and Restore")')[1].split(
        '_("Data Sources")'
    )[0]
    assert "ZIP" in backup_section
    assert "plaintext" in backup_section
    assert "blinding" in backup_section.lower()
