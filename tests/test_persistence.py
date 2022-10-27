import os
from unittest.mock import MagicMock, Mock
from cryptoadvance.specter.persistence import (
    write_devices,
    write_device,
    write_wallet,
    PersistentObject,
)
from cryptoadvance.specter.key import Key
import json

# count files
def count_files_in(path, extension=".json"):
    assert not path is None
    return len(
        [
            f
            for f in os.listdir(path)
            if f.endswith(extension) and os.path.isfile(os.path.join(path, f))
        ]
    )


def test_write_devices(app, monkeypatch, caplog):

    devices_json = json.loads(
        """[
        {"name": "fsedf", "alias": "fsedf", "type": "trezor", "keys": [{"original": "zpub6rGoJTXEhKw7hUFkjMqNctTzojkzRPa3VFuUWAirqpuj13mRweRmnYpGD1aQVFpxNfp17zVU9r7F6oR3c4zL3DjXHdewVvA7kjugHSqz5au", "fingerprint": "1ef4e492", "derivation": "m/84h/0h/0h", "type": "wpkh", "xpub": "xpub6CcGh8BQPxr9zssX4eG8CiGzToU6Y9b3f2s2wNw65p9xtr8ySL6eYRVzAbfEVSX7ZPaPd3JMEXQ9LEBvAgAJSkNKYxG6L6X9DHnPWNQud4H"}, {"original": "Ypub6jtWQ1r2D7EwqNoxERU28MWZH4WdL3pWdN8guFJRBTmGwstJGzMXJe1VaNZEuAAVsZwpKPhs5GzNPEZR77mmX1mjwzEiouxmQYsrxFBNVNN", "fingerprint": "1ef4e492", "derivation": "m/48h/0h/0h/1h", "type": "sh-wsh", "xpub": "xpub6EA9y7SfVU96ZWTTTQDR6C5FPJKvB59RPyxoCb8zRgYzGbWAFvogbTVRkTeBLpHgETm2hL7BjQFKNnL66CCoaHyUFBRtpbgHF6YLyi7fr6m"}, {"original": "Zpub74imhgWwMnnRkSPkiNavCQtSBu1fGo8RP96h9eT2GHCgN5eFU9mZVPhGphvGnG26A1cwJxtkmbHR6nLeTw4okpCDjZCEj2HRLJoVHAEsch9", "fingerprint": "1ef4e492", "derivation": "m/48h/0h/0h/2h", "type": "wsh", "xpub": "xpub6EA9y7SfVU96dGr96zYgxAMd8AgWBCTqEeQafbPi8VcWdhStCS4AA9X4yb3dE1VM7GKLwRhWy4BpD3VkjK5q1riMAQgz9oBSu8QKv5S7KzD"}, {"original": "ypub6XFn7hfb676MLm6ZsAviuQKXeRDNgT9Bs32KpRDPnkKgKDjKcrhYCXJ88aBfy8co2k9eujugJX5nwq7RPG4sj6yncDEPWN9dQGmFWPy4kFB", "fingerprint": "1ef4e492", "derivation": "m/49h/0h/0h", "type": "sh-wpkh", "xpub": "xpub6CRWp2zfwRYsVTuT2p96hKE2UT4vjq9gwvW732KWQjwoG7v6NCXyaTdz7NE5yDxsd72rAGK7qrjF4YVrfZervsJBjsXxvTL98Yhc7poBk7K"}, {"original": "Upub5Tk9tZtdzVaTGWtygRTKDDmaN5vfB59pn2L5MQyH6BkVpg2Y5J95rtpQndjmXNs3LNFiy8zxpHCTtvxxeePjgipF7moTHQZhe3E5uPzDXh8", "fingerprint": "1ef4e492", "derivation": "m/48h/1h/0h/1h", "type": "sh-wsh", "xpub": "tpubDFiVCZzdarbyfdVoh2LJDL3eVKRPmxwnkiqN8tSYCLod75a2966anQbjHajqVAZ97j54xZJPr9hf7ogVuNL4pPCfwvXdKGDQ9SjZF7vXQu1"}], "fullpath": "/home/kim/.specter/devices/fsedf.json"},
        {"name": "myNiceDevice", "alias": "mynicedevice", "type": "specter", "keys": [{"original": "vpub5Z8h5qLg5f2vEKbwDtoyqsiFwbFUiu7kD47LceVRS6Um4m94rfuxjRxghaYYywPh3dqhyd6rZ4TQ9bBCzfWRZgwpdydgbmmGLkx9s6MGKaU", "fingerprint": "1831e62e", "derivation": "m/84h/1h/0h", "type": "wpkh", "xpub": "tpubDDArDQWC6J5LCiB2LoNKTyEdcee2bXboauk5XzLLY1zQvFSESD6B7zwnz2YWWFemepcE69or1UzYcLtwpvBh3bmKSFmqT84UUAfrQCcaTMY"}], "fullpath": "/home/kim/.specter/devices/mynicedevice.json"},
        {"name": "YetAnotherTrezor", "alias": "yetanothertrezor", "type": "trezor", "keys": [{"original": "Ypub6jtWQ1r2D7EwqNoxERU28MWZH4WdL3pWdN8guFJRBTmGwstJGzMXJe1VaNZEuAAVsZwpKPhs5GzNPEZR77mmX1mjwzEiouxmQYsrxFBNVNN", "fingerprint": "1ef4e492", "derivation": "m/48h/0h/0h/1h", "type": "sh-wsh", "xpub": "xpub6EA9y7SfVU96ZWTTTQDR6C5FPJKvB59RPyxoCb8zRgYzGbWAFvogbTVRkTeBLpHgETm2hL7BjQFKNnL66CCoaHyUFBRtpbgHF6YLyi7fr6m"}, {"original": "Zpub74imhgWwMnnRkSPkiNavCQtSBu1fGo8RP96h9eT2GHCgN5eFU9mZVPhGphvGnG26A1cwJxtkmbHR6nLeTw4okpCDjZCEj2HRLJoVHAEsch9", "fingerprint": "1ef4e492", "derivation": "m/48h/0h/0h/2h", "type": "wsh", "xpub": "xpub6EA9y7SfVU96dGr96zYgxAMd8AgWBCTqEeQafbPi8VcWdhStCS4AA9X4yb3dE1VM7GKLwRhWy4BpD3VkjK5q1riMAQgz9oBSu8QKv5S7KzD"}, {"original": "vpub5Y35MNUT8sUR2SnRCU9A9S6z1JDACMTuNnM8WHXvuS7hCwuVuoRAWJGpi66Yo8evGPiecN26oLqx19xf57mqVQjiYb9hbb4QzbNmFfsS9ko", "fingerprint": "1ef4e492", "derivation": "m/84h/1h/0h", "type": "wpkh", "xpub": "tpubDC5EUwdy9WWpzqMWKNhVmXdMgMbi4ywxkdysRdNr1MdM4SCfVLbNtsFvzY6WKSuzsaVAitj6FmP6TugPuNT6yKZDLsHrSwMd816TnqX7kuc"}, {"original": "Upub5Tk9tZtdzVaTGWtygRTKDDmaN5vfB59pn2L5MQyH6BkVpg2Y5J95rtpQndjmXNs3LNFiy8zxpHCTtvxxeePjgipF7moTHQZhe3E5uPzDXh8", "fingerprint": "1ef4e492", "derivation": "m/48h/1h/0h/1h", "type": "sh-wsh", "xpub": "tpubDFiVCZzdarbyfdVoh2LJDL3eVKRPmxwnkiqN8tSYCLod75a2966anQbjHajqVAZ97j54xZJPr9hf7ogVuNL4pPCfwvXdKGDQ9SjZF7vXQu1"}, {"original": "Vpub5naRCEZZ9B7wCKLWuqoNdg6ddWEx8ruztUygXFZDJtW5LRMqUP5HV2TsNw1nc74Ba3QPDSH7qzauZ8LdfNmnmofpfmztCGPgP7vaaYSmpgN", "fingerprint": "1ef4e492", "derivation": "m/48h/1h/0h/2h", "type": "wsh", "xpub": "tpubDFiVCZzdarbyk8kE65tjRhHCambEo8iTx4xkXL8b33BKZj66HWsDnUb3rg4GZz6Mwm6vTNyzRCjYtiScCQJ77ENedb2deDDtcoNQXiUouJQ"}], "fullpath": "/home/kim/.specter/devices/yetanothertrezor.json"}
        ]
        """
    )

    assert count_files_in(app.specter.device_manager.data_folder) == 2
    write_devices(devices_json)
    assert count_files_in(app.specter.device_manager.data_folder) == 5
    assert not "callback failed" in caplog.text
    os.remove(os.path.join(app.specter.device_manager.data_folder, "fsedf.json"))
    monkeypatch.setenv("SPECTER_PERSISTENCE_CALLBACK", "ThisWillFail")
    write_devices(devices_json)
    assert count_files_in(app.specter.device_manager.data_folder) == 5
    assert "callback failed" in caplog.text


