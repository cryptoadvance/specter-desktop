import base64
import copy
import json
import os
import random
import hashlib
from collections import OrderedDict

from . import helpers
from .descriptor import AddChecksum
from .helpers import deep_update, load_jsons
from .rpc import RPC_PORTS, BitcoinCLI, autodetect_cli
from .serializations import PSBT

cache = {}

# a gap of 20 addresses is what many wallets do
WALLET_CHUNK = 20
# we don't need to scan earlier than that 
# as we don't support legacy wallets
FIRST_SEGWIT_BLOCK = 481824

purposes = OrderedDict({
    None: "General",
    "wpkh": "Single (Segwit)",
    "sh-wpkh": "Single (Nested)",
    "pkh": "Single (Legacy)",
    "wsh": "Multisig (Segwit)",
    "sh-wsh": "Multisig (Nested)",
    "sh": "Multisig (Legacy)",
})

addrtypes = {
    "pkh": "legacy",
    "sh-wpkh": "p2sh-segwit",
    "wpkh": "bech32",
    "sh": "legacy",
    "sh-wsh": "p2sh-segwit",
    "wsh": "bech32"
}

def alias(name):
    name = name.replace(" ", "_")
    return "".join(x for x in name if x.isalnum() or x=="_").lower()

def get_cli(conf):
    if "user" not in conf or conf["user"]=="":
        conf["autodetect"] = True
    if conf["autodetect"]:
        if "port" in conf:
            cli_arr = autodetect_cli(port=conf["port"])
        else:
            cli_arr = autodetect_cli()
        if len(cli_arr) > 0:
            cli = cli_arr[0]
        else:
            return None
    else:
        cli = BitcoinCLI(conf["user"], conf["password"], 
                          host=conf["host"], port=conf["port"], protocol=conf["protocol"])
    return cli

class SpecterError(Exception):
    ''' A SpecterError contains meaningfull messages which can be passed directly to the user '''
    pass

class Specter:
    ''' A central Object mostly holding app-settings '''
    CONFIG_FILE_NAME = "config.json"
    def __init__(self, data_folder="./data", config={}):
        if data_folder.startswith("~"):
            data_folder = os.path.expanduser(data_folder)
        self.data_folder = data_folder
        self.cli = None
        self.devices = None
        self.wallets = None

        self.file_config = None  # what comes from config file
        self.arg_config = config # what comes from arguments

        # default config
        self.config = {
            "rpc": {
                "autodetect": True,
                "user": "",
                "password": "",
                "port": "",
                "host": "localhost",        # localhost
                "protocol": "http"          # https for the future
            },
            "auth": "none",
            "explorers": {
                "main": "https://blockstream.info/",
                "test": "https://blockstream.info/testnet/",
                "regtest": None,
                "signet": "https://explorer.bc-2.jp/"
            },
            # unique id that will be used in wallets path in Bitcoin Core
            # empty by default for backward-compatibility
            "uid": "",
        }

        # creating folders if they don't exist
        if not os.path.isdir(data_folder):
            os.makedirs(data_folder)

        self._info = { "chain": None }
        # health check: loads config and tests rpc
        self.check()

    def check(self):

        # if config.json file exists - load from it
        if os.path.isfile(os.path.join(self.data_folder, "config.json")):
            with open(os.path.join(self.data_folder, "config.json"), "r") as f:
                self.file_config = json.loads(f.read())
                deep_update(self.config, self.file_config)
        # otherwise - create one and assign unique id
        else:
            if self.config["uid"] == "":
                self.config["uid"] = random.randint(0,256**8).to_bytes(8,'big').hex()
            self._save()

        # init arguments
        deep_update(self.config, self.arg_config) # override loaded config
        
        self.cli = get_cli(self.config["rpc"])
        self._is_configured = (self.cli is not None)
        self._is_running = False
        if self._is_configured:
            try:
                self._info = self.cli.getmininginfo()
                self._is_running = True
            except:
                pass

        if not self._is_running:
            self._info["chain"] = None

        chain = self._info["chain"]
        if self.wallets is None or chain is None:
            wallets_path = "specter%s/" % self.config["uid"]
            self.wallets = WalletManager(
                                os.path.join(self.data_folder, "wallets"), 
                                self.cli, 
                                chain=chain,
                                path=wallets_path)
        else:
            self.wallets.update(os.path.join(self.data_folder, "wallets"), 
                                self.cli, 
                                chain=chain)

        if self.devices is None:
            self.devices = DeviceManager(os.path.join(self.data_folder, "devices"))
        else:
            self.devices.update(os.path.join(self.data_folder, "devices"))

        try:
            self.wallets.load_all()
        except Exception as e:
            print("can't load wallets...", e)

    def test_rpc(self, **kwargs):
        conf = copy.deepcopy(self.config["rpc"])
        conf.update(kwargs)
        cli = get_cli(conf)
        if cli is None:
            return {"out": "", "err": "autodetect failed", "code": -1}
        r = {}
        try:
            r["out"] = json.dumps(cli.getblockchaininfo(),indent=4)
            r["err"] = ""
            r["code"] = 0
        except:
            r["out"] = ""
            if cli.r is not None and "error" in cli.r:
                r["err"] = cli.r["error"]
                r["code"] = cli.r.status_code
            else:
                r["err"] = "Failed to connect"
                r["code"] = -1
        return r
    
    def _save(self):
        with open(os.path.join(self.data_folder, self.CONFIG_FILE_NAME), "w") as f:
            f.write(json.dumps(self.config, indent=4))

    def update_rpc(self, **kwargs):
        need_update = False
        for k in kwargs:
            if self.config["rpc"][k] != kwargs[k]:
                self.config["rpc"][k] = kwargs[k]
                need_update = True
        if need_update:
            self._save()
            self.check()
    
    def update_auth(self, auth):
        ''' simply persisting the current auth-choice '''
        if self.config["auth"] != auth:
            self.config["auth"] = auth
        self._save()
    
    def update_explorer(self, explorer):
        ''' update the block explorers urls '''

        # make sure the urls end with a "/"
        if not explorer.endswith("/"):
            explorer += "/"

        # update the urls in the app config
        if self.config["explorers"][self.chain] != explorer:
            self.config["explorers"][self.chain] = explorer

    @property
    def info(self):
        return self._info

    def combine(self, psbt_arr):
        final_psbt = self.cli.combinepsbt(psbt_arr)
        return final_psbt

    def finalize(self, psbt):
        final_psbt = self.cli.finalizepsbt(psbt)
        return final_psbt

    def broadcast(self, raw):
        res = self.cli.sendrawtransaction(raw)
        return res

    def estimatesmartfee(self, blocks):
        return self.cli.estimatesmartfee(blocks)

    @property
    def chain(self):
        return self._info["chain"]

    @property
    def explorer(self):
        if "explorers" in self.config and self.chain in self.config["explorers"]:
            return self.config["explorers"][self.chain]
        else:
            return None
    
    
