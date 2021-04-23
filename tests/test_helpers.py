import logging


def test_deep_update():
    import cryptoadvance.specter.helpers as helpers

    base_value = {
        "pli": {"pla": "blub", "yes": "yes"},
        "pli2": ["arrayelm1", "arrayelm2", "arrayelm3"],
        "pli3": "aStringValue",
    }
    assert len(base_value) == 3
    assert len(base_value["pli"]) == 2
    assert len(base_value["pli2"]) == 3

    update_value = {
        "newRootKey": {"pla": "blub"},
        "pli": {"newSubKey": "blub2"},
        "pli2": ["arrayelm4", "arrayelm5"],
    }
    helpers.deep_update(base_value, update_value)
    # There is now a newRootKey
    assert len(base_value) == 4
    # keys get added
    assert len(base_value["pli"]) == 3
    # Arrays get replaced, not appended!
    assert len(base_value["pli2"]) == 2
    # you cannot delete stuff with empty dicts
    helpers.deep_update(base_value, {"newRootKey": {}})
    assert base_value["newRootKey"]["pla"] == "blub"


def test_load_jsons(caplog):
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.specter")
    import cryptoadvance.specter.helpers as helpers

    mydict = helpers.load_jsons("./tests/helpers_testdata")
    assert mydict["some_jsonfile"]["blub"] == "bla"
    assert mydict["some_other_jsonfile"]["bla"] == "blub"
    mydict = helpers.load_jsons("./tests/helpers_testdata", "id")
    assert "some_jsonfile" not in mydict
    # instead the value for the key "id" is now used as the top-level key
    assert mydict["ID123"]["blub"] == "bla"
    # This also assumes that the key is unique!!!!
    assert mydict["ID124"]["bla"] == "blub"
    # ToDo: check the uniqueness in the implementation to avoid issues
    # the filename is added as alias
    assert mydict["ID123"]["alias"] == "some_jsonfile"
    # We also get the fullpath of that file:
    assert mydict["ID123"]["fullpath"] == "./tests/helpers_testdata/some_jsonfile.json"
    # Quite handy if you want to get rid of it which is as easy as:
    # os.remove(mydict["ID123"]['fullpath'])


def test_is_ip_private(caplog):
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.specter")
    import cryptoadvance.specter.helpers as helpers

    # https://en.wikipedia.org/wiki/Private_network
    # For each private network address range, we are testing the lower, arbitrary middle and upper part of the range
    priv_lo_addresses = ["127.0.0.0", "127.1.32.15", "127.255.255.255"]
    priv_24_addresses = ["10.0.0.0", "10.1.32.125", "10.255.255.255"]
    priv_20_addresses = ["172.16.0.0", "172.24.32.125", "172.31.255.255"]
    priv_16_addresses = ["192.168.0.0", "192.168.16.125", "192.168.255.255"]

    # Randomly generated public ip addresses
    public_addresses = ["58.28.76.138", "128.5.218.201", "170.45.214.32"]

    assert helpers.is_ip_private("localhost")
    for ip in priv_lo_addresses:
        assert helpers.is_ip_private(ip)
    for ip in priv_24_addresses:
        assert helpers.is_ip_private(ip)
    for ip in priv_20_addresses:
        assert helpers.is_ip_private(ip)
    for ip in priv_16_addresses:
        assert helpers.is_ip_private(ip)
    for ip in public_addresses:
        assert not helpers.is_ip_private(ip)
