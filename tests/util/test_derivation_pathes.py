from cryptoadvance.specter.util.derivation_pathes import is_testnet


def test_is_testnet():
    assert is_testnet("cd273ae3/48'/1'/0'/1'")
    assert is_testnet("m/48'/1h/0'/1'")
    assert is_testnet("cd273ae3/48/1/0'/1'")
    assert is_testnet("m/48'/1/0'/1'")

    assert not is_testnet("cd273ae3/48'/0'/0'/1'")
    assert not is_testnet("m/48'/0'/0h/1'")
    assert not is_testnet("cd273ae3/48/0/0'/1'")
    assert not is_testnet("m/48'/0/0'/1'")

    assert is_testnet("cd273ae3/48h/1h/0h/1h")
    assert is_testnet("m/48h/1h/0h/1h")
    assert is_testnet("cd273ae3/48/1/0h/1h")
    assert is_testnet("m/48h/1/0'/1h")

    assert not is_testnet("cd273ae3/48h/0h/0h/1h")
    assert not is_testnet("m/48h/0h/0h/1h")
    assert not is_testnet("cd273ae3/48/0/0h/1h")
    assert not is_testnet("m/48h/0/0h/1h")
