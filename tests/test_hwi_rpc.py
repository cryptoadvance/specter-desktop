""" This is just a manual test to understand how HWI works. All tests are marked skipped as hardware plugged in is necessary.
    Don't take this as best practise. This is just something to test difference in behaviour for migration from HWI 2.0.2 to 2.1.0

    To get it to run:
    * comment the test: @pytest.mark.skip()
    * Plugin yout trezor
    * Run the test like: pytest tests/test_hwi_rpc.py::test_enumerate_trezor  -vv -s
    * Type in your Pin
    * Success!
"""

import logging
import io
import pytest
from cryptoadvance.specter.hwi_rpc import HWIBridge
from cryptoadvance.specter.key import Key
from cryptoadvance.specter.util.descriptor import Descriptor


@pytest.mark.skip()
def test_trezor(caplog, monkeypatch):
    """In order to get this test working, you have to run it with "-s":
    pytest tests/test_hwi_rpc.py::test_enumerate_trezor  -vv -s
    """
    caplog.set_level(logging.DEBUG)

    hwi = HWIBridge()
    # bla = hwi.detect_device()

    res = hwi.enumerate(passphrase="")[0]
    print(res)
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

        res = hwi.send_pin(pin, device_type="trezor", passphrase="")
        assert res["success"] == True

    else:
        assert res["error"].startswith(
            "Could not open client or get fingerprint information: Passphrase needs to be specified before the fingerprint information can be retrieved"
        )
        assert len(res["fingerprint"]) == 8
    results = hwi.extract_xpubs(chain="test", device_type="trezor").split("\n")
    assert len(results) == 9
    assert results[0].startswith("[")
    print(results[0])
    # You can construct keys from the results:
    key: Key = Key.parse_xpub(results[0])
    assert len(key.fingerprint) == 8
    assert key.derivation == "m/49h/0h/0h"
    assert key.xpub.startswith("xpub")


@pytest.mark.skip()
def test_jade(caplog):
    caplog.set_level(logging.DEBUG)

    hwi = HWIBridge()
    # bla = hwi.detect_device()

    res = hwi.enumerate(passphrase="")[0]

    # seems to be normal
    assert res["type"] == "jade"
    assert res["model"] == "jade"
    assert res["path"] == "/dev/ttyUSB0"
    assert res["error"].startswith(
        "Could not open client or get fingerprint information: __init__() got an unexpected keyword argument 'timeout'"
    )
    assert res["code"] == -13
    assert res["fingerprint"] == "4c6de3ce"

    results = hwi.extract_xpubs(
        chain="main", device_type="jade", path="/dev/ttyUSB0"
    ).split("\n")
    assert len(results) == 9
    assert results[0].startswith("[")