class DeviceManager:
    ''' A DeviceManager mainly manages the persistence of a device-json-structures
        compliant to helper.load_jsons
    '''
    # of them via json-files in an empty data folder
    def __init__(self, data_folder):
        self.update(data_folder)

    def update(self, data_folder=None):
        if data_folder is not None:
            self.data_folder = data_folder
            if data_folder.startswith("~"):
                data_folder = os.path.expanduser(data_folder)
            # creating folders if they don't exist
            if not os.path.isdir(data_folder):
                os.mkdir(data_folder)
        self._devices = load_jsons(self.data_folder, key="name")
    
    def names(self):
        return list(self._devices.keys())

    def add(self, name, device_type, keys):
        dev = {
            "name": name,
            "type": device_type,
            "keys": []
        }
        fname = alias(name)
        i = 2
        while os.path.isfile(os.path.join(self.data_folder, "%s.json" % fname)):
            fname = alias("%s %d" % (name, i))
            i+=1
        # removing duplicates
        key_arr = [k["original"] for k in dev["keys"]]
        for k in keys:
            if k["original"] not in key_arr:
                dev["keys"].append(k)
                key_arr.append(k["original"])
        with open(os.path.join(self.data_folder, "%s.json" % fname), "w") as f:
            f.write(json.dumps(dev,indent=4))
        self.update() # reload files
        return self[name]

    def get_by_alias(self, fname):
        for dev in self:
            if dev["alias"] == fname:
                return dev

    def remove(self, device):
        os.remove(device["fullpath"])
        self.update()

    def __getitem__(self, name):
        return Device(self._devices[name], manager=self)

    def __iter__(self):
        self._n = 0
        return self

    def __next__(self):
        arr = list(self._devices.keys())
        if self._n < len(arr):
            v = self._devices[arr[self._n]]
            self._n += 1
            return Device(v, manager=self)
        else:
            raise StopIteration

    def __len__(self):
        return len(self._devices.keys())

class Device(dict):
    QR_CODE_TYPES = ['specter', 'other']
    SD_CARD_TYPES = ['coldcard', 'other']
    HWI_TYPES = ['keepkey', 'ledger', 'trezor', 'specter', 'coldcard']

    def __init__(self, d, manager):
        self.manager = manager
        self.update(d)
        self._dict = d

    def update_keys(self, keys):
        self["keys"] = keys
        with open(self["fullpath"], "r") as f:
            content = json.loads(f.read())
        content["keys"] = self["keys"]
        with open(self["fullpath"], "w") as f:
            f.write(json.dumps(content,indent=4))
        self.manager.update()

    def remove_key(self, key):
        keys = [k for k in self["keys"] if k["original"]!=key]
        self.update_keys(keys)

    def add_keys(self, normalized):
        key_arr = [k["original"] for k in self["keys"]]
        keys = self["keys"]
        for k in normalized:
            if k["original"] not in key_arr:
                keys.append(k)
                key_arr.append(k["original"])
        self.update_keys(keys)

