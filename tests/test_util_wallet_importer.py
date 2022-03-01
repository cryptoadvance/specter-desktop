import logging
import pytest
import time

from cryptoadvance.specter.key import Key
from cryptoadvance.specter.managers.device_manager import DeviceManager
from cryptoadvance.specter.user import User
from cryptoadvance.specter.util.descriptor import Descriptor
from cryptoadvance.specter.util.wallet_importer import WalletImporter
from mock import MagicMock, call, patch


@patch("cryptoadvance.specter.util.wallet_importer.flash", print)
@patch("cryptoadvance.specter.util.wallet_importer._", lambda x: x)
def test_WalletImporter_unit():
    specter_mock = MagicMock()
    specter_mock.chain = "regtest"

    # coldcard, trezor import
    wallet_json = """
        {"label": "MyTestMultisig", 
         "blockheight": 0, 
         "descriptor": 
         "wsh(sortedmulti(1,[fb7c1f11/48h/1h/0h/2h]tpubDExnGppazLhZPNadP8Q5Vgee2QcvbyAf9GvGaEY7ALVJREaG2vdTqv1MHRoDtPaYP3y1DGVx7wrKKhsLhs26GY263uE6Wi3qNbi71AHZ6p7/0/*,[1ef4e492/48h/1h/0h/2h]tpubDFiVCZzdarbyk8kE65tjRhHCambEo8iTx4xkXL8b33BKZj66HWsDnUb3rg4GZz6Mwm6vTNyzRCjYtiScCQJ77ENedb2deDDtcoNQXiUouJQ/0/*))#s0jemlck", 
         "devices": 
            [
                {"type": "coldcard", 
                 "label": "MyColdcard"}, 
                {"type": "trezor", 
                 "label": "MyTestTrezor"}
            ]
        } 
    """

    wallet_importer = WalletImporter(wallet_json, specter_mock)
    assert wallet_importer.wallet_name == "MyTestMultisig"

    assert (
        str(wallet_importer.descriptor)
        == "wsh(sortedmulti(1,[fb7c1f11/48h/1h/0h/2h]tpubDExnGppazLhZPNadP8Q5Vgee2QcvbyAf9GvGaEY7ALVJREaG2vdTqv1MHRoDtPaYP3y1DGVx7wrKKhsLhs26GY263uE6Wi3qNbi71AHZ6p7/0/*,[1ef4e492/48h/1h/0h/2h]tpubDFiVCZzdarbyk8kE65tjRhHCambEo8iTx4xkXL8b33BKZj66HWsDnUb3rg4GZz6Mwm6vTNyzRCjYtiScCQJ77ENedb2deDDtcoNQXiUouJQ/0/*))"
    )
    assert wallet_importer.cosigners_types == [
        {"label": "MyColdcard", "type": "coldcard"},
        {"label": "MyTestTrezor", "type": "trezor"},
    ]
    # The descriptor (very briefly)
    assert [
        key.origin.fingerprint.hex() for key in wallet_importer.descriptor.keys
    ] == ["fb7c1f11", "1ef4e492"]
    assert len(wallet_importer.keys) == 0
    assert len(wallet_importer.cosigners) == 0
    assert len(wallet_importer.unknown_cosigners) == 2
    # it's a tuple:
    assert isinstance(wallet_importer.unknown_cosigners[0][0], Key)
    assert wallet_importer.unknown_cosigners[0][1] == "MyColdcard"

    assert isinstance(wallet_importer.unknown_cosigners[1][0], Key)
    assert wallet_importer.unknown_cosigners[1][1] == "MyTestTrezor"

    assert len(wallet_importer.unknown_cosigners_types) == 2
    assert wallet_importer.unknown_cosigners_types == ["coldcard", "trezor"]
    request_form = {
        "unknown_cosigner_0_name": "MyColdcard",
        "unknown_cosigner_1_name": "MyTestTrezor",
    }
    wallet_importer.create_nonexisting_signers(MagicMock(), request_form)
    # The keys has been created
    assert len(wallet_importer.keys) == 2
    # now we have 2 cosigners
    assert len(wallet_importer.cosigners) == 2
    # But still 2 unknown cosigners
    assert len(wallet_importer.unknown_cosigners) == 2
    wm_mock = MagicMock()
    wallet_mock = MagicMock()
    wm_mock.create_wallet.return_value = wallet_mock
    wallet_importer.create_wallet(wm_mock)
    assert wm_mock.create_wallet.called
    wm_mock.create_wallet.assert_called_once
    assert wallet_mock.keypoolrefill.called

    # electrum single-sig and multisig import (Not BIP39, but electrum seeds), Focus is here only on the correct descriptor
    singlesig_json = """
        {
            "keystore": {
                "derivation": "m/0'",
                "pw_hash_version": 1,
                "root_fingerprint": "1f0a071c",
                "seed": "castle flight vessel game mushroom stumble noise list scheme episode sheriff squeeze",
                "seed_type": "segwit",
                "type": "bip32",
                "xprv": "vprv9FTrHquAzV9x9rNoJNA65YTwqyAjJHzs9kvPSfQqoPYKDPiAugDe6sCqrbkut2k3JEeXbmRN9aWMsdJZD1nGhdsCZbbmHrszvifAxo7oVjA",
                "xpub": "vpub5UTChMS4priFNLTGQPh6SgQgQ11DhkiiWyqzF3pTMj5J6C3KTDXtefXKhrrRPuF2TsEuoU9w6NvydP9axJQKuof6gzdvt1eDJSRZzy3WDzV"
            },
            "use_encryption": false,
            "wallet_type": "standard"
        }
    """

    singlesig_importer = WalletImporter(singlesig_json, specter_mock)
    assert (
        str(singlesig_importer.descriptor)
        == "wpkh([1f0a071c/0h]vpub5UTChMS4priFNLTGQPh6SgQgQ11DhkiiWyqzF3pTMj5J6C3KTDXtefXKhrrRPuF2TsEuoU9w6NvydP9axJQKuof6gzdvt1eDJSRZzy3WDzV/0/*)"
    )

    multisig_json = """
        {
            "use_encryption": false,
            "wallet_type": "1of2",
            "x1/": {
                "derivation": "m/1'",
                "pw_hash_version": 1,
                "root_fingerprint": "9f09087f",
                "seed": "bicycle master jacket bring tornado faint bachelor violin delay equip february frog",
                "seed_type": "segwit",
                "type": "bip32",
                "xprv": "Vprv19bpWVjGnupHR8JU9p9RU4gWrUAYProMHQ5MxPw14b1Rtk8mB6V3vQSywnxwJ9GoJwt3Jgf4Qe2DcU9JzYoFj1FNZsuqY3kYt3Rt2JvG4wG",
                "xpub": "Vpub5gHreumWwHVxJbLG3Tp1sULdRVgUZBzFrhg9EuyJUropjEPXoVJe6u4r7y2EpwyVXHgehJ2PNn2R3kDxXLBGNnKmbicdibuoGmNjhCfyEZF"
            },
            "x2/": {
                "derivation": "m/1'",
                "pw_hash_version": 1,
                "root_fingerprint": "1f0a071c",
                "seed": "castle flight vessel game mushroom stumble noise list scheme episode sheriff squeeze",
                "seed_type": "segwit",
                "type": "bip32",
                "xprv": "Vprv18fFgB8GFSawxQYZFf4q8umBXkVGg799uBeuAp1wXSkxX9dgvpwZnjCFwaffHauq1LZHZQPpei13HuMoR7kjTJg8HKWcmqbPTTzbVqUKj5Y",
                "xpub": "Vpub5fMHpbAWPpGcqsaM9JjRYKRJ6n1CqSL4UVFgTL4EwiZMMdtTZDm9yDp87ko2WA1N9dWLuM48H9oiPDE4nGPfpxFNe7ZkcSqc2L2ncuEXu4Z"
            }
        }
    """

    multisig_importer = WalletImporter(multisig_json, specter_mock)
    assert (
        str(multisig_importer.descriptor)
        == "wsh(sortedmulti(1,[9f09087f/1h]Vpub5gHreumWwHVxJbLG3Tp1sULdRVgUZBzFrhg9EuyJUropjEPXoVJe6u4r7y2EpwyVXHgehJ2PNn2R3kDxXLBGNnKmbicdibuoGmNjhCfyEZF/0/*,[1f0a071c/1h]Vpub5fMHpbAWPpGcqsaM9JjRYKRJ6n1CqSL4UVFgTL4EwiZMMdtTZDm9yDp87ko2WA1N9dWLuM48H9oiPDE4nGPfpxFNe7ZkcSqc2L2ncuEXu4Z/0/*))"
    )


