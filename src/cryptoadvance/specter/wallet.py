import hashlib, json, logging, os
from time import time
from .descriptor import AddChecksum
from .device import Device
from .helpers import decode_base58, der_to_bytes, get_xpub_fingerprint
from .serializations import PSBT
from .specter_error import SpecterError


# a gap of 20 addresses is what many wallets do
WALLET_CHUNK = 20

class Wallet(dict):
    def __init__(self, d, manager=None):
        self.update(d)
        self.manager = manager
        self.cli_path = manager.cli_path
        self.cli = manager.cli.wallet(os.path.join(self.cli_path,self["alias"]))
        # check if address is known and derive if not
        # address derivation will also refill the keypool if necessary
        if self["address"] is None:
            self["address"] = self.get_address(0)
            self.setlabel(self["address"], "Address #0")

        self.cli.scan_addresses(self)
        self.getdata()

    def getdata(self):
        self.getbalances()

        try:
            self.utxo = self.cli.listunspent(0)
        except:
            self.utxo = []
        try:
            self.transactions = self.cli.listtransactions("*", 1000, 0, True)
        except:
            self.transactions = []
        try:
            self.info = self.cli.getwalletinfo()
        except:
            self.info = {}

        self._check_change()

    def _check_change(self):
        addr = self["change_address"]
        if addr is not None:
            # check if address was used already
            v = self.cli.getreceivedbyaddress(addr, 0)
            # if not - just return
            if v == 0:
                return
            self["change_index"] += 1
        else:
            if "change_index" not in self:
                self["change_index"] = 0
            index = self["change_index"]
        self["change_address"] = self.get_address(self["change_index"], change=True)
        self._commit()

    def _commit(self, update_manager=True):
        with open(self["fullpath"], "w") as f:
            f.write(json.dumps(self, indent=4))
        self.update(self)
        if update_manager:
            self.manager.update()

    def _uses_device_type(self, type_list):
        if not self.is_multisig:
            return self["device_type"] in type_list
        else:
            for device in self["devices"]:
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
        if "pending_psbts" not in self:
            return {}
        return self["pending_psbts"]

    @property
    def locked_amount(self):
        amount = 0
        for psbt in self.pending_psbts:
            amount += sum([utxo["witness_utxo"]["amount"] for utxo in self.pending_psbts[psbt]["inputs"]])
        return amount

    def delete_pending_psbt(self, txid):
        try:
            self.cli.lockunspent(True, self["pending_psbts"][txid]["tx"]["vin"])
        except:
            # UTXO was spent
            pass
        del self["pending_psbts"][txid]
        self._commit()

    def update_pending_psbt(self, psbt, txid, raw, device_name):
        if txid in self["pending_psbts"]:
            self["pending_psbts"][txid]["sigs_count"] += 1
            self["pending_psbts"][txid]["base64"] = psbt
            if device_name:
                if "devices_signed" not in self["pending_psbts"][txid]:
                    self["pending_psbts"][txid]["devices_signed"] = []
                self["pending_psbts"][txid]["devices_signed"].append(device_name)
            if "hex" in raw:
                self["pending_psbts"][txid]["raw"] = raw["hex"]
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

    @property
    def rescan_progress(self):
        """Returns None if rescanblockchain is not launched,
           value between 0 and 1 otherwise
        """
        if self.info is {} or "scanning" not in self.info or self.info["scanning"] == False:
            return None
        else:
            return self.info["scanning"]["progress"]

    def getnewaddress(self, change=False):
        label = "Change" if change else "Address"
        index_type = "change_index" if change else "address_index"
        address_type = "change_address" if change else "address"
        self[index_type] += 1
        addr = self.get_address(self[index_type], change=change)
        self.setlabel(addr, "{} #{}".format(label, self[index_type]))
        self[address_type] = addr
        self._commit()
        return addr

    def get_address(self, index, change=False):
        # FIXME: refactor wallet dict keys to get rid of this
        pool, desc = ("keypool", "recv_descriptor")
        if change:
            pool, desc = ("change_keypool", "change_descriptor")
        if self[pool] < index+WALLET_CHUNK:
            self.keypoolrefill(self[pool], index+WALLET_CHUNK, change=change)
        if self.is_multisig:
            # using sortedmulti for addresses
            sorted_desc = self.sort_descriptor(self[desc], index=index, change=change)
            return self.cli.deriveaddresses(sorted_desc, change=change)[0]
        return self.cli.deriveaddresses(self[desc], [index, index+1], change=change)[0]

    def getbalance(self, *args, **kwargs):
        ''' wrapping the cli-call:
            Returns the total available balance.
            The available balance is what the wallet considers currently spendable '''
        default_args = ["*", 0, True]
        args = list(args) + default_args[len(args):]
        try:
            return self.cli.getbalance(*args, **kwargs)
        except:
            return 0

    def getbalances(self, *args, **kwargs):
        ''' 18.1 doesn't support it, so we need to build it ourselves... '''
        result = { 
            "trusted": 0,
            "untrusted_pending": 0,
        }

        try:
            result["trusted"] = self.getbalance()
            utxos = self.cli.listunspent(0, 0)
            for utxo in utxos:
                result["untrusted_pending"] += utxo["amount"]
            # Bitcoin Core doesn't return locked UTXO with `listunspent` command. 
            # `getbalance` command doesn't return balance from unconfirmed UTXO.
            # So to imitate `getbalances` we need to add all unconfirmed locked UTXO balance manually with this loop.
            locked_utxo = self.cli.listlockunspent()
            for tx in locked_utxo:
                tx_data = self.cli.gettransaction(tx["txid"])
                raw_tx = self.cli.decoderawtransaction(tx_data["hex"])
                if "confirmations" not in tx_data or tx_data["confirmations"] == 0:
                    result["untrusted_pending"] += raw_tx["vout"][tx["vout"]]["value"]
        except:
            result = { "trusted": 0, "untrusted_pending": 0 }
        self.balance = result
        return result

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
        self[pool] = end
        self._commit(update_manager=False)
        return end
    
    def tx_on_address(self, addr):
        txlist = [tx for tx in self.transactions if tx["address"] == addr]
        return len(txlist)

    def balance_on_address(self, addr):
        balancelist = [utxo["amount"] for utxo in self.utxo if utxo["address"] == addr]
        return sum(balancelist)

    def tx_on_label(self, label):
        txlist = [tx for tx in self.transactions if self.getlabel(tx["address"]) == label]
        return len(txlist)

    def balance_on_label(self, label):
        balancelist = [utxo["amount"] for utxo in self.utxo if self.getlabel(utxo["address"]) == label]
        return sum(balancelist)

    def addresses_on_label(self, label):
        return list(dict.fromkeys(
            [tx["address"] for tx in self.transactions if self.getlabel(tx["address"]) == label]
        ))

    def is_tx_spent(self, txid):
        return txid in [utxo["txid"] for utxo in self.utxo]

    @property
    def tx_on_current_address(self):
        return self.tx_on_address(self["address"])

    @property
    def utxo_addresses(self):
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
    def utxo_labels(self):
        return list(dict.fromkeys([
            self.getlabel(utxo["address"]) for utxo in 
            sorted(
                self.utxo,
                key = lambda utxo: next(
                    tx for tx in self.transactions if tx["txid"] == utxo["txid"]
                )["time"]
            )
        ]))

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
        self.getbalances()
        return self.balance["trusted"] + self.balance["untrusted_pending"]

    @property
    def availablebalance(self):
        self.getbalances()
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
    def addresses(self):
        return [self.get_address(idx) for idx in range(0,self["address_index"] + 1)]

    @property
    def active_addresses(self):
        return list(dict.fromkeys(self.addresses + self.utxo_addresses))
    
    @property
    def change_addresses(self):
        return [self.get_address(idx, change=True) for idx in range(0,self["change_index"] + 1)]

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

        self.setlabel(self["change_address"], "Change #{}".format(self["change_index"]))

        if fee_rate > 0.0 and fee_unit == "SAT_B":
            # bitcoin core needs us to convert sat/B to BTC/kB
            options["feeRate"] = fee_rate / 10 ** 8 * 1024

        # don't reuse change addresses - use getrawchangeaddress instead
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
            for k in self["keys"]:
                key = b'\x01' + decode_base58(k["xpub"])
                if "fingerprint" in k and k["fingerprint"] is not None:
                    fingerprint = bytes.fromhex(k["fingerprint"])
                else:
                    fingerprint = get_xpub_fingerprint(k["xpub"])
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

        if "pending_psbts" not in self:
            self["pending_psbts"] = {}
        psbt["amount"] = amount
        psbt["address"] = address
        psbt["time"] = time()
        psbt["sigs_count"] = 0
        self["pending_psbts"][psbt["tx"]["txid"]] = psbt
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
