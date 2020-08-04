import copy, hashlib, json, logging, os
from time import time
from hwilib.descriptor import AddChecksum
from .device import Device
from .key import Key
from .helpers import decode_base58, der_to_bytes, get_xpub_fingerprint, sort_descriptor, fslock, parse_utxo
from hwilib.serializations import PSBT, CTransaction
from io import BytesIO
from .specter_error import SpecterError
import threading

# a gap of 20 addresses is what many wallets do
WALLET_CHUNK = 20
wallet_tx_batch = 100

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
        manager,
        old_format_detected=False,
        last_block=None,
    ):
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
        self.change_descriptor = change_descriptor
        self.keys = keys
        self.devices = [
            (
                device
                if isinstance(device, Device)
                else device_manager.get_by_alias(device)
            )
            for device in devices
        ]
        if None in self.devices:
            raise Exception(
                'A device used by this wallet could not have been found!'
            )
        self.sigs_required = sigs_required
        self.pending_psbts = pending_psbts
        self.fullpath = fullpath
        self.manager = manager
        self.cli = self.manager.cli.wallet(
            os.path.join(self.manager.cli_path, self.alias)
        )
        self.last_block = last_block

        if address == '':
            self.getnewaddress()
        if change_address == '':
            self.getnewaddress(change=True)

        self.getdata()
        self.update()
        if old_format_detected or self.last_block != last_block:
            self.save_to_file()

    def update(self):
        self.get_balance()
        self.check_addresses()
        self.get_info()

    def check_addresses(self):
        """Checking the gap limit is still ok"""
        if self.last_block is None:
            obj = self.cli.listsinceblock()
            txs = obj["transactions"]
            last_block = obj["lastblock"]
        else:
            obj = self.cli.listsinceblock(self.last_block)
            txs = obj["transactions"]
            last_block = obj["lastblock"]
        addresses = [tx["address"] for tx in txs]
        # remove duplicates
        addresses = list(dict.fromkeys(addresses))
        if len(addresses) > 0:
            # prepare rpc call
            calls = [("getaddressinfo",addr) for addr in addresses]
            # extract results
            res = [r["result"] for r in self.cli.multi(calls)]
            # extract last two indexes of hdkeypath
            paths = [d["hdkeypath"].split("/")[-2:] for d in res if "hdkeypath" in d]
            # get change and recv addresses
            max_recv = max([int(p[1]) for p in paths if p[0]=="0"], default=-1)
            max_change = max([int(p[1]) for p in paths if p[0]=="1"], default=-1)
            # these calls will happen only if current addresses are used
            while max_recv >= self.address_index:
                self.getnewaddress(change=False)
            while max_change >= self.change_index:
                self.getnewaddress(change=True)
        self.last_block = last_block

    @staticmethod
    def parse_old_format(wallet_dict, device_manager):
        old_format_detected = False
        new_dict = {}
        new_dict.update(wallet_dict)
        if 'key' in wallet_dict:
            new_dict['keys'] = [wallet_dict['key']]
            del new_dict['key']
            old_format_detected = True
        if 'device' in wallet_dict:
            new_dict['devices'] = [wallet_dict['device']]
            del new_dict['device']
            old_format_detected = True
        devices = [device_manager.get_by_alias(device) for device in new_dict['devices']]
        if len(new_dict['keys']) > 1 and 'sortedmulti' not in new_dict['recv_descriptor']:
            new_dict['recv_descriptor'] = AddChecksum(new_dict['recv_descriptor'].replace('multi', 'sortedmulti').split('#')[0])
            old_format_detected = True
        if len(new_dict['keys']) > 1 and 'sortedmulti' not in new_dict['change_descriptor']:
            new_dict['change_descriptor'] = AddChecksum(new_dict['change_descriptor'].replace('multi', 'sortedmulti').split('#')[0])
            old_format_detected = True
        if None in devices:
            devices = [((device['name'] if isinstance(device, dict) else device) if (device['name'] if isinstance(device, dict) else device) in device_manager.devices else None) for device in new_dict['devices']]
            if None in devices:
                raise Exception('A device used by this wallet could not have been found!')
            else:
                new_dict['devices'] = [device_manager.devices[device].alias for device in devices]
            old_format_detected = True
        new_dict['old_format_detected'] = old_format_detected
        return new_dict

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
        last_block = wallet_dict['last_block'] if 'last_block' in wallet_dict else None

        wallet_dict = Wallet.parse_old_format(wallet_dict, device_manager)

        try:
            address_type = wallet_dict['address_type']
            recv_descriptor = wallet_dict['recv_descriptor']
            change_descriptor = wallet_dict['change_descriptor']
            keys = [Key.from_json(key_dict) for key_dict in wallet_dict['keys']]
            devices = wallet_dict['devices']
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
            manager,
            old_format_detected=wallet_dict['old_format_detected'],
            last_block=last_block
        )

    def get_info(self):
        try:
            self.info = self.cli.getwalletinfo()
        except Exception:
            self.info = {}

    def getdata(self):
        try:
            self.utxo = parse_utxo(self, self.cli.listunspent(0))
        except Exception:
            self.utxo = []
        self.get_info()
        # TODO: Should do the same for the non change address (?)
        # check if address was used already
        try:
            value_on_address = self.cli.getreceivedbyaddress(
                self.change_address,
                0
            )
        except:
            # Could happen if address not in wallet (wallet was imported)
            # try adding keypool
            self.keypoolrefill(0, end=self.keypool, change=False)
            self.keypoolrefill(0, end=self.change_keypool, change=True)
            value_on_address = 0

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
            "last_block": self.last_block,
            "blockheight": self.blockheight
        }

    def save_to_file(self):
        with fslock:
            with open(self.fullpath, "w+") as f:
                f.write(json.dumps(self.json, indent=4))
        self.manager.update()

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
        if txid in self.pending_psbts:
            del self.pending_psbts[txid]
            self.save_to_file()

    def update_pending_psbt(self, psbt, txid, raw):
        if txid in self.pending_psbts:
            self.pending_psbts[txid]["base64"] = psbt
            decodedpsbt = self.cli.decodepsbt(psbt)
            signed_devices = self.get_signed_devices(decodedpsbt)
            self.pending_psbts[txid]["devices_signed"] = [dev.name for dev in signed_devices]
            if "hex" in raw:
                self.pending_psbts[txid]["sigs_count"] = self.sigs_required
                self.pending_psbts[txid]["raw"] = raw["hex"]
            else:
                self.pending_psbts[txid]["sigs_count"] = len(signed_devices)
            self.save_to_file()
            return self.pending_psbts[txid]
        else:
            raise SpecterError("Can't find pending PSBT with this txid")

    def save_pending_psbt(self, psbt):
        self.pending_psbts[psbt["tx"]["txid"]] = psbt
        self.cli.lockunspent(False, psbt["tx"]["vin"])
        self.save_to_file()

    def txlist(self, idx, wallet_tx_batch=100):
        try:
            cli_txs = self.cli.listtransactions("*", wallet_tx_batch + 2, wallet_tx_batch * idx, True) # get batch + 2 to make sure you have information about send
            cli_txs.reverse()
            transactions = cli_txs[:wallet_tx_batch]
        except:
            return []
        txids = []
        result = []
        for tx in transactions:
            if 'confirmations' not in tx:
                tx['confirmations'] = 0
            if len([_tx for _tx in cli_txs if (_tx['txid'] == tx['txid'] and _tx['address'] == tx['address'])]) > 1:
                continue # means the tx is duplicated (change), continue

            txids.append(tx["txid"])
            result.append(tx)

        return result

    @property
    def rescan_progress(self):
        """Returns None if rescanblockchain is not launched,
           value between 0 and 1 otherwise
        """
        if self.info is {} or "scanning" not in self.info or self.info["scanning"] == False:
            return None
        else:
            return self.info["scanning"]["progress"]

    @property
    def blockheight(self):
        txs = self.cli.listtransactions("*", 100, 0, True)
        i = 0
        while (len(txs) == 100):
            i += 1
            next_txs = self.cli.listtransactions("*", 100, i * 100, True)
            if (len(next_txs) > 0):
                txs = next_txs
            else:
                break
        current_blockheight = self.cli.getblockcount()
        if len(txs) > 0 and 'confirmations' in txs[0]:
            blockheight = current_blockheight - txs[0]['confirmations'] - 101 # To ensure coinbase transactions are indexed properly
            return 0 if blockheight < 0 else blockheight # To ensure regtest don't have negative blockheight
        return current_blockheight

    @property
    def account_map(self):
        return '{ "label": "' + self.name + '", "blockheight": ' + str(self.blockheight) + ', "descriptor": "' + self.recv_descriptor.replace("/", "\\/") + '" }'

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
        if self.is_multisig:
            try:
                # first try with sortedmulti
                addr = self.cli.deriveaddresses(desc, [index, index+1])[0]
            except:
                # if sortedmulti is not supported
                desc = sort_descriptor(self.cli, desc, index=index, change=change)
                addr = self.cli.deriveaddresses(desc)[0]
            return addr
        return self.cli.deriveaddresses(desc, [index, index + 1])[0]

    def get_balance(self):
        try:
            self.balance = self.cli.getbalances()["watchonly"]
        except:
            self.balance = { "trusted": 0, "untrusted_pending": 0 }
        return self.balance

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
        if not self.is_multisig:
            r = self.cli.importmulti(args, {"rescan": False})
        # bip67 requires sorted public keys for multisig addresses
        else:
            # try if sortedmulti is supported
            r = self.cli.importmulti(args, {"rescan": False})
            # doesn't raise, but instead returns "success": False
            if not r[0]['success']:
                # first import normal multi
                # remove checksum
                desc = desc.split("#")[0]
                # switch to multi
                desc = desc.replace("sortedmulti", "multi")
                # add checksum
                desc = AddChecksum(desc)
                # update descriptor
                args[0]["desc"] = desc
                r = self.cli.importmulti(args, {"rescan": False})
                # make a batch of single addresses to import
                arg = args[0]
                # remove range key
                arg.pop("range")
                batch = []
                for i in range(start, end):
                    sorted_desc = sort_descriptor(
                        self.cli,
                        desc,
                        index=i,
                        change=change
                    )
                    # create fresh object
                    obj = {}
                    obj.update(arg)
                    obj.update({"desc": sorted_desc})
                    batch.append(obj)
                r = self.cli.importmulti(batch, {"rescan": False})
        if change:
            self.change_keypool = end
        else:
            self.keypool = end
        self.save_to_file()
        return end

    def utxo_on_address(self, address):
        utxo = [tx for tx in self.utxo if tx["address"] == address]
        return len(utxo)

    def balance_on_address(self, address):
        balancelist = [utxo["amount"] for utxo in self.utxo if utxo["address"] == address]
        return sum(balancelist)

    def utxo_on_label(self, label):
        utxo = [tx for tx in self.utxo if self.getlabel(tx["address"]) == label]
        return len(utxo)

    def balance_on_label(self, label):
        balancelist = [utxo["amount"] for utxo in self.utxo if self.getlabel(utxo["address"]) == label]
        return sum(balancelist)

    def addresses_on_label(self, label):
        return list(dict.fromkeys(
            [address for address in (self.addresses + self.change_addresses) if self.getlabel(address) == label]
        ))

    @property
    def is_current_address_used(self):
        return self.balance_on_address(self.address) > 0

    @property
    def utxo_addresses(self):
        return list(dict.fromkeys([utxo["address"] for utxo in sorted(self.utxo, key = lambda utxo: utxo["time"])]))

    @property
    def utxo_labels(self):
        return list(dict.fromkeys([self.getlabel(utxo["address"]) for utxo in sorted(self.utxo, key = lambda utxo: utxo["time"])]))

    def setlabel(self, address, label):
        self.cli.setlabel(address, label)

    def getlabel(self, address):
        address_info = self.cli.getaddressinfo(address)
        # Bitcoin Core version 0.20.0 has replaced the `label` field with `labels`, an array currently limited to a single item.
        label = address_info["labels"][0] if (
            "labels" in address_info 
            and (isinstance(address_info["labels"], list) 
                and len(address_info["labels"]) > 0) 
            and "label" not in address_info) else address
        if label == "":
            label = address
        return address_info["label"] if "label" in address_info and address_info["label"] != "" else label
    
    def get_address_name(self, address, addr_idx):
        if self.getlabel(address) == address and addr_idx > -1:
            self.setlabel(address, "Address #{}".format(addr_idx))
        return self.getlabel(address)

    @property
    def fullbalance(self):
        balance = self.balance
        return balance["trusted"] + balance["untrusted_pending"]

    @property
    def available_balance(self):
        locked_utxo = self.cli.listlockunspent()
        # copy
        balance = {}
        balance.update(self.balance)
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
    def wallet_addresses(self):
        return self.addresses + self.change_addresses

    @property
    def labels(self):
        return list(dict.fromkeys([self.getlabel(addr) for addr in self.active_addresses]))

    def createpsbt(self, addresses:[str], amounts:[float], subtract:bool=False, fee_rate:float=0.0, fee_unit="SAT_B", selected_coins=[]):
        """
            fee_rate: in sat/B or BTC/kB. Default (None) bitcoin core sets feeRate automatically.
        """

        if self.full_available_balance < sum(amounts):
            raise SpecterError('The wallet does not have sufficient funds to make the transaction.')

        if fee_unit not in ["SAT_B", "BTC_KB"]:
            raise ValueError('Invalid bitcoin unit')

        extra_inputs = []
        if self.available_balance["trusted"] < sum(amounts):
            txlist = self.cli.listunspent(0, 0)
            b = sum(amounts) - self.available_balance["trusted"]
            for tx in txlist:
                extra_inputs.append({"txid": tx["txid"], "vout": tx["vout"]})
                b -= tx["amount"]
                if b < 0:
                    break
        elif selected_coins != []:
            still_needed = sum(amounts)
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
            [{addresses[i]: amounts[i]} for i in range(len(addresses))],    # output
            0,                      # locktime
            options,                # options
            True                    # replaceable
        )

        b64psbt = r["psbt"]
        psbt = self.cli.decodepsbt(b64psbt)
        psbt['base64'] = b64psbt
        psbt["amount"] = amounts
        psbt["address"] = addresses
        psbt["time"] = time()
        psbt["sigs_count"] = 0
        self.save_pending_psbt(psbt)

        return psbt

    def fill_psbt(self, b64psbt, non_witness:bool=True, xpubs:bool=True):
        psbt = PSBT()
        psbt.deserialize(b64psbt)
        if non_witness:
            for i, inp in enumerate(psbt.tx.vin):
                txid = inp.prevout.hash.to_bytes(32,'big').hex()
                try:
                    res = self.cli.gettransaction(txid)
                except:
                    raise SpecterError("Can't find previous transaction in the wallet.")
                stream = BytesIO(bytes.fromhex(res["hex"]))
                prevtx = CTransaction()
                prevtx.deserialize(stream)
                psbt.inputs[i].non_witness_utxo = prevtx
        if xpubs:
            # for multisig add xpub fields
            if len(self.keys) > 1:
                for k in self.keys:
                    key = b'\x01' + decode_base58(k.xpub)
                    if k.fingerprint != '':
                        fingerprint = bytes.fromhex(k.fingerprint)
                    else:
                        fingerprint = get_xpub_fingerprint(k.xpub)
                    if k.derivation != '':
                        der = der_to_bytes(k.derivation)
                    else:
                        der = b''
                    value = fingerprint + der
                    psbt.unknown[key] = value
        return psbt.serialize()

    def get_signed_devices(self, decodedpsbt):
        signed_devices = []
        # check who already signed
        for i, key in enumerate(self.keys):
            sigs = 0
            for inp in decodedpsbt["inputs"]:
                if "bip32_derivs" not in inp:
                    # how are we going to sign it???
                    break
                if "partial_signatures" not in inp:
                    # nothing to update - no signatures for this input
                    break
                for der in inp["bip32_derivs"]:
                    if der["master_fingerprint"] == key.fingerprint:
                        if der["pubkey"] in inp["partial_signatures"]:
                            sigs += 1
            # ok we have all signatures from this key (device)
            if sigs >= len(decodedpsbt["inputs"]):
                # assuming that order of self.devices and self.keys is the same
                signed_devices.append(self.devices[i])
        return signed_devices

    def importpsbt(self, b64psbt):
        # TODO: check maybe some of the inputs are already locked
        psbt = self.cli.decodepsbt(b64psbt)
        psbt['base64'] = b64psbt
        amount = 0
        address = None
        # get output address and amount
        for out in psbt["tx"]["vout"]:
            if "addresses" not in out["scriptPubKey"] or len(out["scriptPubKey"]["addresses"]) == 0:
                # TODO: we need to handle it somehow differently
                raise SpecterError("Sending to raw scripts is not supported yet")
            addr = out["scriptPubKey"]["addresses"][0]
            info = self.cli.getaddressinfo(addr)
            # check if it's a change
            if info["iswatchonly"] or info["ismine"]:
                continue
            # if not - this is out address
            # ups, more than one sending address
            if address is not None:
                # TODO: we need to have multiple address support 
                raise SpecterError("Sending to multiple addresses is not supported yet")
            address = addr
            amount += out["value"]
        # detect signatures
        signed_devices = self.get_signed_devices(psbt)
        psbt["devices_signed"] = [dev.name for dev in signed_devices]
        psbt["amount"] = amount
        psbt["address"] = address
        psbt["time"] = time()
        psbt["sigs_count"] = len(signed_devices)
        raw = self.cli.finalizepsbt(b64psbt)
        if "hex" in raw:
            psbt["raw"] = raw["hex"]
        self.save_pending_psbt(psbt)
        return psbt
