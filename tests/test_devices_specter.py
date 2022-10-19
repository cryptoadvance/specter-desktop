from pathlib import Path
from cryptoadvance.specter.device import Device

from cryptoadvance.specter.devices.specter import (
    Specter,
    get_wallet_fingerprint,
    get_wallet_qr_descriptor,
)
from cryptoadvance.specter.key import Key
from cryptoadvance.specter.managers.device_manager import DeviceManager
from cryptoadvance.specter.managers.wallet_manager import WalletManager
from cryptoadvance.specter.wallet import Wallet
from mock import MagicMock
import logging

from cryptoadvance.specterext.devhelp.devices.devhelpdevice import DevhelpDevice


def test_device_blueprint():
    device = Device("somename", "somealias", [], [], "muh", None)
    assert device.blueprint() == "static"
    assert Device.blueprint() == "static"
    other_device = DevhelpDevice("somename", "somealias", [], [], "muh", None)
    print(other_device.blueprint())
    assert other_device.blueprint() == "devhelp_endpoint.static"
    assert DevhelpDevice.blueprint() == "devhelp_endpoint.static"


def test_get_wallet_qr_descriptor(
    caplog, specter_regtest_configured, acc0key_hold_accident: Key
):
    # logging.getLogger("cryptoadvance.specter.rpc").setLevel(logging.DEBUG)
    wallet_manager: WalletManager = specter_regtest_configured.wallet_manager
    specter_device = specter_regtest_configured.device_manager.add_device(
        "specter_device", "specter", [acc0key_hold_accident]
    )
    assert isinstance(specter_device, Specter)
    print(specter_device.keys[0].json)
    specter_device.keys
    wallet: Wallet = wallet_manager.create_wallet(
        "someName", 1, "wpkh", [specter_device.keys[0]], [specter_device]
    )

    assert wallet != None

    assert (
        get_wallet_qr_descriptor(wallet)
        == "wpkh([ccf2e5c3/84h/1h/0h]tpubDCnYSFavtHxX7w8S8GyYwQ2bQPeA5fSVd2WqFzY7BeE1DKhqvq9Qdyz4AM13xGQvo1J5c46ixbW84evZhqerR3eh1r2tndT8r51p3sxiQ8F)"
    )
    assert get_wallet_fingerprint(wallet) == b"Kh\xb5*"
