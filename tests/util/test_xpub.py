import pytest

from cryptoadvance.specter.util.xpub import (
    convert_xpub_prefix,
    get_xpub_fingerprint,
)

### Tests for xpub


def test_convert_to_ypub(ghost_machine_xpub_49, ghost_machine_ypub):
    new_prefix = b"\x04\x9d\x7c\xb2"
    assert convert_xpub_prefix(ghost_machine_xpub_49, new_prefix) == ghost_machine_ypub


def test_convert_to_zpub(ghost_machine_xpub_84, ghost_machine_zpub):
    new_prefix = b"\x04\xb2\x47\x46"
    assert convert_xpub_prefix(ghost_machine_xpub_84, new_prefix) == ghost_machine_zpub


def test_convert_ypub_back(ghost_machine_ypub, ghost_machine_xpub_49):
    new_prefix = b"\x04\x88\xb2\x1e"
    assert convert_xpub_prefix(ghost_machine_ypub, new_prefix) == ghost_machine_xpub_49


def test_convert_zpub_back(ghost_machine_zpub, ghost_machine_xpub_84):
    new_prefix = b"\x04\x88\xb2\x1e"
    assert convert_xpub_prefix(ghost_machine_zpub, new_prefix) == ghost_machine_xpub_84


def test_convert_to_upub(ghost_machine_tpub_49, ghost_machine_upub):
    new_prefix = b"\x04\x4a\x52\x62"
    assert convert_xpub_prefix(ghost_machine_tpub_49, new_prefix) == ghost_machine_upub


def test_convert_to_vpub(ghost_machine_tpub_84, ghost_machine_vpub):
    new_prefix = b"\x04\x5f\x1c\xf6"
    assert convert_xpub_prefix(ghost_machine_tpub_84, new_prefix) == ghost_machine_vpub


def test_get_xpub_fingerprint(ghost_machine_xpub_44):
    # fingerprint from https://jlopp.github.io/xpub-converter/
    assert get_xpub_fingerprint(ghost_machine_xpub_44).hex() == "81f802e3"
