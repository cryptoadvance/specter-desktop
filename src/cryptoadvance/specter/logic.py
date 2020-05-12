import base64
import copy
import json
import os
import shutil
import random
import hashlib
from time import time
from collections import OrderedDict

from . import helpers
from .descriptor import AddChecksum
from .helpers import deep_update, load_jsons, get_xpub_fingerprint
from .rpc import RPC_PORTS, autodetect_cli_confs, get_default_datadir
from .rpc_cache import BitcoinCLICached
from .serializations import PSBT


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
            cli_conf_arr = autodetect_cli_confs(port=conf["port"])
        else:
            cli_conf_arr = autodetect_cli_confs()
        if len(cli_conf_arr) > 0:
            cli = BitcoinCLICached(**cli_conf_arr[0])
        else:
            return None
    else:
        cli = BitcoinCLICached(conf["user"], conf["password"], 
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
                self._info = self.cli.getblockchaininfo()
                self._is_running = True
            except:
                pass

        if not self._is_running:
            self._info["chain"] = None

        chain = self._info["chain"]
        if self.wallets is None or chain is None:
            wallets_path = "specter%s" % self.config["uid"]
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
        arr = sorted(list(self._devices.keys()))
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
    def __init__(self, data_folder, cli, chain, path="specter"):
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
                if os.path.join(self.cli_path,wallets[k]["alias"]) in existing_wallets:
                    self._wallets[k] = wallets[k]
        else:
            self._wallets = {}

    def load_all(self):
        loaded_wallets = self.cli.listwallets()
        loadable_wallets = [w["name"] for w in self.cli.listwalletdir()["wallets"]]
        not_loaded_wallets = [w for w in loadable_wallets if w not in loaded_wallets]
        # print("not loaded wallets:", not_loaded_wallets)
        for k in self._wallets:
            if os.path.join(self.cli_path,self._wallets[k]["alias"]) in not_loaded_wallets:
                print("loading", self._wallets[k]["alias"])
                self.cli.loadwallet(os.path.join(self.cli_path,self._wallets[k]["alias"]))
                if "pending_psbts" in self._wallets[k] and len(self._wallets[k]["pending_psbts"]) > 0:
                    for psbt in self._wallets[k]["pending_psbts"]:
                        print("lock", self._wallets[k]["alias"], self._wallets[k]["pending_psbts"][psbt]["tx"]["vin"])
                        Wallet(self._wallets[k], self).cli.lockunspent(False, [utxo for utxo in self._wallets[k]["pending_psbts"][psbt]["tx"]["vin"]])

    def get_by_alias(self, alias):
        for w in self:
            if w["alias"] == alias:
                return w

    def names(self):
        return list(self._wallets.keys())

    def _get_intial_wallet_dict(self, name):
        walletsindir = [wallet["name"] for wallet in self.cli.listwalletdir()["wallets"]]
        al = alias(name)
        i = 2
        while os.path.isfile(os.path.join(self.working_folder, "%s.json" % al)) or os.path.join(self.cli_path,al) in walletsindir:
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
            "pending_psbts": {}
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
        r = self.cli.createwallet(os.path.join(self.cli_path,o["alias"]), True)
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
        r = self.cli.createwallet(os.path.join(self.cli_path,o["alias"]), True)
        # save wallet file to disk
        if self.working_folder is not None:
            with open(o["fullpath"], "w+") as f:
                f.write(json.dumps(o, indent=4))
        # update myself - loads wallet files
        self.update()
        # get Wallet class instance
        w = Wallet(o, self)
        return w

    def delete_wallet(self, wallet):
        print("Deleting {}".format(wallet["alias"]))
        self.cli.unloadwallet(os.path.join(self.cli_path,wallet["alias"]))
        # Try deleting wallet file
        if get_default_datadir() and os.path.exists(os.path.join(get_default_datadir(), os.path.join(self.cli_path,wallet["alias"]))):
            shutil.rmtree(os.path.join(get_default_datadir(), os.path.join(self.cli_path,wallet["alias"])))
        # Delete JSON
        if os.path.exists(wallet["fullpath"]):
            os.remove(wallet["fullpath"])

    def rename_wallet(self, wallet, name):
        print("Renaming {}".format(wallet["alias"]))
        wallet["name"] = name
        if self.working_folder is not None:
            with open(wallet["fullpath"], "w+") as f:
                f.write(json.dumps(wallet, indent=4))
        self.update()

    def __getitem__(self, name):
        return Wallet(self._wallets[name], manager=self)

    def __iter__(self):
        self._n = 0
        return self

    def __next__(self):
        arr = sorted(list(self._wallets.keys()))
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
        self.cli = manager.cli.wallet(os.path.join(self.cli_path,self["alias"]))
        self._dict = d
        # check if address is known and derive if not
        # address derivation will also refill the keypool if necessary
        if self._dict["address"] is None:
            self._dict["address"] = self.get_address(0)
            self.setlabel(self._dict["address"], "Address #0")
        if self._dict["change_address"] is None:
            self._dict["change_address"] = self.get_address(0, change=True)
        self.cli.scan_addresses(self)
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

    @property
    def sigs_required(self):
        return 1 if not self.is_multisig else self["sigs_required"]

    @property
    def pending_psbts(self):
        if "pending_psbts" not in self._dict:
            return {}
        return self._dict["pending_psbts"]

    @property
    def locked_amount(self):
        amount = 0
        for psbt in self.pending_psbts:
            amount += sum([utxo["witness_utxo"]["amount"] for utxo in self.pending_psbts[psbt]["inputs"]])
        return amount

    def delete_pending_psbt(self, txid):
        try:
            self.cli.lockunspent(True, self._dict["pending_psbts"][txid]["tx"]["vin"])
        except:
            # UTXO was spent
            pass
        del self._dict["pending_psbts"][txid]
        self._commit()

    def update_pending_psbt(self, psbt, txid, device_name):
        if txid in self._dict["pending_psbts"]:
            if self._dict["pending_psbts"][txid]["sigs_count"] + 1 == self.sigs_required:
                self.delete_pending_psbt(txid)
                return
            self._dict["pending_psbts"][txid]["sigs_count"] += 1
            self._dict["pending_psbts"][txid]["base64"] = psbt
            if device_name:
                if "devices_signed" not in self._dict["pending_psbts"][txid]:
                    self._dict["pending_psbts"][txid]["devices_signed"] = []
                self._dict["pending_psbts"][txid]["devices_signed"].append(device_name)
            self._commit()

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

    @property
    def txlist(self):
        ''' The last 1000 transactions for that wallet - filtering out change addresses transactions and duplicated transactions (except for self-transfers)
            This list is used for the wallet `txs` tab to list the wallet transacions.
        '''
        txidlist = []
        txlist = []
        for tx in self.transactions:
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
            self.transactions = self.cli.listtransactions("*", 1000, 0, True)
        except:
            self.transactions = None
        try:
            self.info = self.cli.getwalletinfo()
        except:
            self.info = None

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

    def getnewaddress(self, change=False):
        label = "Change" if change else "Address"
        index_type = "change_index" if change else "address_index"
        address_type = "change_address" if change else "address"
        self._dict[index_type] += 1
        addr = self.get_address(self._dict[index_type], change=change)
        self.setlabel(addr, "{} #{}".format(label, self._dict[index_type]))
        self._dict[address_type] = addr
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
            sorted_desc = self.sort_descriptor(self[desc], index=index, change=change)
            return self.cli.deriveaddresses(sorted_desc, change=change)[0]
        return self.cli.deriveaddresses(self._dict[desc], [index, index+1], change=change)[0]

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
            # Bitcoin Core doesn't return locked UTXO with `listunspent` command. 
            # `getbalance` command doesn't return balance from unconfirmed UTXO.
            # So to imitate `getbalances` we need to add all unconfirmed locked UTXO balance manually with this loop.
            locked_utxo = self.cli.listlockunspent()
            for tx in locked_utxo:
                tx_data = self.cli.gettransaction(tx["txid"])
                raw_tx = self.cli.decoderawtransaction(tx_data["hex"])
                if "confirmations" not in tx_data or tx_data["confirmations"] == 0:
                    r["untrusted_pending"] += raw_tx["vout"][tx["vout"]]["value"]
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

    def sort_descriptor(self, descriptor, index=None, change=False):
        if index is not None:
            descriptor = descriptor.replace("*", f"{index}")
        # remove checksum
        descriptor = descriptor.split("#")[0]

        # get address (should be already imported to the wallet)
        address = self.cli.deriveaddresses(AddChecksum(descriptor), change=change)[0]

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
                sorted_desc = self.sort_descriptor(self[desc], index=i, change=change)
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
        txlist = [tx for tx in self.transactions if self.getlabel(tx["address"]) == label]
        return len(txlist)

    def balanceonlabel(self, label):
        balancelist = [utxo["amount"] for utxo in self.utxo if self.getlabel(utxo["address"]) == label]
        return sum(balancelist)

    def addressesonlabel(self, label):
        return list(dict.fromkeys(
            [tx["address"] for tx in self.transactions if self.getlabel(tx["address"]) == label]
        ))

    def istxspent(self, txid):
        return txid in [utxo["txid"] for utxo in self.utxo]

    def setlabel(self, addr, label):
        self.cli.setlabel(addr, label)

    def getlabel(self, addr):
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
    def availablebalance(self):
        ''' This is cached.'''
        if self.balance is None:
            return None
        if self.balance["trusted"] is None or self.balance["untrusted_pending"] is None:
            return None
        locked = [0]
        for psbt in self.pending_psbts:
            for i, txid in enumerate([tx["txid"] for tx in self.pending_psbts[psbt]["tx"]["vin"]]):
                tx_data = self.cli.gettransaction(txid)
                if "confirmations" in tx_data and tx_data["confirmations"] != 0:
                    locked.append(self.pending_psbts[psbt]["inputs"][i]["witness_utxo"]["amount"])
        return self.balance["trusted"]+self.balance["untrusted_pending"] - sum(locked)

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
                key = lambda utxo: next(
                    tx for tx in self.transactions if tx["txid"] == utxo["txid"]
                )["time"]
            )
        ]))

    @property
    def utxolabels(self):
        return list(dict.fromkeys([
            self.getlabel(utxo["address"]) for utxo in 
            sorted(
                self.utxo,
                key = lambda utxo: next(
                    tx for tx in self.transactions if tx["txid"] == utxo["txid"]
                )["time"]
            )
        ]))

    @property
    def addresses(self):
        return [self.get_address(idx) for idx in range(0,self._dict["address_index"] + 1)]

    @property
    def active_addresses(self):
        return list(dict.fromkeys(self.addresses + self.utxoaddresses))
    
    @property
    def change_addresses(self):
        return [self.get_address(idx, change=True) for idx in range(0,self._dict["change_index"] + 1)]

    @property
    def labels(self):
        return list(dict.fromkeys([self.getlabel(addr) for addr in self.active_addresses]))

    def createpsbt(self, address:str, amount:float, subtract:bool=False, fee_rate:float=0.0, fee_unit="SAT_B", selected_coins=[]):
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
        elif selected_coins != []:
            still_needed = amount
            for coin in selected_coins:
                coin_txid = coin.split(",")[0]
                coin_vout = int(coin.split(",")[1])
                coin_amount = float(coin.split(",")[2])
                extra_inputs.append({"txid": coin_txid, "vout": coin_vout})
                still_needed -= coin_amount
                if still_needed < 0:
                    break;
            if still_needed > 0:
                raise SpecterError("Selected coins does not cover Full amount! Please select more coins!")

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
                if "fingerprint" in k and k["fingerprint"] is not None:
                    fingerprint = bytes.fromhex(k["fingerprint"])
                else:
                    fingerprint = helpers.get_xpub_fingerprint(k["xpub"])
                if "derivation" in k and k["derivation"] is not None:
                    der = der_to_bytes(k["derivation"])
                else:
                    der = b''
                value = fingerprint+der
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

        self.cli.lockunspent(False, psbt["tx"]["vin"])

        if "pending_psbts" not in self._dict:
            self._dict["pending_psbts"] = {}
        psbt["amount"] = amount
        psbt["address"] = address
        psbt["time"] = time()
        psbt["sigs_count"] = 0
        self._dict["pending_psbts"][psbt["tx"]["txid"]] = psbt
        self._commit()

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
            if "derivation" in k and k["derivation"] is not None:
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
                fingerprint = get_xpub_fingerprint(k['xpub']).hex()
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