class WalletManager:
    # chain is required to manage wallets when bitcoin-cli is not running
    def __init__(self, data_folder, cli, chain, path="specter/"):
        self.data_folder = data_folder
        self.chain = chain
        self.cli = cli
        self.cli_path = path
        self.update(data_folder, cli, chain)

    def update(self, data_folder=None, cli=None, chain=None):
        if chain is not None:
            self.chain = chain
        if data_folder is not None:
            self.data_folder = data_folder
            if data_folder.startswith("~"):
                data_folder = os.path.expanduser(data_folder)
            # creating folders if they don't exist
            if not os.path.isdir(data_folder):
                os.mkdir(data_folder)
        self.working_folder = None
        if self.chain is not None and self.data_folder is not None:
            self.working_folder = os.path.join(self.data_folder, self.chain)
        if self.working_folder is not None and not os.path.isdir(self.working_folder):
            os.mkdir(self.working_folder)
        if cli is not None:
            self.cli = cli
        if self.working_folder is not None:
            self._wallets = {}
            wallets = load_jsons(self.working_folder, key="name")
            existing_wallets = [w["name"] for w in self.cli.listwalletdir()["wallets"]]
            for k in wallets:
                if self.cli_path+wallets[k]["alias"] in existing_wallets:
                    self._wallets[k] = wallets[k]
        else:
            self._wallets = {}

    def load_all(self):
        loaded_wallets = self.cli.listwallets()
        loadable_wallets = [w["name"] for w in self.cli.listwalletdir()["wallets"]]
        not_loaded_wallets = [w for w in loadable_wallets if w not in loaded_wallets]
        # print("not loaded wallets:", not_loaded_wallets)
        for k in self._wallets:
            if self.cli_path+self._wallets[k]["alias"] in not_loaded_wallets:
                print("loading", self._wallets[k]["alias"])
                self.cli.loadwallet(self.cli_path+self._wallets[k]["alias"])

    def get_by_alias(self, fname):
        for dev in self:
            if dev["alias"] == fname:
                return dev

    def names(self):
        return list(self._wallets.keys())

    def _get_intial_wallet_dict(self, name):
        al = alias(name)
        i = 2
        while os.path.isfile(os.path.join(self.working_folder, "%s.json" % al)):
            al = alias("%s %d" % (name, i))
            i+=1
        dic = {
            "alias": al,
            "fullpath": os.path.join(self.working_folder, "%s.json" % al),
            "name": name,
            "address_index": 0,
            "keypool": 0,
            "address": None,
            "change_index": 0,
            "change_address": None,
            "change_keypool": 0,
        }
        return dic

    def create_simple(self, name, key_type, key, device):
        o = self._get_intial_wallet_dict(name)
        arr = key_type.split("-")
        desc = key["xpub"]
        if key["derivation"] is not None:
            desc = "[%s%s]%s" % (key["fingerprint"], key["derivation"][1:], key["xpub"])
        recv_desc = "%s/0/*" % desc
        change_desc = "%s/1/*" % desc
        for el in arr[::-1]:
            recv_desc = "%s(%s)" % (el, recv_desc)
            change_desc = "%s(%s)" % (el, change_desc)
        recv_desc = AddChecksum(recv_desc)
        change_desc = AddChecksum(change_desc)
        o.update({
            "type": "simple", 
            "description": purposes[key_type],
            "key": key,
            "recv_descriptor": recv_desc,
            "change_descriptor": change_desc,
            "device": device["name"],
            "device_type": device["type"],
            "address_type": addrtypes[key_type],
        })
        # add wallet to internal dict
        self._wallets[o["alias"]] = o
        # create a wallet in Bitcoin Core
        r = self.cli.createwallet(self.cli_path+o["alias"], True)
        # save wallet file to disk
        if self.working_folder is not None:
            with open(o["fullpath"], "w+") as f:
                f.write(json.dumps(o, indent=4))
        # update myself - loads wallet files
        self.update()
        # get Wallet class instance
        w = Wallet(o, self)
        return w

    def create_multi(self, name, sigs_required, key_type, keys, devices):
        o = self._get_intial_wallet_dict(name)
        # TODO: refactor, ugly
        arr = key_type.split("-")
        descs = [key["xpub"] for key in keys]
        for i, desc in enumerate(descs):
            key = keys[i]
            if key["derivation"] is not None:
                descs[i] = "[%s%s]%s" % (key["fingerprint"], key["derivation"][1:], key["xpub"])
        recv_descs = ["%s/0/*" % desc for desc in descs]
        change_descs = ["%s/1/*" % desc for desc in descs]
        recv_desc = "multi({},{})".format(sigs_required, ",".join(recv_descs))
        change_desc = "multi({},{})".format(sigs_required, ",".join(change_descs))
        for el in arr[::-1]:
            recv_desc = "%s(%s)" % (el, recv_desc)
            change_desc = "%s(%s)" % (el, change_desc)
        recv_desc = AddChecksum(recv_desc)
        change_desc = AddChecksum(change_desc)
        devices_list = []
        for device in devices:
            devices_list.append({
                "name": device["name"],
                "type": device["type"]
            })
        o.update({
            "type": "multisig",
            "description": "{} of {} {}".format(sigs_required, len(keys), purposes[key_type]),
            "sigs_required": sigs_required,
            "keys": keys,
            "recv_descriptor": recv_desc,
            "change_descriptor": change_desc,
            "devices": devices_list,
            "address_type": addrtypes[key_type]
        })
        # add wallet to internal dict
        self._wallets[o["alias"]] = o
        # create a wallet in Bitcoin Core
        r = self.cli.createwallet(self.cli_path+o["alias"], True)
        # save wallet file to disk
        if self.working_folder is not None:
            with open(o["fullpath"], "w+") as f:
                f.write(json.dumps(o, indent=4))
        # update myself - loads wallet files
        self.update()
        # get Wallet class instance
        w = Wallet(o, self)
        return w

    def __getitem__(self, name):
        return Wallet(self._wallets[name], manager=self)

    def __iter__(self):
        self._n = 0
        return self

    def __next__(self):
        arr = list(self._wallets.keys())
        if self._n < len(arr):
            v = self._wallets[arr[self._n]]
            self._n += 1
            return Wallet(v, manager=self)
        else:
            raise StopIteration

    def __len__(self):
        return len(self._wallets.keys())

