"""Opt-in tests requiring a physical Blockstream Jade attached + operator.

Skipped by default. Enable with::

    pytest --run-jade-hardware tests/test_jade_hardware.py -s

The ``-s`` is required so that operator prompts reach your terminal.

Operator setup
--------------
- Connect the Jade over USB and unlock it.
- For the signing test, the Jade must be initialised with a known seed
  matching ``tests/fixtures/jade_hardware.psbt`` (see fixture for the
  derivation paths used). If the fixture is absent the signing test
  skips with a hint.
"""

from pathlib import Path

import pytest

from cryptoadvance.specter.hwi_rpc import HWIBridge


FIXTURE_DIR = Path(__file__).parent / "fixtures"
PSBT_FIXTURE = FIXTURE_DIR / "jade_hardware.psbt"


def _enumerate_jade(bridge: HWIBridge):
    devs = bridge.enumerate()
    return [d for d in devs if d.get("type") == "jade"]


def _prompt(msg: str) -> None:
    print(f"\n>>> {msg}")
    try:
        input(">>> Press Enter when ready... ")
    except EOFError:
        # Non-interactive runner: continue without blocking.
        pass


@pytest.mark.jade_hardware
def test_jade_enumerate_via_specter():
    """Jade is detected by Specter's HWIBridge and reports a fingerprint."""
    _prompt("Connect and unlock the Jade.")
    bridge = HWIBridge()
    jades = _enumerate_jade(bridge)
    assert jades, "no Jade detected — connect, unlock, and rerun"
    jade = jades[0]
    assert jade.get("fingerprint"), f"Jade enumerated without fingerprint: {jade}"
    assert jade.get("path"), f"Jade enumerated without path: {jade}"


@pytest.mark.jade_hardware
def test_jade_extract_xpub_via_specter():
    """Specter can pull an xpub at a known derivation from Jade."""
    _prompt("Unlock the Jade. You may be asked to confirm the xpub export.")
    bridge = HWIBridge()
    jades = _enumerate_jade(bridge)
    assert jades, "no Jade detected"
    fingerprint = jades[0]["fingerprint"]

    # BIP84 native segwit, mainnet account 0
    xpub_line = bridge.extract_xpub(
        derivation="m/84h/0h/0h",
        device_type="jade",
        fingerprint=fingerprint,
    )
    assert xpub_line, "extract_xpub returned empty"
    assert xpub_line.startswith("["), f"unexpected format: {xpub_line!r}"
    assert "]" in xpub_line, f"unexpected format: {xpub_line!r}"
    body = xpub_line.split("]", 1)[1].strip()
    assert body.startswith(("xpub", "zpub", "ypub")), f"unexpected xpub: {body[:8]}"


@pytest.mark.jade_hardware
def test_jade_sign_psbt_via_specter():
    """End-to-end: Specter signs a canned PSBT through Jade.

    Requires ``tests/fixtures/jade_hardware.psbt`` whose input derivations
    match the seed loaded on the attached Jade. Skipped if absent.
    """
    if not PSBT_FIXTURE.exists():
        pytest.skip(
            f"missing fixture {PSBT_FIXTURE}; create one whose input paths "
            "match the seed on the test Jade"
        )

    psbt_b64 = PSBT_FIXTURE.read_text().strip()

    _prompt("Unlock the Jade. You will be asked to confirm the transaction on device.")
    bridge = HWIBridge()
    jades = _enumerate_jade(bridge)
    assert jades, "no Jade detected"
    fingerprint = jades[0]["fingerprint"]

    signed = bridge.sign_tx(
        psbt=psbt_b64,
        device_type="jade",
        fingerprint=fingerprint,
    )
    assert signed, "sign_tx returned empty"
    assert signed != psbt_b64, "PSBT was returned unsigned"
