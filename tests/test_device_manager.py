import os
from cryptoadvance.specter.devices.device import Device
from cryptoadvance.specter.devices.key import Key
from cryptoadvance.specter.device_manager import DeviceManager


def test_DeviceManager(empty_data_folder):
    # A DeviceManager manages devices, specifically the persistence 
    # of them via json-files in an empty data folder
    dm = DeviceManager(data_folder=empty_data_folder)
    # initialization will load from the folder but it's empty at first
    assert len(dm.devices) == 0
    # a device has a name, a type and a list of keys
    a_key = Key(
        'Vpub5n9kKePTPPGtw3RddeJWJe29epEyBBcoHbbPi5HhpoG2kTVsSCUzsad33RJUt3LktEUUPPofcZczuudnwR7ZgkAkT6N2K2Z7wdyjYrVAkXM',
        '08686ac6',
        'm/48h/1h/0h/2h',
        'wsh', 
        'tpubDFHpKypXq4kwUrqLotPs6fCic5bFqTRGMBaTi9s5YwwGymE8FLGwB2kDXALxqvNwFxB1dLWYBmmeFVjmUSdt2AsaQuPmkyPLBKRZW8BGCiL'
    )
    # the DeviceManager doesn't care so much about the content of a key
    # so this is a minimal valid "key":
    another_key = Key.from_json({
        'original': 'blub'
    })
    dm.add_device("some_name","the_type",[a_key, another_key])
    # A json file was generated for the new device:
    assert os.path.isfile(dm.devices['some_name'].fullpath)
    # You can access the new device either by its name of with `get_by_alias` by its alias
    assert dm.get_by_alias('some_name').name == 'some_name'
    assert dm.get_by_alias('some_name').device_type == 'the_type'
    assert dm.get_by_alias('some_name').keys[0].fingerprint == '08686ac6'
    # Now it has a length of 1
    assert len(dm.devices) == 1
    # and is iterable
    assert [the_type.device_type for the_type in dm.devices.values()] == ['the_type']
    # The DeviceManager will return Device-Types (subclass of dict)
    assert type(dm.devices['some_name']) == Device

    # The DeviceManager also has a `devices_names` property, returning a sorted list of the names of all devices
    assert dm.devices_names == ['some_name']
    dm.add_device("another_name","the_type",[a_key, another_key])
    assert dm.devices_names == ['another_name', 'some_name']

    # You can also remove a device - which will delete its json and remove it from the manager
    another_device_fullpath = dm.devices['another_name'].fullpath
    assert os.path.isfile(another_device_fullpath)
    dm.remove_device(dm.devices['another_name'])
    assert not os.path.isfile(another_device_fullpath)
    assert len(dm.devices) == 1
    assert dm.devices_names == ['some_name']

    # A device is mainly a Domain-Object which assumes an underlying 
    # json-file which can be found in the "fullpath"-key
    # It derives from a dict
    # It needs a DeviceManager to be injected and can't reasonable
    # be created on your own.
    # It has 5 dict keys: `fullpath`, `alias`, `name`, `type`, `keys`
    some_device = dm.devices['some_name']
    assert some_device.fullpath == empty_data_folder + '/some_name.json'
    assert some_device.alias == 'some_name'
    assert some_device.name == 'some_name'
    assert some_device.device_type == 'the_type'
    assert len(some_device.keys) == 2
    assert some_device.keys[0] == a_key
    assert some_device.keys[1] == another_key

    # Keys can be added and removed. It will instantly update the underlying json
    # Adding keys can be done by passing an array of keys object to the `add_keys` method of a device
    # A key dict must contain an `original` property
    third_key = Key.from_json({
        'original': 'third_key'
    })
    some_device.add_keys([third_key])
    assert len(some_device.keys) == 3
    assert some_device.keys[0] == a_key
    assert some_device.keys[1] == another_key
    assert some_device.keys[2] == third_key

    # adding an existing key will do nothing
    some_device.add_keys([third_key])
    assert len(some_device.keys) == 3
    assert some_device.keys[0] == a_key
    assert some_device.keys[1] == another_key
    assert some_device.keys[2] == third_key

    # Removing a key can be done by passing the `original` property of the key to remove to the `remove_key` method of a device
    some_device.remove_key(third_key)
    assert len(some_device.keys) == 2
    assert some_device.keys[0] == a_key
    assert some_device.keys[1] == another_key

    # removing a none existing key will do nothing
    some_device.remove_key(third_key)
    assert len(some_device.keys) == 2
    assert some_device.keys[0] == a_key
    assert some_device.keys[1] == another_key
