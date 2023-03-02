import os
import logging
from unittest.mock import MagicMock
from cryptoadvance.specter.devices.generic import GenericDevice
from cryptoadvance.specter.key import Key
from cryptoadvance.specter.managers.device_manager import DeviceManager
from cryptoadvance.specter.managers.wallet_manager import WalletManager


def test_DeviceManager(empty_data_folder, a_key, a_tpub_only_key):
    # A DeviceManager manages devices, specifically the persistence
    # of them via json-files in an empty data folder
    dm = DeviceManager(data_folder=empty_data_folder)
    # initialization will load from the folder but it's empty at first
    assert len(dm.devices) == 0
    # a device has a name, a type and a list of keys
    a_key = Key(
        "Vpub5n9kKePTPPGtw3RddeJWJe29epEyBBcoHbbPi5HhpoG2kTVsSCUzsad33RJUt3LktEUUPPofcZczuudnwR7ZgkAkT6N2K2Z7wdyjYrVAkXM",
        "08686ac6",
        "m/48h/1h/0h/2h",
        "wsh",
        "",
        "tpubDFHpKypXq4kwUrqLotPs6fCic5bFqTRGMBaTi9s5YwwGymE8FLGwB2kDXALxqvNwFxB1dLWYBmmeFVjmUSdt2AsaQuPmkyPLBKRZW8BGCiL",
    )
    # the DeviceManager doesn't care so much about the content of a key
    # so let's add two keys:
    dm.add_device("some_name", "the_type", [a_key, a_tpub_only_key])
    # A json file was generated for the new device:
    assert os.path.isfile(dm.devices["some_name"].fullpath)
    # You can access the new device either by its name of with `get_by_alias` by its alias
    assert dm.get_by_alias("some_name").name == "some_name"
    # unknown device is replaced by 'other'
    assert dm.get_by_alias("some_name").device_type == "other"
    assert dm.get_by_alias("some_name").keys[0].fingerprint == "08686ac6"
    # Now it has a length of 1
    assert len(dm.devices) == 1
    # and is iterable
    assert [the_type.device_type for the_type in dm.devices.values()] == ["other"]
    # The DeviceManager will return Device-Types (subclass of dict)
    # any unknown type is replaced by GenericDevice
    assert type(dm.devices["some_name"]) == GenericDevice

    # The DeviceManager also has a `devices_names` property, returning a sorted list of the names of all devices
    assert dm.devices_names == ["some_name"]
    dm.add_device("another_name", "the_type", [a_key, a_tpub_only_key])
    assert dm.devices_names == ["another_name", "some_name"]

    # You can also remove a device - which will delete its json and remove it from the manager
    another_device_fullpath = dm.devices["another_name"].fullpath
    assert os.path.isfile(another_device_fullpath)
    dm.remove_device(dm.devices["another_name"])
    assert not os.path.isfile(another_device_fullpath)
    assert len(dm.devices) == 1
    assert dm.devices_names == ["some_name"]

    # A device is mainly a Domain-Object which assumes an underlying
    # json-file which can be found in the "fullpath"-key
    # It derives from a dict
    # It needs a DeviceManager to be injected and can't reasonable
    # be created on your own.
    # It has 5 dict keys: `fullpath`, `alias`, `name`, `type`, `keys`
    some_device = dm.devices["some_name"]
    assert some_device.fullpath == empty_data_folder + "/some_name.json"
    assert some_device.alias == "some_name"
    assert some_device.name == "some_name"
    assert some_device.device_type == "other"
    assert len(some_device.keys) == 2
    assert some_device.keys[0] == a_key
    assert some_device.keys[1] == a_tpub_only_key

    # Keys can be added and removed. It will instantly update the underlying json
    # Adding keys can be done by passing an array of keys object to the `add_keys` method of a device
    # A key dict must contain an `original` property
    third_key = Key.from_json(
        {
            "original": "tpubDEmTg3b5aPNFnkHXx481F3h9dPSVJiyvqV24dBMXWncoRRu6VJzPDeEtQ4H7EnRtLbn2aPkxhTn8odWXsXkSRDdmAvCCrPmfjfPSVswfDhg"
        }
    )
    some_device.add_keys([third_key])
    assert len(some_device.keys) == 3
    assert some_device.keys[0] == a_key
    assert some_device.keys[1] == a_tpub_only_key
    assert some_device.keys[2] == third_key

    # adding an existing key will do nothing
    some_device.add_keys([third_key])
    assert len(some_device.keys) == 3
    assert some_device.keys[0] == a_key
    assert some_device.keys[1] == a_tpub_only_key
    assert some_device.keys[2] == third_key

    # Removing a key can be done by passing the `original` property of the key to remove to the `remove_key` method of a device
    some_device.remove_key(third_key)
    assert len(some_device.keys) == 2
    assert some_device.keys[0] == a_key
    assert some_device.keys[1] == a_tpub_only_key

    # removing a none existing key will do nothing
    some_device.remove_key(third_key)
    assert len(some_device.keys) == 2
    assert some_device.keys[0] == a_key
    assert some_device.keys[1] == a_tpub_only_key


def test_DeviceManager_supported_devices_for_chain(empty_data_folder):
    # A DeviceManager manages devices, specifically the persistence
    # of them via json-files in an empty data folder
    dm = DeviceManager(data_folder=empty_data_folder)
    specter_mock = MagicMock()
    specter_mock.chain = False
    device_classes = dm.supported_devices_for_chain(specter=specter_mock)
    for device_class in device_classes:
        assert device_class.__class__ == type
    specter_mock.chain = True
    device_classes = dm.supported_devices_for_chain(specter=specter_mock)
    for device_class in device_classes:
        assert device_class.__class__ == type
    specter_mock.is_liquid = True
    device_classes = dm.supported_devices_for_chain(specter=specter_mock)
    for device_class in device_classes:
        assert device_class.__class__ == type


def test_device_wallets(
    bitcoin_regtest, devices_filled_data_folder, device_manager, caplog
):
    caplog.set_level(logging.DEBUG)
    wm = WalletManager(
        devices_filled_data_folder,
        bitcoin_regtest.get_rpc(),
        "regtest",
        device_manager,
    )
    device = device_manager.get_by_alias("trezor")
    assert len(device.wallets(wm)) == 0
    wallet = wm.create_wallet("a_test_wallet", 1, "wpkh", [device.keys[5]], [device])
    assert len(device.wallets(wm)) == 1
    assert device.wallets(wm)[0].alias == wallet.alias
    second_device = device_manager.get_by_alias("specter")
    multisig_wallet = wm.create_wallet(
        "multisig_wallet_for_device_test",
        1,
        "wsh",
        [device.keys[7], second_device.keys[0]],
        [device, second_device],
    )

    assert len(device.wallets(wm)) == 2
    assert device.wallets(wm)[0].alias == wallet.alias
    assert device.wallets(wm)[1].alias == multisig_wallet.alias

    assert len(second_device.wallets(wm)) == 1
    assert second_device.wallets(wm)[0].alias == multisig_wallet.alias
