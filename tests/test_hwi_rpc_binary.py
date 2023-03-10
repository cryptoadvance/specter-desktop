"""
    This is a manual test file. You can only run those tests manually because hardware needs to 
    be connected. As the stdin needs to be used, you have to run these tests like this:

    pytest tests/test_hwi_rpc_binary.py -m manual -s -vv
"""

import pytest
from cryptoadvance.specterext.hwi.hwi_rpc import AbstractHWIBridge
from cryptoadvance.specterext.hwi.hwi_rpc_binary import HWIBinaryBridge
from cryptoadvance.specterext.hwi.hwi_rpc_hwilib import HWILibBridge
from cryptoadvance.specter.key import Key
import logging
from hwilib.errors import DeviceNotReadyError


@pytest.fixture(
    params=[
        # HWILibBridge,
        HWIBinaryBridge
    ]
)
def hwi(request):
    instance = request.param()
    # There is a bug https://github.com/bitcoin-core/HWI/issues/636 which makes it necessary
    # to pass the device-path for certain commands
    # instance.path = instance.enumerate()["path"]
    return instance


@pytest.mark.manual
def test_trezor_enumerate(hwi: AbstractHWIBridge, caplog):
    caplog.set_level(logging.DEBUG)
    unlock_trezor_if_needed(hwi)


@pytest.mark.manual
def test_trezor_prompt_pin(hwi: AbstractHWIBridge, caplog):
    unlock_trezor_if_needed(hwi)


@pytest.mark.manual
def test_trezor_toggle_passphrase(hwi: AbstractHWIBridge, caplog):
    caplog.set_level(logging.DEBUG)
    unlock_trezor_if_needed(hwi)
    res = hwi.toggle_passphrase(device_type="trezor", passphrase="Blub")
    assert res == {"success": True}


@pytest.mark.manual
def test_trezor_extract_xpubs(hwi: AbstractHWIBridge, caplog):
    caplog.set_level(logging.DEBUG)
    unlock_trezor_if_needed(hwi)
    res = hwi.extract_xpubs(
        account=0,
        device_type="trezor",
        path=None,
        fingerprint=None,
        passphrase="",
        chain="",
    )
    res_arr = res.split("\n")
    assert len(res_arr) == 9
    for xpub in res_arr:
        if xpub == "":
            continue
        print(xpub)
        Key.parse_xpub(xpub)


@pytest.mark.manual
def test_trezor_extract_xpub(hwi: AbstractHWIBridge, caplog):
    caplog.set_level(logging.DEBUG)
    unlock_trezor_if_needed(hwi)
    res = hwi.extract_xpub(
        derivation="m/0h/0h",
        device_type="trezor",
        path=None,
        fingerprint=None,
        passphrase="",
        chain="main",
    )
    print(f"resulting xpub: {res}")
    key = Key.parse_xpub(res)
    assert key.fingerprint == "1ef4e492"
    assert key.derivation == "m/0h/0h"
    assert (
        key.xpub
        == "xpub6BGiTwRU3zniWXgR6wb7De8uez1UYLpgfqxR9Qtu9ye4ToWPNUdu9rNTVBSkZ5HTMW6SuKaGE3ypZFRdGQccekSj55DZ9XnDxh3Fj5oL6t3"
    )
    res = hwi.extract_xpub(
        derivation="m/48h/1h/0h/1h",
        device_type="trezor",
        path=None,
        fingerprint="1ef4e492",
        passphrase="blub",
        chain="testnet",
    )
    print(f"resulting xpub: {res}")
    key = Key.parse_xpub(res)
    assert key.fingerprint == "1ef4e492"
    assert key.derivation == "m/48h/1h/0h/1h"  # Nested Mutisig on testnet
    # I don't understand why it's not a Upub?
    # assert key.xpub == "Upub5Tk9tZtdzVaTGWtygRTKDDmaN5vfB59pn2L5MQyH6BkVpg2Y5J95rtpQndjmXNs3LNFiy8zxpHCTtvxxeePjgipF7moTHQZhe3E5uPzDXh8"
    assert (
        key.xpub
        == "tpubDFiVCZzdarbyfdVoh2LJDL3eVKRPmxwnkiqN8tSYCLod75a2966anQbjHajqVAZ97j54xZJPr9hf7ogVuNL4pPCfwvXdKGDQ9SjZF7vXQu1"
    )
    assert False


def unlock_trezor_if_needed(hwi):
    res = hwi.enumerate(passphrase="")[0]
    print(f"type(result) = {type(res)}")
    # seems to be normal
    assert res["type"] == "trezor"
    assert res["model"] == "trezor_1"
    assert res["path"].startswith("webusb:003:1:1:")
    if res["needs_pin_sent"]:
        assert res["error"].startswith(
            "Could not open client or get fingerprint information: Trezor is locked"
        )
        res = hwi.prompt_pin(device_type="trezor", passphrase="")
        assert res["success"] == True
        # monkeypatch.setattr('sys.stdin', io.StringIO('my input'))
        pin = input("Enter pin: ")
        print(f"pin entered: {pin}")

        res = hwi.send_pin(pin, device_type="trezor", passphrase="")
        assert res["success"] == True

    else:
        # assert res["error"].startswith(
        #     "Could not open client or get fingerprint information: Passphrase needs to be specified before the fingerprint information can be retrieved"
        # )
        assert len(res.get("fingerprint", "")) == 8, f" {res}"
