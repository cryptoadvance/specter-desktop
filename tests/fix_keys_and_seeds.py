from binascii import hexlify
import json
import pytest
from cryptoadvance.specter.key import Key

from embit.bip39 import mnemonic_to_seed
from embit.bip32 import HDKey, NETWORKS
from embit import script


@pytest.fixture
def mnemonic_ghost_machine():
    return 11 * "ghost " + "machine"


@pytest.fixture
def mnemonic_keen_join():
    return 11 * "keen " + "join"


@pytest.fixture
def mnemonic_hold_accident():
    return 11 * "hold " + "accident"


# The following is a formal creation of all major bitcoin artifacts from the
# hold accident mnemonic


@pytest.fixture
def seed_hold_accident(mnemonic_hold_accident):
    seed = mnemonic_to_seed(mnemonic_hold_accident)
    print(f"Hold Accident seed: {hexlify(seed)}")
    return mnemonic_to_seed(mnemonic_hold_accident)


@pytest.fixture
def rootkey_hold_accident(seed_hold_accident):
    rootkey = HDKey.from_seed(seed_hold_accident)
    print(f"Hold Accident rootkey: {rootkey.to_base58()}")
    # xprv9s21ZrQH143K45uYUg7zhHku3bik5a2nw8XcanYCUGHn7RE1Bhkr53RWcjAQVFDTmruDceNDAGbc7yYsZCGveKMDrPr18hMsMcvYTGJ4Mae
    print(f"Hold Accident rootkey fp: {hexlify(rootkey.my_fingerprint)}")
    return rootkey


@pytest.fixture
def acc0xprv_hold_accident(rootkey_hold_accident: HDKey):
    xprv = rootkey_hold_accident.derive("m/84h/1h/0h")
    print(f"Hold Accident acc0xprv: {xprv.to_base58(version=NETWORKS['test']['xprv'])}")
    # tprv8g6WHqYgjvGrEU6eEdJxXzNUqN8DvLFb3iv3yUVomNRcNqT5JSKpTVNBzBD3qTDmmhRHPLcjE5fxFcGmU3FqU5u9zHm9W6sGX2isPMZAKq2

    return xprv


@pytest.fixture
def acc0xpub_hold_accident(acc0xprv_hold_accident: HDKey):
    xpub = acc0xprv_hold_accident.to_public()
    print(f"Hold Accident acc0xpub: {xpub.to_base58(version=NETWORKS['test']['xpub'])}")
    # vpub5YkPJgRQsev79YZM1NRDKJWDjLFcD2xSFAt6LehC5iiMMqQgMHyCFQzwsu16Rx9rBpXZVXPjWAxybuCpsayaw8qCDZtjwH9vifJ7WiQkHwu
    return xpub


@pytest.fixture
def acc0key0pubkey_hold_accident(acc0xpub_hold_accident: HDKey):
    pubkey = acc0xpub_hold_accident.derive("m/0/0")
    print("------------")
    print(pubkey.key)
    # 03584dc8282f626ce5570633018be0760baae68f1ecd6e801192c466ada55f5f31
    print(hexlify(pubkey.sec()))
    # b'03584dc8282f626ce5570633018be0760baae68f1ecd6e801192c466ada55f5f31'
    return pubkey


@pytest.fixture
def acc0key0addr_hold_accident(acc0key0pubkey_hold_accident):
    sc = script.p2wpkh(acc0key0pubkey_hold_accident)
    address = sc.address(NETWORKS["test"])
    print(address)  # m/84'/1'/0'/0/0
    # tb1qnwc84tkupy5v0tzgt27zkd3uxex3nmyr6vfhdd
    return address


@pytest.fixture
def key_hold_accident(acc0key0pubkey_hold_accident):
    sc = script.p2wpkh(acc0key0pubkey_hold_accident)
    address = sc.address(NETWORKS["test"])
    print(address)  # m/84'/1'/0'/0/0
    # tb1qnwc84tkupy5v0tzgt27zkd3uxex3nmyr6vfhdd
    return address


@pytest.fixture
def acc0key_hold_accident(acc0xpub_hold_accident, rootkey_hold_accident: HDKey):

    key: Key = Key(
        acc0xpub_hold_accident.to_base58(
            version=NETWORKS["test"]["xpub"]
        ),  # original (ToDo: better original)
        hexlify(rootkey_hold_accident.my_fingerprint).decode("utf-8"),  # fingerprint
        "m/84h/1h/0h",  # derivation
        "wpkh",  # key_type
        "Muuh",  # purpose
        acc0xpub_hold_accident.to_base58(version=NETWORKS["test"]["xpub"]),  # xpub
    )
    mydict = key.json
    print(json.dumps(mydict))

    return key


# random other keys


@pytest.fixture
def a_key():
    a_key = Key(
        "Vpub5n9kKePTPPGtw3RddeJWJe29epEyBBcoHbbPi5HhpoG2kTVsSCUzsad33RJUt3LktEUUPPofcZczuudnwR7ZgkAkT6N2K2Z7wdyjYrVAkXM",
        "08686ac6",
        "m/48h/1h/0h/2h",
        "wsh",
        "",
        "tpubDFHpKypXq4kwUrqLotPs6fCic5bFqTRGMBaTi9s5YwwGymE8FLGwB2kDXALxqvNwFxB1dLWYBmmeFVjmUSdt2AsaQuPmkyPLBKRZW8BGCiL",
    )
    return a_key


@pytest.fixture
def a_tpub_only_key():
    a_tpub_only_key = Key.from_json(
        {
            "original": "tpubDDZ5jjGT5RvrAyjoLZfdCfv1PAPmicnhNctwZGKiCMF1Zy5hCGMqppxwYZzWgvPqk7LucMMHo7rkB6Dyj5ZLd2W62FAEP3U6pV4jD5gb9ma"
        }
    )
    return a_tpub_only_key
