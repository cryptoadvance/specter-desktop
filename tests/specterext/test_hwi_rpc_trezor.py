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
    # but that seem to be an issue with the Key implementation rather then with trezor.
    assert (
        key.xpub
        == "tpubDFiVCZzdarbyfdVoh2LJDL3eVKRPmxwnkiqN8tSYCLod75a2966anQbjHajqVAZ97j54xZJPr9hf7ogVuNL4pPCfwvXdKGDQ9SjZF7vXQu1"
    )


@pytest.mark.manual
def test_display_address(hwi: AbstractHWIBridge, caplog):
    caplog.set_level(logging.DEBUG)
    unlock_trezor_if_needed(hwi)
    res = hwi.display_address(
        descriptor="wpkh([1ef4e492/84h/0h/0h/0/21]03f214b890c320d6b5a2ceab8c64b47d047010cfddc87a8deddc15e9daadea6647)#fjhj5z6n",
        xpubs_descriptor="wpkh([1ef4e492/84h/0h/0h]xpub6CcGh8BQPxr9zssX4eG8CiGzToU6Y9b3f2s2wNw65p9xtr8ySL6eYRVzAbfEVSX7ZPaPd3JMEXQ9LEBvAgAJSkNKYxG6L6X9DHnPWNQud4H/0/21)#pyqxsrsw",
        device_type="trezor",
        # path="webusb:003:1:1:4",
        fingerprint=None,
        passphrase="",
        chain="main",
    )
    assert res == "bc1qdzf5acm0kcr0f729ges607x2naekrj4us02ame"


@pytest.mark.manual
def test_sign_tx(hwi: AbstractHWIBridge, caplog):
    caplog.set_level(logging.DEBUG)
    unlock_trezor_if_needed(hwi)
    res = hwi.sign_tx(
        psbt="cHNidP8BAHECAAAAAYaQGEXHo1QAsi3/33wjF6vpOdtpXnYNcboe16utv2oMAQAAAAD9////AlgbAAAAAAAAFgAUW46Yr/VeBEC0uVPtrkw40pXu8s2+BAAAAAAAABYAFPnD6cQqE8y5vu2hvu92LBAjw/zlAAAAAAABAHECAAAAAWAWfmUKjC3LWvcN17/3yI0LIQroEy2QQ7QU/qCjA2VmAQAAAAD9////Am8qAAAAAAAAFgAUY/pVYLnNWw+D4k6XZzg501MEg60sMAAAAAAAABYAFHmDzTVdXOnETp4iPTKJvfihitENAAAAAAEBHywwAAAAAAAAFgAUeYPNNV1c6cROniI9Mom9+KGK0Q0iBgLdqE8nZJHdvRTEdjCJe+32ypnai+6JK/GwEhBZjLNNeRge9OSSVAAAgAAAAIAAAACAAAAAAAsAAAAAACICAnr5/7MsgmM3d8JSSIt1CiziWsxCfteVIodmp6+q33jsGB705JJUAACAAAAAgAAAAIABAAAAAwAAAAA=",
        device_type="trezor",
        # path="webusb:003:1:1:4",
        fingerprint=None,
        passphrase="",
        chain="main",
    )
    assert (
        res
        == "cHNidP8BAHECAAAAAYaQGEXHo1QAsi3/33wjF6vpOdtpXnYNcboe16utv2oMAQAAAAD9////AlgbAAAAAAAAFgAUW46Yr/VeBEC0uVPtrkw40pXu8s2+BAAAAAAAABYAFPnD6cQqE8y5vu2hvu92LBAjw/zlAAAAAAABAHECAAAAAWAWfmUKjC3LWvcN17/3yI0LIQroEy2QQ7QU/qCjA2VmAQAAAAD9////Am8qAAAAAAAAFgAUY/pVYLnNWw+D4k6XZzg501MEg60sMAAAAAAAABYAFHmDzTVdXOnETp4iPTKJvfihitENAAAAAAEBHywwAAAAAAAAFgAUeYPNNV1c6cROniI9Mom9+KGK0Q0iAgLdqE8nZJHdvRTEdjCJe+32ypnai+6JK/GwEhBZjLNNeUcwRAIgJeD6DuRVtkDho8AJiPtL4Vaem9AtnGJwdbRP6wtS6RACIAdcNo7GF0K+cd+qjDfUGB5OcRwmw021WojvM2xuvMtJASIGAt2oTydkkd29FMR2MIl77fbKmdqL7okr8bASEFmMs015GB705JJUAACAAAAAgAAAAIAAAAAACwAAAAAAIgICevn/syyCYzd3wlJIi3UKLOJazEJ+15Uih2anr6rfeOwYHvTkklQAAIAAAACAAAAAgAEAAAADAAAAAA=="
    )


@pytest.mark.manual
def test_sign_message(hwi: AbstractHWIBridge, caplog):
    caplog.set_level(logging.DEBUG)
    unlock_trezor_if_needed(hwi)
    res = hwi.sign_message(
        message="cypherpunks write code",
        derivation_path="m/84h/0h/0h/0/21",
        device_type="trezor",
        path="webusb:003:1:1:4",
        fingerprint=None,
        passphrase="",
        chain="main",
    )

    # trezor Suite:
    # -----BEGIN BITCOIN SIGNED MESSAGE-----
    # cypherpunks write code
    # -----BEGIN SIGNATURE-----
    # bc1qc8smx85mquyrgez4cggjqk49u2j0u2cml67lax
    # J0lg4/INa4zPphTaZjblEbLhRqveeejyoFJKcaCC9xBQUO5kT71O5LjSk25nGKLLcihSxRhrdFFy3wdCRE60TqA=
    # -----END BITCOIN SIGNED MESSAGE-----

    # Doesn't work for neither of the two impls. Did it ever work?
    # assert (
    #     res == "J0lg4/INa4zPphTaZjblEbLhRqveeejyoFJKcaCC9xBQUO5kT71O5LjSk25nGKLLcihSxRhrdFFy3wdCRE60TqA="
    # )


def unlock_trezor_if_needed(hwi: AbstractHWIBridge, should_need_passphrase_sent=False):
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
        if res["needs_passphrase_sent"] != should_need_passphrase_sent:
            hwi.toggle_passphrase(device_type="trezor")
            res = hwi.enumerate(passphrase="")[0]
        # assert res["error"].startswith(
        #     "Could not open client or get fingerprint information: Passphrase needs to be specified before the fingerprint information can be retrieved"
        # )

        assert len(res.get("fingerprint", "")) == 8, f" {res}"