class Wallet(dict):
    def __init__(self, d, manager=None):
        self.update(d)
        self.manager = manager
        self.cli_path = manager.cli_path
        self.cli = manager.cli.wallet(self.cli_path+self["alias"])
        self._dict = d
        # check if address is known and derive if not
        # address derivation will also refill the keypool if necessary
        if self._dict["address"] is None:
            self._dict["address"] = self.get_address(0)
            self.setlabel(self._dict["address"], "Address #0")
        if self._dict["change_address"] is None:
            self._dict["change_address"] = self.get_address(0, change=True)
        self.getdata()

    def _commit(self, update_manager=True):
        with open(self["fullpath"], "w") as f:
            f.write(json.dumps(self._dict, indent=4))
        self.update(self._dict)
        if update_manager:
            self.manager.update()

    def _uses_device_type(self, type_list):
        if not self.is_multisig:
            return self.get("device_type") in type_list
        else:
            for device in self.get("devices"):
                if device["type"] in type_list:
                    return True
        return False

    @property
    def uses_qrcode_device(self):
        return self._uses_device_type(Device.QR_CODE_TYPES)
    @property
    def uses_sdcard_device(self):
        return self._uses_device_type(Device.SD_CARD_TYPES)
    @property
    def uses_hwi_device(self):
        return self._uses_device_type(Device.HWI_TYPES)

    @property
    def is_multisig(self):
        return "sigs_required" in self

    def _check_change(self):
        addr = self["change_address"]
        if addr is not None:
            # check if address was used already
            v = self.cli.getreceivedbyaddress(addr, 0)
            # if not - just return
            if v == 0:
                return
            self._dict["change_index"] += 1
        else:
            if "change_index" not in self._dict:
                self._dict["change_index"] = 0
            index = self._dict["change_index"]
        self._dict["change_address"] = self.get_address(self._dict["change_index"], change=True)
        self._commit()

    def setup_cache(self):
        """Setup cache if don't exist yet for the wallet
        """
        if self["name"] in cache:
            if "cli_txs" not in cache[self["name"]]:
                cache[self["name"]]["cli_txs"] = {}
            if "raw_transactions" not in cache[self["name"]]:
                cache[self["name"]]["raw_transactions"] = {}
            if "transactions" not in cache[self["name"]]:
                cache[self["name"]]["transactions"] = []
            if "addresses" not in cache[self["name"]]:
                cache[self["name"]]["addresses"] = []
            if "tx_count" not in cache[self["name"]]:
                cache[self["name"]]["tx_count"] = None
            if "tx_changed" not in cache[self["name"]]:
                cache[self["name"]]["tx_changed"] = True
            if "labels" not in cache[self["name"]]:
                cache[self["name"]]["labels"] = []
            if "last_block" not in cache[self["name"]]:
                cache[self["name"]]["last_block"] = None
        else:
            cache[self["name"]] = {
                "cli_txs": {},
                "raw_transactions": {},
                "transactions": [],
                "addresses": [],
                "tx_count": None,
                "tx_changed": True,
                "labels": [],
                "last_block": None
            }

    def cache_cli_txs(self):
        """Cache Bitcoin Core `listtransactions` result
        """
        cache[self["name"]]["cli_txs"] = {tx["txid"]: tx for tx in self.cli_transactions}

    def cache_addresses(self):
        """Cache wallet addresses
        """
        cache[self["name"]]["active_addresses"] = list(dict.fromkeys(self.addresses))
        cache[self["name"]]["addresses"] = list(dict.fromkeys(self.addresses + self.change_addresses))

    def cache_raw_txs(self):
        """Cache `raw_transactions` (with full data on all the inputs and outputs of each tx)
        """
        # Get list of all tx ids
        txids = list(dict.fromkeys(cache[self["name"]]["cli_txs"].keys()))
        tx_count = len(txids)
        # If there are new transactions (if the transations count changed)
        if tx_count != cache[self["name"]]["tx_count"]:
            for txid in txids:
                # Cache each tx, if not already cached.
                # Data is immutable (unless reorg occurs and except of confirmations) and can be saved in a file for permanent caching
                if txid not in cache[self["name"]]["raw_transactions"]:
                    # Call Bitcoin Core to get the "raw" transaction - allows to read detailed inputs and outputs
                    raw_tx = self.cli.getrawtransaction(txid, 1)
                    # Some data (like fee and category, and when unconfirmed also time) available from the `listtransactions`
                    # command is not available in the `getrawtransacion` - so add it "manually" here.
                    if "fee" in cache[self["name"]]["cli_txs"][txid]:
                        raw_tx["fee"] = cache[self["name"]]["cli_txs"][txid]["fee"]
                    if "category" in cache[self["name"]]["cli_txs"][txid]:
                        raw_tx["category"] = cache[self["name"]]["cli_txs"][txid]["category"]
                    if "time" in cache[self["name"]]["cli_txs"][txid]:
                        raw_tx["time"] = cache[self["name"]]["cli_txs"][txid]["time"]

                    # Loop on the transaction's inputs
                    # If not a coinbase transaction:
                    # Get the the output data corresponding to the input (that is: input_txid[output_index])
                    tx_ins = []
                    for vin in raw_tx["vin"]:
                        # If the tx is a coinbase tx - set `coinbase` to True
                        if "coinbase" in vin:
                            raw_tx["coinbase"] = True
                            break
                        # If the tx is a coinbase tx - set `coinbase` to True
                        vin_txid = vin["txid"]
                        vin_vout = vin["vout"]
                        tx_in = self.cli.getrawtransaction(vin_txid, 1)["vout"][vin_vout]
                        tx_in["txid"] = vin["txid"]
                        tx_ins.append(tx_in)
                    # For each output in the tx_ins list (the tx inputs in their output "format")
                    # Create object with the address, amount, and whatever the address belongs to the wallet (`internal=True` if it is).
                    raw_tx["from"] = [{"address": out["scriptPubKey"]["addresses"][0], "amount": out["value"], "internal": out["scriptPubKey"]["addresses"][0] in cache[self["name"]]["addresses"]} for out in tx_ins]
                    # For each output in the tx (`vout`)
                    # Create object with the address, amount, and whatever the address belongs to the wallet (`internal=True` if it is).
                    raw_tx["to"] = [({"address": out["scriptPubKey"]["addresses"][0], "amount": out["value"], "internal": out["scriptPubKey"]["addresses"][0] in cache[self["name"]]["addresses"]}) for out in raw_tx["vout"] if "addresses" in out["scriptPubKey"]]
                    # Save the raw_transaction to the cache
                    cache[self["name"]]["raw_transactions"][txid] = raw_tx
            # Set the tx count to avoid unnecessary indexing
            cache[self["name"]]["tx_count"] = tx_count
            # Set the tx changed to indicate the there are new transactions to cache
            cache[self["name"]]["tx_changed"] = True
        else:
            # Set the tx changed to False to avoid unnecessary indexing
            cache[self["name"]]["tx_changed"] = False

    def cache_labels(self):
        """Cache labels for addresses (if not cached already)
        """
        # This list is updated from the `self.setlabel` method
        if len(cache[self["name"]]["labels"]) == 0:
            cache[self["name"]]["labels"] = {address: self.getlabel(address) for address in cache[self["name"]]["addresses"]}
    
    def cache_confirmations(self):
        """Update the confirmations count for txs.
        """
        # Get the block count from Bitcoin Core
        blocks = self.cli.getblockcount()
        # If there are new blocks since the last cache update
        if blocks != cache[self["name"]]["last_block"] or cache[self["name"]]["tx_changed"]:
            # Loop through the cached `transactions` and update its confirmations according to the cached `cli_txs` data 
            for i in range(0, len(cache[self["name"]]["transactions"])):
                confs = cache[self["name"]]["cli_txs"][cache[self["name"]]["transactions"][i]["txid"]]["confirmations"]
                cache[self["name"]]["transactions"][i]["confirmations"] = confs

            # Update last block confirmations were cached for
            cache[self["name"]]["last_block"] = blocks

    def cache_txs(self):
        """Caches the transactions list.
            Cache the inputs and outputs which belong to the user's wallet for each `raw_transaction` 
            This method relies on a few assumptions regarding the txs format to cache data properly:
                - In `send` transactions, all inputs belong to the wallet.
                - In `send` transactions, there is only one output not belonging to the wallet (i.e. only one recipient).
                - In `coinbase` transactions, there is only one input.
                - Change addresses are derived from the path used by Specter
        """
        # Get the cached `raw_transactions` dict (txid -> tx) as a list of txs
        transactions = list(sorted(cache[self["name"]]["raw_transactions"].values(), key = lambda tx: tx['time'], reverse=True))
        result = []

        # If the `raw_transactions` did not change - exit here.
        if not cache[self["name"]]["tx_changed"]:
            return

        # Loop through the raw_transactions list
        for i, tx in enumerate(transactions):
            # If tx is a user generated one (categories: `send`/ `receive`) and not coinbase (categories: `generated`/ `immature`)
            if tx["category"] == "send" or tx["category"] == "receive":
                is_send = True
                is_self = True

                # Check if the transaction is a `send` or not (if all inputs belong to the wallet)
                for fromdata in tx["from"]:
                    if not fromdata["internal"]:
                        is_send = False

                # Check if the transaction is a `self-transfer` (if all inputs and all outputs belong to the wallet)
                for to in tx["to"]:
                    if not is_send or not to["internal"]:
                        is_self = False
                        break

                tx["is_self"] = is_self

                if not is_send or is_self:
                    for to in tx["to"]:
                        if to["internal"]:
                            # Cache received outputs
                            result.append(self.prepare_tx(tx, to, "receive", destination=None, is_change=(to["address"] in self.change_addresses)))

                if is_send or is_self:
                    destination = None
                    for to in tx["to"]:
                        if to["address"] in self.change_addresses:
                            # Cache change output
                            result.append(self.prepare_tx(tx, to, "receive", destination=destination, is_change=True))
                        elif not to["internal"] or (is_self and to["address"] not in self.change_addresses):
                            destination = to
                    for fromdata in tx["from"]:
                        # Cache sent inputs
                        result.append(self.prepare_tx(tx, fromdata, "send", destination=destination))
            else:
                tx["is_self"] = False
                # Cache coinbase output
                result.append(self.prepare_tx(tx, tx["to"][0], tx["category"]))

        # Save the result to the cache
        cache[self["name"]]["transactions"] = result
    
    def prepare_tx(self, tx, output, category, destination=None, is_change=False):
        tx_clone = tx.copy()
        tx_clone["destination"] = destination
        tx_clone["address"] = output["address"]
        tx_clone["label"] = self.getlabel(tx_clone["address"])
        tx_clone["amount"] = output["amount"]
        tx_clone["category"] = category
        tx_clone["is_change"] = is_change
        return tx_clone

    def update_cache(self):
        self.setup_cache()
        self.cache_cli_txs()
        self.cache_addresses()
        self.cache_labels()
        self.cache_raw_txs()
        self.cache_txs()
        self.cache_confirmations()

    def rebuild_cache(self):
        del cache[self["name"]]
        self.update_cache()

    @property
    def transactions(self):
        if self["name"] not in cache or "transactions" not in cache[self["name"]] or len(cache[self["name"]]["transactions"]) == 0:
            return self.cli_transactions
        return cache[self["name"]]["transactions"]
    
    @property
    def cli_transactions(self):
        return self.cli.listtransactions("*", 1000, 0, True)[::-1]

    @property
    def txlist(self):
        txidlist = []
        txlist = []
        for tx in cache[self["name"]]["transactions"]:
            if tx["is_change"] == False and (tx["is_self"] or tx["txid"] not in txidlist):
                txidlist.append(tx["txid"])
                txlist.append(tx)
        return txlist

    def getdata(self):
        try:
            self.balance = self.getbalances()
        except:
            self.balance = None
        try:
            self.utxo = self.cli.listunspent(0)
        except:
            self.utxo = None
        try:
            self.info = self.cli.getwalletinfo()
        except:
            self.info = None

        if self["name"] not in cache:
            self.update_cache()

        self._check_change()
        return {
            "balance": self.balance,
            "transactions": self.transactions,
            "utxo": self.utxo
        }

    @property
    def rescan_progress(self):
        """Returns None if rescanblockchain is not launched,
           value between 0 and 1 otherwise
        """
        if self.info is None or "scanning" not in self.info or self.info["scanning"] == False:
            return None
        else:
            return self.info["scanning"]["progress"]

    def getnewaddress(self):
        self._dict["address_index"] += 1
        addr = self.get_address(self._dict["address_index"])
        self.setlabel(addr, "Address #{}".format(self._dict["address_index"]))
        self._dict["address"] = addr
        self._commit()
        return addr

    def get_address(self, index, change=False):
        # FIXME: refactor wallet dict keys to get rid of this
        pool, desc = ("keypool", "recv_descriptor")
        if change:
            pool, desc = ("change_keypool", "change_descriptor")
        if self._dict[pool] < index+WALLET_CHUNK:
            self.keypoolrefill(self._dict[pool], index+WALLET_CHUNK, change=change)
        if self.is_multisig:
            # using sortedmulti for addresses
            sorted_desc = self.sort_descriptor(self[desc], index)
            return self.cli.deriveaddresses(sorted_desc)[0]
        return self.cli.deriveaddresses(self._dict[desc], [index, index+1])[0]

    def geterror(self):
        if self.cli.r is not None:
            try:
                err = self.cli.r.json()
            except:
                return self.cli.r.text
            if "error" in err:
                if "message" in err["error"]:
                    return err["error"]["message"]
                return err
            return self.cli.r
        return None

    def getbalance(self, *args, **kwargs):
        ''' wrapping the cli-call:
            Returns the total available balance.
            The available balance is what the wallet considers currently spendable '''
        default_args = ["*", 0, True]
        args = list(args) + default_args[len(args):]
        try:
            return self.cli.getbalance(*args, **kwargs)
        except:
            return None

    def getbalances(self, *args, **kwargs):
        ''' 18.1 doesn't support it, so we need to build it ourselves... '''
        r = { 
            "trusted": 0,
            "untrusted_pending": 0,
        }
        try:
            r["trusted"] = self.getbalance()
            unspent = self.cli.listunspent(0, 0)
            for t in unspent:
                r["untrusted_pending"] += t["amount"]
        except:
            r = { "trusted": None, "untrusted_pending": None }
        self.balance = r
        return r

    def getfullbalance(self):
        ''' Returns sum of trusted balances AND pending transactions '''
        r = self.getbalances()
        if r["trusted"] is None:
            return None
        return r["trusted"]+r["untrusted_pending"]

    def sort_descriptor(self, descriptor, index=None):
        if index is not None:
            descriptor = descriptor.replace("*", f"{index}")
        # remove checksum
        descriptor = descriptor.split("#")[0]

        # get address (should be already imported to the wallet)
        address = self.cli.deriveaddresses(AddChecksum(descriptor))[0]

        # get pubkeys involved
        address_info = self.cli.getaddressinfo(address)
        if 'pubkeys' in address_info:
            pubkeys = address_info["pubkeys"]
        elif 'embedded' in address_info and 'pubkeys' in address_info['embedded']:
            pubkeys = address_info["embedded"]["pubkeys"]
        else:
            raise Exception("Could not find 'pubkeys' in address info:\n%s" % json.dumps(address_info, indent=2))

        # get xpubs from the descriptor
        arr = descriptor.split("(multi(")[1].split(")")[0].split(",")

        # getting [wsh] or [sh, wsh]
        prefix = descriptor.split("(multi(")[0].split("(")
        sigs_required = arr[0]
        keys = arr[1:]

        # sort them according to sortedmulti
        z = sorted(zip(pubkeys,keys), key=lambda x: x[0])
        keys = [zz[1] for zz in z]
        inner = f"{sigs_required},"+",".join(keys)
        desc = f"multi({inner})"

        # Write from the inside out
        prefix.reverse()
        for p in prefix:
            desc = f"{p}({desc})"

        return AddChecksum(desc)

    def keypoolrefill(self, start, end=None, change=False):
        if end is None:
            end = start + WALLET_CHUNK
        desc = "recv_descriptor" if not change else "change_descriptor"
        pool = "keypool" if not change else "change_keypool"
        args = [
            {
                "desc": self[desc],
                "internal": change, 
                "range": [start, end], 
                "timestamp": "now", 
                "keypool": True, 
                "watchonly": True
            }
        ]
        r = self.cli.importmulti(args, {"rescan": False}, timeout=120)
        # bip67 requires sorted public keys for multisig addresses
        if self.is_multisig:
            # we do one at a time
            args[0].pop("range")
            for i in range(start, end):
                sorted_desc = self.sort_descriptor(self[desc], i)
                args[0]["desc"] = sorted_desc
                self.cli.importmulti(args, {"rescan": False}, timeout=120)
        self._dict[pool] = end
        self._commit(update_manager=False)
        return end
    
    def txonaddr(self, addr):
        txlist = [tx for tx in self.transactions if tx["address"] == addr]
        return len(txlist)

    def balanceonaddr(self, addr):
        balancelist = [utxo["amount"] for utxo in self.utxo if utxo["address"] == addr]
        return sum(balancelist)

    def txonlabel(self, label):
        txlist = [tx for tx in self.transactions if (tx["label"] == label if "label" in tx else tx["address"] == label)]
        return len(txlist)

    def balanceonlabel(self, label):
        balancelist = [utxo["amount"] for utxo in self.utxo if ("label" in utxo and utxo["label"] == label) or utxo["address"] == label]
        return sum(balancelist)

    def addressesonlabel(self, label):
        return list(dict.fromkeys(
            [tx["address"] for tx in self.transactions if (tx["label"] == label if "label" in tx else tx["address"] == label)]
        ))

    def istxspent(self, txid):
        return txid in [utxo["txid"] for utxo in self.utxo]

    def setlabel(self, addr, label):
        self.cli.setlabel(addr, label)
        old_label = cache[self["name"]]["labels"][addr] if addr in cache[self["name"]]["labels"] else addr
        cache[self["name"]]["labels"][addr] = label
        for i, tx in enumerate(self.transactions):
            if tx["label"] == old_label if "label" in tx else tx["address"] == old_label:
                self.transactions[i]["label"] = label

    def getlabel(self, addr):
        if addr in cache[self["name"]]["labels"]:
            return cache[self["name"]]["labels"][addr]
        address_info = self.cli.getaddressinfo(addr)
        return address_info["label"] if "label" in address_info and address_info["label"] != "" else addr
    
    def getaddressname(self, addr, addr_idx):
        address_info = self.cli.getaddressinfo(addr)
        if ("label" not in address_info or address_info["label"] == "") and addr_idx > -1:
            self.setlabel(addr, "Address #{}".format(addr_idx))
            address_info["label"] = "Address #{}".format(addr_idx)
        return addr if ("label" not in address_info or address_info["label"] == "") else address_info["label"]

    @property    
    def fullbalance(self):
        ''' This is cached. Consider to use getfullbalance '''
        if self.balance is None:
            return None
        if self.balance["trusted"] is None or self.balance["untrusted_pending"] is None:
            return None
        return self.balance["trusted"]+self.balance["untrusted_pending"]

    @property
    def descriptor(self):
        return self['recv_descriptor'].split("#")[0].replace("/0/*", "").replace("multi", "sortedmulti")

    @property
    def fingerprint(self):
        """ Unique fingerprint of the wallet - first 4 bytes of hash160 of its descriptor """
        h256 = hashlib.sha256(self.descriptor.encode()).digest()
        h160 = hashlib.new('ripemd160', h256).digest()
        return h160[:4]

    @property
    def txoncurrentaddr(self):
        addr = self["address"]
        return self.txonaddr(addr)

    @property
    def utxoaddresses(self):
        return list(dict.fromkeys([
            utxo["address"] for utxo in 
            sorted(
                self.utxo,
                key = lambda utxo: cache[self["name"]]["cli_txs"][utxo["txid"]]["time"]
            )
        ]))

    @property
    def utxolabels(self):
        return list(dict.fromkeys([
            utxo["label"] if "label" in utxo and utxo["label"] != "" else utxo["address"] for utxo in 
            sorted(
                self.utxo,
                key = lambda utxo: next(
                    tx for tx in self.transactions if tx["txid"] == utxo["txid"]
                )["time"]
            )
        ]))

    @property
    def addresses(self):
        addresses = [self.get_address(idx) for idx in range(0,self._dict["address_index"] + 1)]
        return list(dict.fromkeys(addresses + self.utxoaddresses))
    
    @property
    def change_addresses(self):
        return [self.get_address(idx, change=True) for idx in range(0,self._dict["change_index"] + 1)]

    @property
    def labels(self):
        return list(dict.fromkeys([self.getlabel(addr) for addr in self.addresses]))

    def createpsbt(self, address:str, amount:float, subtract:bool=False, fee_rate:float=0.0, fee_unit="SAT_B"):
        """
            fee_rate: in sat/B or BTC/kB. Default (None) bitcoin core sets feeRate automatically.
        """
        if self.fullbalance < amount:
            return None
        print (fee_unit)
        if fee_unit not in ["SAT_B", "BTC_KB"]:
            raise ValueError('Invalid bitcoin unit')

        extra_inputs = []
        if self.balance["trusted"] < amount:
            txlist = self.cli.listunspent(0,0)
            b = amount-self.balance["trusted"]
            for tx in txlist:
                extra_inputs.append({"txid": tx["txid"], "vout": tx["vout"]})
                b -= tx["amount"]
                if b < 0:
                    break;

        # subtract fee from amount of this output:
        # currently only one address is supported, so either
        # empty array (subtract from change) or [0]
        subtract_arr = [0] if subtract else []

        options = {   
            "includeWatching": True, 
            "changeAddress": self["change_address"],
            "subtractFeeFromOutputs": subtract_arr
        }

        self.setlabel(self["change_address"], "Change #{}".format(self._dict["change_index"]))

        if fee_rate > 0.0 and fee_unit == "SAT_B":
            # bitcoin core needs us to convert sat/B to BTC/kB
            options["feeRate"] = fee_rate / 10 ** 8 * 1024

        # Dont reuse change addresses - use getrawchangeaddress instead
        r = self.cli.walletcreatefundedpsbt(
            extra_inputs,           # inputs
            [{address: amount}],    # output
            0,                      # locktime
            options,                # options
            True                    # replaceable
        )
        b64psbt = r["psbt"]
        psbt = self.cli.decodepsbt(b64psbt)
        psbt['base64'] = b64psbt
        # adding xpub fields for coldcard
        cc_psbt = PSBT()
        cc_psbt.deserialize(b64psbt)
        if self.is_multisig:
            for k in self._dict["keys"]:
                key = b'\x01'+helpers.decode_base58(k["xpub"])
                value = bytes.fromhex(k["fingerprint"])+der_to_bytes(k["derivation"])
                cc_psbt.unknown[key] = value
        psbt["coldcard"]=cc_psbt.serialize()

        # removing unnecessary fields for specter
        # to reduce size of the QR code
        qr_psbt = PSBT()
        qr_psbt.deserialize(b64psbt)
        for inp in qr_psbt.inputs + qr_psbt.outputs:
            inp.witness_script = b""
            inp.redeem_script = b""
            if len(inp.hd_keypaths) > 0:
                k = list(inp.hd_keypaths.keys())[0]
                # proprietary field - wallet derivation path
                # only contains two last derivation indexes - change and index
                inp.unknown[b"\xfc\xca\x01"+self.fingerprint] = b"".join([i.to_bytes(4, "little") for i in inp.hd_keypaths[k][-2:]])
                inp.hd_keypaths = {}
        psbt["specter"]=qr_psbt.serialize()
        print("PSBT for Specter:", psbt["specter"])
        return psbt

    def get_cc_file(self):
        CC_TYPES = {
        'legacy': 'BIP45',
        'p2sh-segwit': 'P2WSH-P2SH',
        'bech32': 'P2WSH'
        }
        # try to find at least one derivation
        # cc assume the same derivation for all keys :(
        derivation = None
        for k in self["keys"]:
            if "derivation" in k:
                derivation = k["derivation"].replace("h","'")
                break
        if derivation is None:
            return None
        cc_file = """# Coldcard Multisig setup file (created on Specter Desktop)
#
Name: {}
Policy: {} of {}
Derivation: {}
Format: {}
""".format(self['name'], self['sigs_required'], 
            len(self['keys']), derivation,
            CC_TYPES[self['address_type']]
            )
        for k in self['keys']:
            # cc assumes fingerprint is known
            fingerprint = None
            if 'fingerprint' in k:
                fingerprint = k['fingerprint']
            if fingerprint is None:
                return None
            cc_file += "{}: {}\n".format(fingerprint.upper(), k['xpub'])
        return cc_file

def der_to_bytes(derivation):
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

if __name__ == '__main__':
    # specter = Specter("~/_specter", config={"rpc":{"port":18332}})
    # specter = Specter(config={"rpc":{"port":18332}})
    specter = Specter("~/.specter")
    w = specter.wallets['Stupid']
    print(w.getbalances())
    # print(w.getbalance("*", 0, True))
    # for v in specter.devices:
    #     print(v)
        # print(v.is_multisig)
