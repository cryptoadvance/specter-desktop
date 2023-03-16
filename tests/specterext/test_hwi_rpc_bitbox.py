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
def test_bitbox_enumerate(hwi: AbstractHWIBridge, caplog):
    caplog.set_level(logging.DEBUG)
    unlock_bitbox_if_needed(hwi)


@pytest.mark.manual
def test_bitbox_prompt_pin(hwi: AbstractHWIBridge, caplog):
    unlock_bitbox_if_needed(hwi)


@pytest.mark.manual
def test_bitbox_extract_xpubs(hwi: AbstractHWIBridge, caplog):
    caplog.set_level(logging.DEBUG)
    unlock_bitbox_if_needed(hwi)
    res = hwi.extract_xpubs(
        account=0,
        device_type="bitbox02",
        path=None,
        fingerprint=None,
        passphrase="",
        chain="",
    )
    res_arr = res.split("\n")
    for xpub in res_arr:
        if xpub == "":
            continue
        print(xpub)
        Key.parse_xpub(xpub)
    assert len(res_arr) == 9


@pytest.mark.manual
def test_bitbox_extract_xpub(hwi: AbstractHWIBridge, caplog):
    caplog.set_level(logging.DEBUG)
    unlock_bitbox_if_needed(hwi)
    res = hwi.extract_xpub(
        derivation="m/84h/0h/1h",
        device_type="bitbox02",
        path=None,
        fingerprint=None,
        passphrase="",
        chain="main",
    )
    print(f"resulting xpub: {res}")
    key = Key.parse_xpub(res)
    assert key.fingerprint == "cd273ae3"
    assert key.derivation == "m/84h/0h/1h"
    assert (
        key.xpub
        == "xpub6CBoEYQErJLQ65uf8Z39dwMfRTZ9EsLsna9MpQ95G5EUtXe66pUjhrSkDnj6DJMCXkvQfTccnqmgaAryb5mJJLv1QZciauNLCeaqmBfB23A"
    )
    res = hwi.extract_xpub(
        derivation="m/48h/1h/0h/1h",
        device_type="bitbox02",
        path=None,
        fingerprint="cd273ae3",
        passphrase="",
        chain="testnet",
    )
    print(f"resulting xpub: {res}")
    key = Key.parse_xpub(res)
    assert key.fingerprint == "cd273ae3"
    assert key.derivation == "m/48h/1h/0h/1h"  # Nested Mutisig on testnet
    # I don't understand why it's not a Upub?
    # assert key.xpub == "Upub5Tk9tZtdzVaTGWtygRTKDDmaN5vfB59pn2L5MQyH6BkVpg2Y5J95rtpQndjmXNs3LNFiy8zxpHCTtvxxeePjgipF7moTHQZhe3E5uPzDXh8"
    # but that seem to be an issue with the Key implementation rather then with bitbox02.
    assert (
        key.xpub
        == "tpubDEUtjvNPZjY8b7vALPmPmp12iCMwudukQdhJ7NovWoRAvSdaocyajJxxdtQoUjbziSqy8oswqNjXdLGLqUjizrxHWB7pLeXfQAF9Jxsr5Do"
    )


@pytest.mark.manual
def test_display_address(hwi: AbstractHWIBridge, caplog):
    caplog.set_level(logging.DEBUG)
    unlock_bitbox_if_needed(hwi)
    res = hwi.display_address(
        descriptor="wpkh([cd273ae3/84h/0h/0h/0/14]03854607c89e2cc0af6a348ac3084c655267545a71926d9ffc291d72a0bac2d34b)#6lgn77hx",
        xpubs_descriptor="wpkh([cd273ae3/84h/0h/0h]xpub6CBoEYQErJLQ3HUu6Svnm5QCd1LxptPxDaTwDuB7QAunM5if2WU6cdvK7bh2V2Lw62LCJPPNLxXnVbUM7yDiUnjCNZ6qXN9L5VFLHEeTBES/0/14)#vfl3htjv",
        device_type="bitbox02",
        # path="webusb:003:1:1:4",
        fingerprint=None,
        passphrase="",
        chain="main",
    )
    assert res == "bc1q0pcxq4mkuch3lxl7acffda2vwwy0824uc839zv"


@pytest.mark.manual
def test_sign_tx(hwi: AbstractHWIBridge, caplog):
    caplog.set_level(logging.DEBUG)
    unlock_bitbox_if_needed(hwi)
    res = hwi.sign_tx(
        psbt="cHNidP8BAHECAAAAAYaQGEXHo1QAsi3/33wjF6vpOdtpXnYNcboe16utv2oMAQAAAAD9////AlgbAAAAAAAAFgAUW46Yr/VeBEC0uVPtrkw40pXu8s2+BAAAAAAAABYAFPnD6cQqE8y5vu2hvu92LBAjw/zlAAAAAAABAHECAAAAAWAWfmUKjC3LWvcN17/3yI0LIQroEy2QQ7QU/qCjA2VmAQAAAAD9////Am8qAAAAAAAAFgAUY/pVYLnNWw+D4k6XZzg501MEg60sMAAAAAAAABYAFHmDzTVdXOnETp4iPTKJvfihitENAAAAAAEBHywwAAAAAAAAFgAUeYPNNV1c6cROniI9Mom9+KGK0Q0iBgLdqE8nZJHdvRTEdjCJe+32ypnai+6JK/GwEhBZjLNNeRge9OSSVAAAgAAAAIAAAACAAAAAAAsAAAAAACICAnr5/7MsgmM3d8JSSIt1CiziWsxCfteVIodmp6+q33jsGB705JJUAACAAAAAgAAAAIABAAAAAwAAAAA=",
        device_type="bitbox02",
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
    unlock_bitbox_if_needed(hwi)
    res = hwi.sign_message(
        message="cypherpunks write code",
        derivation_path="m/84h/0h/0h/0/21",
        device_type="bitbox02",
        path="webusb:003:1:1:4",
        fingerprint=None,
        passphrase="",
        chain="main",
    )


def unlock_bitbox_if_needed(hwi: AbstractHWIBridge, should_need_passphrase_sent=False):
    res = hwi.enumerate(passphrase="")[0]
    print(f"type(result) = {type(res)}")
    # seems to be normal
    assert res["type"] == "bitbox02"
    assert res["model"] == "bitbox02_multi"
    assert res["path"].startswith("3-1.1.1.2:1.0")
    # The bitbox will not be enumerated if not unlocked
    assert not res["needs_pin_sent"]
    if res["needs_passphrase_sent"] != should_need_passphrase_sent:
        hwi.toggle_passphrase(device_type="bitbox")
        res = hwi.enumerate(passphrase="")[0]
    # assert res["error"].startswith(
    #     "Could not open client or get fingerprint information: Passphrase needs to be specified before the fingerprint information can be retrieved"
    # )

    assert len(res.get("fingerprint", "")) == 8, f" {res}"


@pytest.mark.manual
def test_misc(rootkey_keen_join, rootkey_ghost_machine, rootkey_hold_accident):
    pass
