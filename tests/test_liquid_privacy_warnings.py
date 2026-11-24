"""Liquid privacy warnings without browser fixtures."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader


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
