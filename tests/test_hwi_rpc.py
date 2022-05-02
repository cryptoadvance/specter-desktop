import logging
from cryptoadvance.specter.hwi_rpc import HWIBridge
from cryptoadvance.specter.util.descriptor import Descriptor


def test_enumerate(caplog):
    caplog.set_level(logging.DEBUG)

    hwi = HWIBridge()
    # bla = hwi.detect_device()

    res = hwi.enumerate(passphrase="")[0]

    # seems to be normal
    assert res["type"] == "trezor"
    assert res["model"] == "trezor_1"
    assert res["path"] == "webusb:003:1:1:1:2"
    assert res["error"].startswith(
        "Could not open client or get fingerprint information: Passphrase needs to be specified before the fingerprint information can be retrieved"
    )
    assert res["code"] == -12
    assert res["fingerprint"] == "1ef4e492"

    results = hwi.extract_xpubs(chain="test", device_type="trezor").split("\n")
    assert len(results) == 9
    assert results[0].startswith("[")
    assert results == None