@pytest.mark.slow
def test_WalletImporter_integration(specter_regtest_configured, bitcoin_regtest):
    """
    WalletImporter can load a wallet from a backup json with unknown devices and
    initialize a watch-only wallet that can receive funds and update its balance.
    """
    specter = specter_regtest_configured
    someuser: User = specter.user_manager.add_user(
        User.from_json(
            {
                "id": "someuser",
                "username": "someuser",
                "password": "somepassword",
                "config": {},
                "is_admin": False,
            },
            specter,
        )
    )
    specter.user_manager.save()
    specter.check()

    # Create a Wallet
    wallet_json = '{"label": "another_simple_wallet", "blockheight": 0, "descriptor": "wpkh([1ef4e492/84h/1h/0h]tpubDC5EUwdy9WWpzqMWKNhVmXdMgMbi4ywxkdysRdNr1MdM4SCfVLbNtsFvzY6WKSuzsaVAitj6FmP6TugPuNT6yKZDLsHrSwMd816TnqX7kuc/0/*)#xp8lv5nr", "devices": [{"type": "trezor", "label": "trezor"}]} '
    wallet_importer = WalletImporter(
        wallet_json, specter, device_manager=someuser.device_manager
    )
    wallet_importer.create_nonexisting_signers(
        someuser.device_manager,
        {"unknown_cosigner_0_name": "trezor", "unknown_cosigner_0_type": "trezor"},
    )
    dm: DeviceManager = someuser.device_manager
    wallet = wallet_importer.create_wallet(someuser.wallet_manager)
    # fund it with some coins
    bitcoin_regtest.testcoin_faucet(
        address=wallet.getnewaddress(), confirm_payment=False
    )

    # There can be a delay in the node generating the faucet deposit tx so keep
    #   rechecking until it's done (or we timeout).
    for i in range(0, 15):
        wallet.update()
        if wallet.update_balance()["untrusted_pending"] != 0:
            break
        else:
            time.sleep(2)

    wallet = someuser.wallet_manager.get_by_alias("another_simple_wallet")
    assert wallet.update_balance()["untrusted_pending"] == 20
