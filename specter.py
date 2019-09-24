from rpc import BitcoinCLI, RPC_PORTS
import os, json, copy
from helpers import deep_update, load_jsons
from collections import OrderedDict
from descriptor import AddChecksum
import base64

WALLET_CHUNK = 5

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

def load_bitcoin_conf(path=None):
    # trying to find bitcoin.conf in default location
    if path is None:
        # add other platforms later
        paths = ["~/Library/Application Support/Bitcoin/", "~/.bitcoin/"]
        for p in paths:
            p = os.path.expanduser(p)
            if os.path.isfile(os.path.join(p, "bitcoin.conf")):
                path = os.path.join(p, "bitcoin.conf")
                break
    if path is None:
        raise Exception("Didn't find bitcoin.conf in standard folders")
    with open(path, "r") as f:
        content = f.read()
    lines = content.split("\n")
    conf = {}
    for line in lines:
        arr = line.split("#")[0].split("=") # get rid of comments and get values
        if len(arr) == 2:
            k = arr[0].strip()
            v = arr[1].strip()
            if k.startswith("rpc"): #rpcuser, rpcpassword, rpcport
                conf[k[3:]] = v
            if k == "testnet" and v=="1" and "port" not in conf:
                conf["port"] = RPC_PORTS["test"]
            if k == "regtest" and v=="1" and "port" not in conf:
                conf["port"] = RPC_PORTS["regtest"]
    return conf

def alias(name):
    name = name.replace(" ", "_")
    return "".join(x for x in name if x.isalnum() or x=="_").lower()

class Specter:
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
                "user": None,
                "password": None,
                "port": RPC_PORTS["main"],
                "host": "localhost",        # localhost
                "protocol": "http"          # https for the future
            },
            # add hwi later?
        }

        # creating folders if they don't exist
        if not os.path.isdir(data_folder):
            os.mkdir(data_folder)

        self._info = { "chain": None, "last_chain": None }
        # health check: loads config and tests rpc
        self.check()

    def check(self):
        # bitcoin.conf
        try:
            self.config["rpc"].update(load_bitcoin_conf()) # should rize an error if fails
        except:
            pass # not a big deal

        # config.json file
        if os.path.isfile(os.path.join(self.data_folder, "config.json")):
            with open(os.path.join(self.data_folder, "config.json"), "r") as f:
                self.file_config = json.loads(f.read())
                deep_update(self.config, self.file_config)

        # init arguments
        deep_update(self.config, self.arg_config) # override loaded config

        # check if we have user, password and can connect
        self._is_configured = bool(self.config["rpc"]["user"] and self.config["rpc"]["password"])
        self._is_running = False
        if self._is_configured:
            self.cli = BitcoinCLI(self.config["rpc"]["user"], self.config["rpc"]["password"], 
                                  host=self.config["rpc"]["host"], port=self.config["rpc"]["port"], protocol=self.config["rpc"]["protocol"])
            try:
                self._info = self.cli.getmininginfo()
                self._is_running = True
            except:
                # last_chain is used to manage wallets when can't reach bitcoin-cli
                last_chain = self._info["chain"]
                if "last_chain" in self._info and last_chain is None:
                    last_chain = self.info["last_chain"]
                self._info = { "chain": None, "last_chain": last_chain }

        chain = self._info["chain"]
        if chain is None:
            chain = self._info["last_chain"]
        if self.wallets is None:
            self.wallets = WalletManager(os.path.join(self.data_folder, "wallets"), self.cli, chain=chain)
        else:
            self.wallets.update(os.path.join(self.data_folder, "wallets"), self.cli, chain=chain)
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
        cli = BitcoinCLI(conf["user"], conf["password"], 
                              host=conf["host"], port=conf["port"], protocol=conf["protocol"])
        r = {}
        try:
            r["out"] = json.dumps(cli.getmininginfo(),indent=4)
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

    def update_rpc(self, **kwargs):
        need_update = False
        for k in kwargs:
            if self.config["rpc"][k] != kwargs[k]:
                self.config["rpc"][k] = kwargs[k]
                need_update = True
        if need_update:
            with open(os.path.join(self.data_folder, "config.json"), "w") as f:
                f.write(json.dumps(self.config, indent=4))
            self.check()

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

    @property
    def chain(self):
        return self._info["chain"]
    
    
