import json


class Device(dict):
    QR_CODE_TYPES = ['specter', 'other']
    SD_CARD_TYPES = ['coldcard', 'other']
    HWI_TYPES = ['keepkey', 'ledger', 'trezor', 'specter', 'coldcard']

    def __init__(self, d, manager):
        self.manager = manager
        self.update(d)

    def _update_keys(self, keys):
        self["keys"] = keys
        with open(self["fullpath"], "r") as f:
            content = json.loads(f.read())
        content["keys"] = self["keys"]
        with open(self["fullpath"], "w") as f:
            f.write(json.dumps(content,indent=4))
        self.manager.update()

    def remove_key(self, key):
        keys = [k for k in self["keys"] if k["original"]!=key]
        self._update_keys(keys)

    def add_keys(self, normalized):
        key_arr = [k["original"] for k in self["keys"]]
        keys = self["keys"]
        for k in normalized:
            if k["original"] not in key_arr:
                keys.append(k)
                key_arr.append(k["original"])
        self._update_keys(keys)