def test_write_wallet(app, monkeypatch, caplog):
    assert not app.specter.wallet_manager.working_folder is None
    wallet_json = json.loads(
        """
        {"name": "MyOtherWallet", "alias": "myotherwallet", "description": "Single (Segwit)", "address_type": "bech32", "address": "bcrt1qavs8svrqcgnrzktvsn27z3w7acq0dljgnf8k89", "address_index": 0, "change_address": "bcrt1qx70x540rcy26usrdxpv27l5qfhx7rmv9sjdx6c", "change_index": 0, "keypool": 20, "change_keypool": 20, "recv_descriptor": "wpkh([1831e62e/84h/1h/0h]tpubDDArDQWC6J5LCiB2LoNKTyEdcee2bXboauk5XzLLY1zQvFSESD6B7zwnz2YWWFemepcE69or1UzYcLtwpvBh3bmKSFmqT84UUAfrQCcaTMY/0/*)#zpjep3zd", "change_descriptor": "wpkh([1831e62e/84h/1h/0h]tpubDDArDQWC6J5LCiB2LoNKTyEdcee2bXboauk5XzLLY1zQvFSESD6B7zwnz2YWWFemepcE69or1UzYcLtwpvBh3bmKSFmqT84UUAfrQCcaTMY/1/*)#n4hcuyj4", "keys": [{"original": "vpub5Z8h5qLg5f2vEKbwDtoyqsiFwbFUiu7kD47LceVRS6Um4m94rfuxjRxghaYYywPh3dqhyd6rZ4TQ9bBCzfWRZgwpdydgbmmGLkx9s6MGKaU", "fingerprint": "1831e62e", "derivation": "m/84h/1h/0h", "type": "wpkh", "xpub": "tpubDDArDQWC6J5LCiB2LoNKTyEdcee2bXboauk5XzLLY1zQvFSESD6B7zwnz2YWWFemepcE69or1UzYcLtwpvBh3bmKSFmqT84UUAfrQCcaTMY"}], "devices": ["mynicedevice"], "sigs_required": 1, "pending_psbts": {}, "fullpath": "/home/kim/.specter/wallets/regtest/myotherwallet.json", "last_block": "24ca00b211427afb921dec51d4d7c7b110f7aef6165298149a5fcf009c5abea0", "blockheight": 214}
        """
    )
    assert count_files_in(app.specter.wallet_manager.working_folder) == 0
    write_wallet(wallet_json)
    assert count_files_in(app.specter.wallet_manager.working_folder) == 1
    assert not "callback failed" in caplog.text
    os.remove(
        os.path.join(app.specter.wallet_manager.working_folder, "myotherwallet.json")
    )
    monkeypatch.setenv("SPECTER_PERSISTENCE_CALLBACK", "ThisWillFail")
    write_wallet(wallet_json)
    assert count_files_in(app.specter.wallet_manager.working_folder) == 1
    assert "callback failed" in caplog.text


def test_write_device(app, a_key, a_tpub_only_key):
    app.specter.device_manager.add_device(
        "some_name2", "the_type", [a_key, a_tpub_only_key]
    )
    write_device(
        app.specter.device_manager.get_by_alias("some_name2"),
        "/tmp/delete_me_test_file.json",
    )
    os.remove("/tmp/delete_me_test_file.json")


def test_PersistentObject():
    some_node = PersistentObject.from_json(
        {"python_class": "cryptoadvance.specter.node.Node"}, MagicMock()
    )
    assert some_node.__class__.__name__ == "Node"
