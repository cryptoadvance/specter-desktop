import json
from ..helpers import decode_base58, hash160
from ..serializations import PSBT
from .key import Key


class Device:
    QR_CODE_TYPES = ['specter', 'other']
    SD_CARD_TYPES = ['coldcard', 'other']
    HWI_TYPES = ['keepkey', 'ledger', 'trezor', 'specter', 'coldcard']

    def __init__(self, name, alias, device_type, keys, fullpath, manager):
        self.name = name
        self.alias = alias
        self.device_type = device_type
        self.keys = keys
        self.fullpath = fullpath
        self.manager = manager

    @classmethod
    def from_json(cls, device_dict, manager, default_alias='', default_fullpath=''):
        name = device_dict['name'] if 'name' in device_dict else ''
        alias = device_dict['alias'] if 'alias' in device_dict else default_alias
        device_type = device_dict['type'] if 'type' in device_dict else ''
        keys = [Key.from_json(key_dict) for key_dict in device_dict['keys']]
        fullpath = device_dict['fullpath'] if 'fullpath' in device_dict else default_fullpath
        return cls(name, alias, device_type, keys, fullpath, manager)

    @property
    def json(self):
        return {
            "name": self.name,
            "alias": self.alias,
            "type": self.device_type,
            "keys": [key.json for key in self.keys],
            "fullpath": self.fullpath,
        }

    def _update_keys(self):
        with open(self.fullpath, "r") as f:
            content = json.loads(f.read())
        content['keys'] = [key.json for key in self.keys]
        with open(self.fullpath, "w") as f:
            f.write(json.dumps(content,indent=4))
        self.manager.update()

    def remove_key(self, key):
        self.keys = [k for k in self.keys if k != key]
        self._update_keys()

    def add_keys(self, keys):
        for key in keys:
            if key not in self.keys:
                self.keys.append(key)
        self._update_keys()

    def wallets(self, wallet_manager):
        wallets = []
        for wallet in wallet_manager.wallets.values():
            if self in wallet.devices:
                wallets.append(wallet)
        return wallets

    @staticmethod
    def create_sdcard_psbt(base64_psbt, keys):
        sdcard_psbt = PSBT()
        sdcard_psbt.deserialize(base64_psbt)
        if len(keys) > 1:
            for k in keys:
                key = b'\x01' + decode_base58(k.xpub)
                if k.fingerprint != '':
                    fingerprint = bytes.fromhex(k.fingerprint)
                else:
                    fingerprint = _get_xpub_fingerprint(k.xpub)
                if k.derivation != '':
                    der = _der_to_bytes(k.derivation)
                else:
                    der = b''
                value = fingerprint + der
                sdcard_psbt.unknown[key] = value
        return sdcard_psbt.serialize()

    @staticmethod
    def create_qrcode_psbt(base64_psbt, fingerprint):
        qr_psbt = PSBT()
        qr_psbt.deserialize(base64_psbt)
        for inp in qr_psbt.inputs + qr_psbt.outputs:
            inp.witness_script = b""
            inp.redeem_script = b""
            if len(inp.hd_keypaths) > 0:
                k = list(inp.hd_keypaths.keys())[0]
                # proprietary field - wallet derivation path
                # only contains two last derivation indexes - change and index
                inp.unknown[b"\xfc\xca\x01" + fingerprint] = b"".join([i.to_bytes(4, "little") for i in inp.hd_keypaths[k][-2:]])
                inp.hd_keypaths = {}
        return qr_psbt.serialize()

    def __eq__(self, other):
        return self.alias == other.alias

    def __hash__(self):
        return hash(self.alias)


def _get_xpub_fingerprint(xpub):
    b = decode_base58(xpub)
    return hash160(b[-33:])[:4]

def _der_to_bytes(derivation):
    items = derivation.split("/")
    if len(items) == 0:
        return b''
    if items[0] == 'm':
        items = items[1:]
    if items[-1] == '':
        items = items[:-1]
    res = b''
    for item in items:
        index = 0
        if item[-1] == 'h' or item[-1] == "'":
            index += 0x80000000
            item = item[:-1]
        index += int(item)
        res += index.to_bytes(4,'big')
    return res