class DeviceManager:
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
    def __init__(self, d, manager=None):
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
            self._wallets = load_jsons(self.working_folder, key="name")
        else:
            self._wallets = {}

    def load_all(self):
        loaded_wallets = self.cli.listwallets()
        loadable_wallets = [w["name"] for w in self.cli.listwalletdir()["wallets"]]
        not_loaded_wallets = [w for w in loadable_wallets if w not in loaded_wallets]
        print(not_loaded_wallets)
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

    def create_simple(self, name, key_type, key, device):
        al = alias(name)
        i = 2
        while os.path.isfile(os.path.join(self.working_folder, "%s.json" % al)):
            al = alias("%s %d" % (name, i))
            i+=1
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
        o = {
            "type": "simple", 
            "name": name,
            "description": purposes[key_type],
            "key": key,
            "recv_descriptor": recv_desc,
            "change_descriptor": change_desc,
            "device": device["name"],
            "address_type": addrtypes[key_type],
            "address_index": 0,
            "keypool": WALLET_CHUNK,
            "address": None,
            "change_index": 0,
            "change_address": None,
            "change_keypool": WALLET_CHUNK,
        }
        self._wallets[al] = o
        args = [
            {
                "desc": recv_desc, 
                "internal": False, 
                "range": [0, WALLET_CHUNK], 
                "timestamp": "now", 
                "keypool": True, 
                "watchonly": True
            }, 
            {
                "desc": change_desc, 
                "internal": True, 
                "range": [0, WALLET_CHUNK], 
                "timestamp": "now", 
                "keypool": True, 
                "watchonly": True
            }
        ]
        r = self.cli.createwallet(self.cli_path+al, True)
        r = self.cli.importmulti(args, {"rescan": False}, wallet=self.cli_path+al, timeout=120)
        addr = self.cli.deriveaddresses(recv_desc, [0, 1])[0]
        change_addr = self.cli.deriveaddresses(change_desc, [0, 1])[0]
        o["address"] = addr
        o["change_address"] = change_addr
        if self.working_folder is not None:
            fullpath = os.path.join(self.working_folder, "%s.json" % al)
            with open(fullpath, "w+") as f:
                f.write(json.dumps(o, indent=4))
            o["alias"] = al
            o["fullpath"] = fullpath
        self.update()
        return Wallet(o, self)

    def create_multi(self, name, sigs_required, key_type, keys, devices):
        al = alias(name)
        i = 2
        while os.path.isfile(os.path.join(self.working_folder, "%s.json" % al)):
            al = alias("%s %d" % (name, i))
            i+=1
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
        o = {
            "type": "multisig",
            "name": name,
            "description": "{} of {} {}".format(sigs_required, len(keys), purposes[key_type]),
            "sigs_required": sigs_required,
            "keys": keys,
            "recv_descriptor": recv_desc,
            "change_descriptor": change_desc,
            "devices": [device["name"] for device in devices],
            "address_type": addrtypes[key_type],
            "address_index": 0,
            "keypool": WALLET_CHUNK,
            "address": None,
            "change_address": None,
            "change_keypool": WALLET_CHUNK,
        }
        self._wallets[al] = o
        args = [
            {
                "desc": recv_desc, 
                "internal": False, 
                "range": [0, o["keypool"]], 
                "timestamp": "now", 
                "keypool": True, 
                "watchonly": True
            }, 
            {
                "desc": change_desc, 
                "internal": True, 
                "range": [0, o["keypool"]], 
                "timestamp": "now", 
                "keypool": True, 
                "watchonly": True
            }
        ]
        r = self.cli.createwallet(self.cli_path+al, True)
        r = self.cli.importmulti(args, {"rescan": False}, wallet=self.cli_path+al, timeout=120)
        print(args)
        addr = self.cli.deriveaddresses(recv_desc, [0, 1])[0]
        o["address"] = addr
        if self.working_folder is not None:
            with open(os.path.join(self.working_folder, "%s.json" % al), "w+") as f:
                f.write(json.dumps(o, indent=4))
        self.update()
        return self[name]

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
        self.getdata()

    def _commit(self):
        with open(self["fullpath"], "w") as f:
            f.write(json.dumps(self._dict, indent=4))
        self.update(self._dict)
        self.manager.update()

    def is_multisig(self):
        return "sigs_required" in self

    def _check_change(self):
        addr = self["change_address"]
        if addr is not None:
            v = self.cli.getreceivedbyaddress(addr, 0)
            if v > 0:
                self._dict["change_index"] += 1
                index = self._dict["change_index"]
                self._dict["change_address"] = self.cli.deriveaddresses(self._dict["change_descriptor"], [index, index+1])[0]
                if index == self._dict["change_keypool"]-1:
                    self._dict["change_keypool"] = self.keypoolrefill(self._dict["change_keypool"])

    def getdata(self):
        try:
            self.balance = self.getbalances()
        except:
            self.balance = None
        try:
            self.transactions = self.cli.listtransactions("*", 20, 0, True)[::-1]
        except:
            self.transactions = None
        self._check_change()
        return {
            "balance": self.balance,
            "transactions": self.transactions
        }

    def getnewaddress(self):
        self._dict["address_index"] += 1
        index = self._dict["address_index"]
        addr = self.cli.deriveaddresses(self._dict["recv_descriptor"], [index, index+1])[0]
        if index == self._dict["keypool"]-1:
            self._dict["keypool"] = self.keypoolrefill(self._dict["keypool"])
        self._dict["address"] = addr
        self._commit()
        return addr

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
        default_args = ["*", 0, True]
        args = list(args) + default_args[len(args):]
        try:
            return self.cli.getbalance(*args, **kwargs)
        except:
            return None

    def getbalances(self, *args, **kwargs):
        """ 18.1 doesn't support it, so we need to build it ourselves... """
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
        r = self.getbalances()
        if r["trusted"] is None:
            return None
        return r["trusted"]+r["untrusted_pending"]

    def keypoolrefill(self, start, end=None, change=False):
        if end is None:
            end = start + WALLET_CHUNK
        desc = self["recv_descriptor"] if not change else self["change_descriptor"]
        args = [
            {
                "desc": self["recv_descriptor"],
                "internal": change, 
                "range": [start, end], 
                "timestamp": "now", 
                "keypool": True, 
                "watchonly": True
            }
        ]
        r = self.cli.importmulti(args, timeout=120)
        return end

    @property    
    def fullbalance(self):
        if self.balance is None:
            return None
        if self.balance["trusted"] is None or self.balance["untrusted_pending"] is None:
            return None
        return self.balance["trusted"]+self.balance["untrusted_pending"]

    def createpsbt(self, address:str, amount:float):
        if self.fullbalance < amount:
            return None
        extra_inputs = []
        if self.balance["trusted"] < amount:
            txlist = self.cli.listunspent(0,0)
            b = amount-self.balance["trusted"]
            for tx in txlist:
                extra_inputs.append({"txid": tx["txid"], "vout": tx["vout"]})
                b -= tx["amount"]
                if b < 0:
                    break;
        # Dont reuse change addresses - use getrawchangeaddress instead
        r = self.cli.walletcreatefundedpsbt(extra_inputs, [{address: amount}], 0, 
                                        {   
                                            "includeWatching": True, 
                                            "changeAddress": self["change_address"]
                                        }, True)
        b64psbt = r["psbt"]
        psbt = self.cli.decodepsbt(b64psbt)
        psbt['base64'] = b64psbt
        return psbt


if __name__ == '__main__':
    # specter = Specter("~/_specter", config={"rpc":{"port":18332}})
    # specter = Specter(config={"rpc":{"port":18332}})
    specter = Specter("~/.specter")
    w = specter.wallets['Stupid']
    print(w.getbalances())
    # print(w.getbalance("*", 0, True))
    # for v in specter.devices:
    #     print(v)
        # print(v.is_multisig())
