import copy, hashlib, json, logging, os
from time import time
from ..descriptor import AddChecksum
from ..devices.device import Device
from ..devices.key import Key
from ..helpers import decode_base58, der_to_bytes, get_xpub_fingerprint
from ..serializations import PSBT
from ..specter_error import SpecterError


# a gap of 20 addresses is what many wallets do
WALLET_CHUNK = 20

class Wallet():

    def __init__(
        self,
        name,
        alias,
        description,
        address_type,
        address,
        address_index,
        change_address,
        change_index,
        keypool,
        change_keypool,
        recv_descriptor,
        change_descriptor,
        keys,
        devices,
        sigs_required,
        pending_psbts,
        fullpath,
        device_manager,
        manager
    ):
        old_format_detected = False
        self.name = name
        self.alias = alias
        self.description = description
        self.address_type = address_type
        self.address = address
        self.address_index = address_index
        self.change_address = change_address
        self.change_index = change_index
        self.keypool = keypool
        self.change_keypool = change_keypool
        self.recv_descriptor = recv_descriptor
        # Migrate from older format
        if len(keys) > 1 and 'sortedmulti' not in recv_descriptor:
            self.recv_descriptor = AddChecksum(self.recv_descriptor.replace('multi', 'sortedmulti').split('#')[0])
            old_format_detected = True
        self.change_descriptor = change_descriptor
        # Migrate from older format
        if len(keys) > 1 and 'sortedmulti' not in change_descriptor:
            self.change_descriptor = AddChecksum(self.change_descriptor.replace('multi', 'sortedmulti').split('#')[0])
            old_format_detected = True
        self.keys = keys
        self.devices = [(device if isinstance(device, Device) else device_manager.get_by_alias(device)) for device in devices]
        if None in self.devices:
            # Migrate from older format using name
            self.devices = [(device_manager.devices[(device['name'] if isinstance(device, dict) else device)] if (device['name'] if isinstance(device, dict) else device) in device_manager.devices else None) for device in devices]
            if None in self.devices:
                raise Exception('A device used by this wallet could not have been found!')
            old_format_detected = True
        self.sigs_required = sigs_required
        self.pending_psbts = pending_psbts
        self.fullpath = fullpath
        self.manager = manager
        self.cli = self.manager.cli.wallet(os.path.join(self.manager.cli_path, self.alias))

        if address == '':
            self.getnewaddress()
        if change_address == '':
            self.getnewaddress(change=True)

        self.cli.scan_addresses(self)
        self.getdata()
        if old_format_detected:
            self.save_to_file()

    @classmethod
    def from_json(cls, wallet_dict, device_manager, manager, default_alias='', default_fullpath=''):
        name = wallet_dict['name'] if 'name' in wallet_dict else ''
        alias = wallet_dict['alias'] if 'alias' in wallet_dict else default_alias
        description = wallet_dict['description'] if 'description' in wallet_dict else ''
        address = wallet_dict['address'] if 'address' in wallet_dict else ''
        address_index = wallet_dict['address_index'] if 'address_index' in wallet_dict else 0
        change_address = wallet_dict['change_address'] if 'change_address' in wallet_dict else ''
        change_index = wallet_dict['change_index'] if 'change_index' in wallet_dict else 0
        keypool = wallet_dict['keypool'] if 'keypool' in wallet_dict else 0
        change_keypool = wallet_dict['change_keypool'] if 'change_keypool' in wallet_dict else 0
        sigs_required = wallet_dict['sigs_required'] if 'sigs_required' in wallet_dict else 1
        pending_psbts = wallet_dict['pending_psbts'] if 'pending_psbts' in wallet_dict else {}
        fullpath = wallet_dict['fullpath'] if 'fullpath' in wallet_dict else default_fullpath

        try:
            address_type = wallet_dict['address_type']
            recv_descriptor = wallet_dict['recv_descriptor']
            change_descriptor = wallet_dict['change_descriptor']

            # Part of migration from old to new format
            if 'keys' in wallet_dict:
                keys = [Key.from_json(key_dict) for key_dict in wallet_dict['keys']]
            else:
                keys = [Key.from_json(wallet_dict['key'])]
            if 'devices' in wallet_dict:
                devices = wallet_dict['devices']
            else:
                devices = [wallet_dict['device']]
        except:
            Exception('Could not construct a Wallet object from the data provided.')

        return cls(
            name,
            alias,
            description,
            address_type,
            address,
            address_index,
            change_address,
            change_index,
            keypool,
            change_keypool,
            recv_descriptor,
            change_descriptor,
            keys,
            devices,
            sigs_required,
            pending_psbts,
            fullpath,
            device_manager,
            manager
        )

    def getdata(self):
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
        # TODO: Should do the same for the non change address (?)
        # check if address was used already
        value_on_address = self.cli.getreceivedbyaddress(self.change_address, 0)
        # if not - just return
        if value_on_address > 0:
            self.change_index += 1
            self.getnewaddress(change=True)

    @property
    def json(self):
        return {
            "name": self.name,
            "alias": self.alias,
            "description": self.description,
            "address_type": self.address_type,
            "address": self.address,
            "address_index": self.address_index,
            "change_address": self.change_address,
            "change_index": self.change_index,
            "keypool": self.keypool,
            "change_keypool": self.change_keypool,
            "recv_descriptor": self.recv_descriptor,
            "change_descriptor": self.change_descriptor,
            "keys": [key.json for key in self.keys],
            "devices": [device.alias for device in self.devices],
            "sigs_required": self.sigs_required,
            "pending_psbts": self.pending_psbts,
            "fullpath": self.fullpath,
        }

    def save_to_file(self):
        with open(self.fullpath, "w+") as f:
            f.write(json.dumps(self.json, indent=4))
        self.manager.update()

    def _uses_device_type(self, type_list):
        for device in self.devices:
            if device.device_type in type_list:
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
        return len(self.keys) > 1

    @property
    def locked_amount(self):
        amount = 0
        for psbt in self.pending_psbts:
            amount += sum([utxo["witness_utxo"]["amount"] for utxo in self.pending_psbts[psbt]["inputs"]])
        return amount

    def delete_pending_psbt(self, txid):
        try:
            self.cli.lockunspent(True, self.pending_psbts[txid]["tx"]["vin"])
        except:
            # UTXO was spent
            pass
        del self.pending_psbts[txid]
        self.save_to_file()

    def update_pending_psbt(self, psbt, txid, raw, device_name):
        if txid in self.pending_psbts:
            self.pending_psbts[txid]["sigs_count"] += 1
            self.pending_psbts[txid]["base64"] = psbt
            if device_name:
                if "devices_signed" not in self.pending_psbts[txid]:
                    self.pending_psbts[txid]["devices_signed"] = []
                self.pending_psbts[txid]["devices_signed"].append(device_name)
            if "hex" in raw:
                self.pending_psbts[txid]["raw"] = raw["hex"]
            self.save_to_file()

    def save_pending_psbt(self, psbt):
        self.pending_psbts[psbt["tx"]["txid"]] = psbt
        self.cli.lockunspent(False, psbt["tx"]["vin"])
        self.save_to_file()

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
        if change:
            self.change_index += 1
            index = self.change_index
        else:
            self.address_index += 1
            index = self.address_index
        address = self.get_address(index, change=change)
        self.setlabel(address, "{} #{}".format(label, index))
        if change:
            self.change_address = address
        else:
            self.address = address
        self.save_to_file()
        return address

    def get_address(self, index, change=False):
        pool = self.change_keypool if change else self.keypool
        if pool < index + WALLET_CHUNK:
            self.keypoolrefill(pool, index + WALLET_CHUNK, change=change)
        desc = self.change_descriptor if change else self.recv_descriptor
        return self.cli.deriveaddresses(desc, [index, index+1])[0]

    @property
    def balance(self):
        try:
            balance = self.cli.getbalances()["watchonly"]
        except:
            balance = { "trusted": 0, "untrusted_pending": 0 }
        return balance

    def keypoolrefill(self, start, end=None, change=False):
        if end is None:
            end = start + WALLET_CHUNK
        desc = self.recv_descriptor if not change else self.change_descriptor
        args = [
            {
                "desc": desc,
                "internal": change, 
                "range": [start, end], 
                "timestamp": "now", 
                "keypool": True, 
                "watchonly": True
            }
        ]
        self.cli.importmulti(args, {"rescan": False}, timeout=120)
        if change:
            self.change_keypool = end
        else:
            self.keypool = end
        self.save_to_file()
        return end
    
    def tx_on_address(self, address):
        txlist = [tx for tx in self.transactions if tx["address"] == address]
        return len(txlist)

    def balance_on_address(self, address):
        balancelist = [utxo["amount"] for utxo in self.utxo if utxo["address"] == address]
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
        return self.tx_on_address(self.address)

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

    def setlabel(self, address, label):
        self.cli.setlabel(address, label)

    def getlabel(self, address):
        address_info = self.cli.getaddressinfo(address)
        # Bitcoin Core version 0.20.0 has replaced the `label` field with `labels`, an array currently limited to a single item.
        label = address_info["labels"][0] if "labels" in address_info and (isinstance(address_info["labels"], list) and len(address_info["labels"]) > 0) else address
        if label == "":
            label = address
        return address_info["label"] if "label" in address_info and address_info["label"] != "" else label
    
    def get_address_name(self, address, addr_idx):
        address_info = self.cli.getaddressinfo(address)
        if ("label" not in address_info or address_info["label"] == "") and addr_idx > -1:
            self.setlabel(address, "Address #{}".format(addr_idx))
            address_info["label"] = "Address #{}".format(addr_idx)
        return self.getlabel(address)

    @property
    def fullbalance(self):
        return self.balance["trusted"] + self.balance["untrusted_pending"]

    @property
    def available_balance(self):
        locked_utxo = self.cli.listlockunspent()
        balance = self.balance
        for tx in locked_utxo:
            tx_data = self.cli.gettransaction(tx["txid"])
            raw_tx = self.cli.decoderawtransaction(tx_data["hex"])
            if "confirmations" not in tx_data or tx_data["confirmations"] == 0:
                balance["untrusted_pending"] -= raw_tx["vout"][tx["vout"]]["value"]
            else:
                balance["trusted"] -= raw_tx["vout"][tx["vout"]]["value"]
        return balance

    @property
    def full_available_balance(self):
        balance = self.available_balance
        return balance["trusted"] + balance["untrusted_pending"]

    # NOTE: Only needed for QR (should be moved)
    @property
    def qr_descriptor(self):
        return self.recv_descriptor.split("#")[0].replace("/0/*", "")

    # NOTE: Only needed for QR (should be moved)
    @property
    def fingerprint(self):
        """ Unique fingerprint of the wallet - first 4 bytes of hash160 of its descriptor """
        h256 = hashlib.sha256(self.qr_descriptor.encode()).digest()
        h160 = hashlib.new('ripemd160', h256).digest()
        return h160[:4]

    @property
    def addresses(self):
        return [self.get_address(idx) for idx in range(0, self.address_index + 1)]

    @property
    def active_addresses(self):
        return list(dict.fromkeys(self.addresses + self.utxo_addresses))
    
    @property
    def change_addresses(self):
        return [self.get_address(idx, change=True) for idx in range(0, self.change_index + 1)]

    @property
    def labels(self):
        return list(dict.fromkeys([self.getlabel(addr) for addr in self.active_addresses]))

    def createpsbt(self, address:str, amount:float, subtract:bool=False, fee_rate:float=0.0, fee_unit="SAT_B", selected_coins=[]):
        """
            fee_rate: in sat/B or BTC/kB. Default (None) bitcoin core sets feeRate automatically.
        """
        if self.full_available_balance < amount:
            raise SpecterError('The wallet does not have sufficient funds to make the transaction.')

        if fee_unit not in ["SAT_B", "BTC_KB"]:
            raise ValueError('Invalid bitcoin unit')

        extra_inputs = []
        if self.available_balance["trusted"] < amount:
            txlist = self.cli.listunspent(0, 0)
            b = amount - self.available_balance["trusted"]
            for tx in txlist:
                extra_inputs.append({"txid": tx["txid"], "vout": tx["vout"]})
                b -= tx["amount"]
                if b < 0:
                    break
        elif selected_coins != []:
            still_needed = amount
            for coin in selected_coins:
                coin_txid = coin.split(",")[0]
                coin_vout = int(coin.split(",")[1])
                coin_amount = float(coin.split(",")[2])
                extra_inputs.append({"txid": coin_txid, "vout": coin_vout})
                still_needed -= coin_amount
                if still_needed < 0:
                    break
            if still_needed > 0:
                raise SpecterError("Selected coins does not cover Full amount! Please select more coins!")

        # subtract fee from amount of this output:
        # currently only one address is supported, so either
        # empty array (subtract from change) or [0]
        subtract_arr = [0] if subtract else []

        options = {
            "includeWatching": True, 
            "changeAddress": self.change_address,
            "subtractFeeFromOutputs": subtract_arr
        }

        self.setlabel(self.change_address, "Change #{}".format(self.change_index))

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

        if self.uses_sdcard_device:
            psbt["sdcard"] = Device.create_sdcard_psbt(b64psbt, self.keys)

        if self.uses_qrcode_device:
            psbt["qrcode"] = Device.create_qrcode_psbt(b64psbt, self.fingerprint)

        psbt["amount"] = amount
        psbt["address"] = address
        psbt["time"] = time()
        psbt["sigs_count"] = 0
        self.save_pending_psbt(psbt)

        return psbt

    # TODO: Move to Coldcard class(?)
    def get_cc_file(self):
        CC_TYPES = {
        'legacy': 'BIP45',
        'p2sh-segwit': 'P2WSH-P2SH',
        'bech32': 'P2WSH'
        }
        # try to find at least one derivation
        # cc assume the same derivation for all keys :(
        derivation = None
        for k in self.keys:
            if k.derivation != '':
                derivation = k.derivation.replace("h","'")
                break
        if derivation is None:
            return None
        cc_file = """# Coldcard Multisig setup file (created on Specter Desktop)
#
Name: {}
Policy: {} of {}
Derivation: {}
Format: {}
""".format(self.name, self.sigs_required, 
            len(self.keys), derivation,
            CC_TYPES[self.address_type]
            )
        for k in self.keys:
            # cc assumes fingerprint is known
            fingerprint = k.fingerprint
            if fingerprint == '':
                fingerprint = get_xpub_fingerprint(k.xpub).hex()
            cc_file += "{}: {}\n".format(fingerprint.upper(), k.xpub)
        return cc_file
