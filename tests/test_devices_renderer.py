from cryptoadvance.specter.devices.renderer import HWIDeviceRenderer, DeviceRenderer
from cryptoadvance.specter.devices import GenericDevice
from cryptoadvance.specter.wallet_manager import WalletManager


def test_DeviceRenderer(bitcoin_regtest, devices_filled_data_folder, device_manager):
    device = device_manager.get_by_alias("trezor")
    assert device.device_type == "trezor"
    assert device.__class__.name == "Trezor"

    device.render("device_scripts")


def test_HWIRenderer(bitcoin_regtest, devices_filled_data_folder, device_manager):
    device = device_manager.get_by_alias("specter")
    device.render("button_toggle_password")
