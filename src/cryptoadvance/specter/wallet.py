import copy, hashlib, json, logging, os
import time
from hwilib.descriptor import AddChecksum
from .device import Device
from .key import Key
from .util.merkleblock import is_valid_merkle_proof
from .helpers import der_to_bytes, sort_descriptor, parse_utxo
from .util.base58 import decode_base58
from .util.descriptor import Descriptor
from .util.xpub import get_xpub_fingerprint
from .persistence import write_json_file
from hwilib.serializations import PSBT, CTransaction
from io import BytesIO
from .specter_error import SpecterError
import threading
import requests
from math import ceil

logger = logging.getLogger()


class Wallet:
    # if the wallet is old we import 300 addresses
    IMPORT_KEYPOOL = 300
    # a gap of 20 addresses is what many wallets do
    GAP_LIMIT = 20
    # minimal fee rate is slightly above 1 sat/vbyte
    # to avoid rounding errors
    MIN_FEE_RATE = 1.01

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
            raise Exception("A device used by this wallet could not have been found!")
        self.sigs_required = int(sigs_required)
        self.pending_psbts = pending_psbts
        self.fullpath = fullpath
        self.manager = manager
        self.rpc = self.manager.rpc.wallet(
            os.path.join(self.manager.rpc_path, self.alias)
        )
        self.last_block = last_block

        if address == "":
            self.getnewaddress()
        if change_address == "":
            self.getnewaddress(change=True)

        self.getdata()
        self.update()
        if old_format_detected or self.last_block != last_block:
            self.save_to_file()

    def update(self):
        self.get_balance()
        self.check_addresses()
        self.get_info()

    def check_unused(self):
        """Check current receive address is unused and get new if needed"""
        addr = self.address
        while self.rpc.getreceivedbyaddress(addr, 0) != 0:
            addr = self.getnewaddress()

    def check_addresses(self):
        """Checking the gap limit is still ok"""
        if self.last_block is None:
            obj = self.rpc.listsinceblock()
        else:
            # sometimes last_block is invalid, not sure why
            try:
                obj = self.rpc.listsinceblock(self.last_block)
            except:
                logger.error(f"Invalid block {self.last_block}")
                obj = self.rpc.listsinceblock()
        txs = obj["transactions"]
        last_block = obj["lastblock"]
        addresses = [tx["address"] for tx in txs]
        # remove duplicates
        addresses = list(dict.fromkeys(addresses))
        if len(addresses) > 0:
            # prepare rpc call
            calls = [("getaddressinfo", addr) for addr in addresses]
            # extract results
            res = [r["result"] for r in self.rpc.multi(calls)]
            # extract last two indexes of hdkeypath
            paths = [d["hdkeypath"].split("/")[-2:] for d in res if "hdkeypath" in d]
            # get change and recv addresses
            max_recv = max([int(p[1]) for p in paths if p[0] == "0"], default=-1)
            max_change = max([int(p[1]) for p in paths if p[0] == "1"], default=-1)
            # these calls will happen only if current addresses are used
            updated = False
            while max_recv >= self.address_index:
                self.getnewaddress(change=False, save=False)
                updated = True
            while max_change >= self.change_index:
                self.getnewaddress(change=True, save=False)
                updated = True
            # save only if needed
            if updated:
                self.save_to_file()
        self.last_block = last_block

    @staticmethod
    def parse_old_format(wallet_dict, device_manager):
        old_format_detected = False
        new_dict = {}
        new_dict.update(wallet_dict)
        if "key" in wallet_dict:
            new_dict["keys"] = [wallet_dict["key"]]
            del new_dict["key"]
            old_format_detected = True
        if "device" in wallet_dict:
            new_dict["devices"] = [wallet_dict["device"]]
            del new_dict["device"]
            old_format_detected = True
        devices = [
            device_manager.get_by_alias(device) for device in new_dict["devices"]
        ]
        if (
            len(new_dict["keys"]) > 1
            and "sortedmulti" not in new_dict["recv_descriptor"]
        ):
            new_dict["recv_descriptor"] = AddChecksum(
                new_dict["recv_descriptor"]
                .replace("multi", "sortedmulti")
                .split("#")[0]
            )
            old_format_detected = True
        if (
            len(new_dict["keys"]) > 1
            and "sortedmulti" not in new_dict["change_descriptor"]
        ):
            new_dict["change_descriptor"] = AddChecksum(
                new_dict["change_descriptor"]
                .replace("multi", "sortedmulti")
                .split("#")[0]
            )
            old_format_detected = True
        if None in devices:
            devices = [
                (
                    (device["name"] if isinstance(device, dict) else device)
                    if (device["name"] if isinstance(device, dict) else device)
                    in device_manager.devices
                    else None
                )
                for device in new_dict["devices"]
            ]
            if None in devices:
                raise Exception(
                    "A device used by this wallet could not have been found!"
                )
            else:
                new_dict["devices"] = [
                    device_manager.devices[device].alias for device in devices
                ]
            old_format_detected = True
        new_dict["old_format_detected"] = old_format_detected
        return new_dict

    @classmethod
    def from_json(
        cls, wallet_dict, device_manager, manager, default_alias="", default_fullpath=""
    ):
        name = wallet_dict.get("name", "")
        alias = wallet_dict.get("alias", default_alias)
        description = wallet_dict.get("description", "")
        address = wallet_dict.get("address", "")
        address_index = wallet_dict.get("address_index", 0)
        change_address = wallet_dict.get("change_address", "")
        change_index = wallet_dict.get("change_index", 0)
        keypool = wallet_dict.get("keypool", 0)
        change_keypool = wallet_dict.get("change_keypool", 0)
        sigs_required = wallet_dict.get("sigs_required", 1)
        pending_psbts = wallet_dict.get("pending_psbts", {})
        fullpath = wallet_dict.get("fullpath", default_fullpath)
        last_block = wallet_dict.get("last_block", None)

        wallet_dict = Wallet.parse_old_format(wallet_dict, device_manager)

        try:
            address_type = wallet_dict["address_type"]
            recv_descriptor = wallet_dict["recv_descriptor"]
            change_descriptor = wallet_dict["change_descriptor"]
            keys = [Key.from_json(key_dict) for key_dict in wallet_dict["keys"]]
            devices = wallet_dict["devices"]
        except:
            raise Exception(
                "Could not construct a Wallet object from the data provided."
            )

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
            old_format_detected=wallet_dict["old_format_detected"],
            last_block=last_block,
        )

    def get_info(self):
        try:
            self.info = self.rpc.getwalletinfo()
        except Exception:
            self.info = {}
        return self.info

    def check_utxo(self):
        try:
            self.utxo = parse_utxo(self, self.rpc.listunspent(0))
            self.utxo_labels_list = self.getlabels(
                utxo["address"] for utxo in self.utxo
            )
        except Exception:
            self.utxo = []
            self.utxo_labels_list = {}

    def getdata(self):
        self.check_utxo()
        self.get_info()
        # TODO: Should do the same for the non change address (?)
        # check if address was used already
        try:
            value_on_address = self.rpc.getreceivedbyaddress(self.change_address, 0)
        except:
            # Could happen if address not in wallet (wallet was imported)
            # try adding keypool
            logger.info(
                f"Didn't get transactions on address {self.change_address}. Refilling keypool."
            )
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
            "blockheight": self.blockheight,
            "labels": self.export_labels(),
        }

    def save_to_file(self):
        write_json_file(self.json, self.fullpath)
        self.manager.update()

    @property
    def is_multisig(self):
        return len(self.keys) > 1

    @property
    def locked_amount(self):
        amount = 0
        for psbt in self.pending_psbts:
            amount += sum(
                [
                    utxo["witness_utxo"]["amount"]
                    for utxo in self.pending_psbts[psbt]["inputs"]
                ]
            )
        return amount

    def delete_pending_psbt(self, txid):
        try:
            self.rpc.lockunspent(True, self.pending_psbts[txid]["tx"]["vin"])
        except:
            # UTXO was spent
            pass
        if txid in self.pending_psbts:
            del self.pending_psbts[txid]
            self.save_to_file()

    def update_pending_psbt(self, psbt, txid, raw):
        if txid in self.pending_psbts:
            self.pending_psbts[txid]["base64"] = psbt
            decodedpsbt = self.rpc.decodepsbt(psbt)
            signed_devices = self.get_signed_devices(decodedpsbt)
            self.pending_psbts[txid]["devices_signed"] = [
                dev.alias for dev in signed_devices
            ]
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
        self.rpc.lockunspent(False, psbt["tx"]["vin"])
        self.save_to_file()

    def txlist(self, idx, wallet_tx_batch=100, validate_merkle_proofs=False):
        try:
            rpc_txs = self.rpc.listtransactions(
                "*", wallet_tx_batch + 2, wallet_tx_batch * idx, True
            )  # get batch + 2 to make sure you have information about send
            rpc_txs.reverse()
            transactions = rpc_txs[:wallet_tx_batch]
        except:
            return []
        result = []
        blocks = {}
        for tx in transactions:
            if "confirmations" not in tx:
                tx["confirmations"] = 0
            if (
                len(
                    [
                        _tx
                        for _tx in rpc_txs
                        if (
                            _tx["txid"] == tx["txid"]
                            and _tx["address"] == tx["address"]
                        )
                    ]
                )
                > 1
            ):
                continue  # means the tx is duplicated (change), continue

            tx["validated_blockhash"] = ""  # default is assume unvalidated
            if (
                validate_merkle_proofs is True
                and tx["confirmations"] > 0
                and tx.get("blockhash")
            ):
                proof_hex = self.rpc.gettxoutproof([tx["txid"]], tx["blockhash"])
                logger.debug(
                    f"Attempting merkle proof validation of tx { tx['txid'] } in block { tx['blockhash'] }"
                )
                if is_valid_merkle_proof(
                    proof_hex=proof_hex,
                    target_tx_hex=tx["txid"],
                    target_block_hash_hex=tx["blockhash"],
                    target_merkle_root_hex=None,
                ):
                    # NOTE: this does NOT guarantee this blockhash is actually in the real Bitcoin blockchain!
                    # See merkletooltip.html for details
                    logger.debug(f"Merkle proof of { tx['txid'] } validation success")
                    tx["validated_blockhash"] = tx["blockhash"]
                else:
                    logger.warning(
                        f"Attempted merkle proof validation on {tx['txid']} but failed. This is likely a configuration error but perhaps your node is compromised! Details: {proof_hex}"
                    )

            result.append(tx)

        return result

    def gettransaction(self, txid):
        return self.rpc.gettransaction(txid)

    def rescanutxo(self, explorer=None):
        t = threading.Thread(target=self._rescan_utxo_thread, args=(explorer,))
        t.start()

    def export_labels(self):
        labels = self.rpc.listlabels()
        if "" in labels:
            labels.remove("")
        res = self.rpc.multi([("getaddressesbylabel", label) for label in labels])
        return {
            labels[i]: list(result["result"].keys()) for i, result in enumerate(res)
        }

    def import_labels(self, labels):
        # format:
        #   {
        #       'label1': ['address1', 'address2'],
        #       'label2': ['address3', 'address4']
        #   }
        #
        rpc_calls = [
            ("setlabel", address, label)
            for label, addresses in labels.items()
            for address in addresses
        ]
        if rpc_calls:
            self.rpc.multi(rpc_calls)

    def _rescan_utxo_thread(self, explorer=None):
        # rescan utxo is pretty fast,
        # so we can check large range of addresses
        # and adjust keypool accordingly
        args = [
            "start",
            [
                {"desc": self.recv_descriptor, "range": max(self.keypool, 1000)},
                {
                    "desc": self.change_descriptor,
                    "range": max(self.change_keypool, 1000),
                },
            ],
        ]
        unspents = self.rpc.scantxoutset(*args)["unspents"]
        # if keypool adjustments fails - not a big deal
        try:
            # check derivation indexes in found unspents (last 2 indexes in [brackets])
            derivations = [
                tx["desc"].split("[")[1].split("]")[0].split("/")[-2:]
                for tx in unspents
            ]
            # get max derivation for change and receive branches
            max_recv = max([-1] + [int(der[1]) for der in derivations if der[0] == "0"])
            max_change = max(
                [-1] + [int(der[1]) for der in derivations if der[0] == "1"]
            )

            updated = False
            if max_recv >= self.address_index:
                # skip to max_recv
                self.address_index = max_recv
                # get next
                self.getnewaddress(change=False, save=False)
                updated = True
            while max_change >= self.change_index:
                # skip to max_change
                self.change_index = max_change
                # get next
                self.getnewaddress(change=True, save=False)
                updated = True
            # save only if needed
            if updated:
                self.save_to_file()
        except Exception as e:
            logger.warning(f"Failed to get derivation path from utxo transaction: {e}")

        # keep working with unspents
        res = self.rpc.multi([("getblockhash", tx["height"]) for tx in unspents])
        block_hashes = [r["result"] for r in res]
        for i, tx in enumerate(unspents):
            tx["blockhash"] = block_hashes[i]
        res = self.rpc.multi(
            [("gettxoutproof", [tx["txid"]], tx["blockhash"]) for tx in unspents]
        )
        proofs = [r["result"] for r in res]
        for i, tx in enumerate(unspents):
            tx["proof"] = proofs[i]
        res = self.rpc.multi(
            [
                ("getrawtransaction", tx["txid"], False, tx["blockhash"])
                for tx in unspents
            ]
        )
        raws = [r["result"] for r in res]
        for i, tx in enumerate(unspents):
            tx["raw"] = raws[i]
        missing = [tx for tx in unspents if tx["raw"] is None]
        existing = [tx for tx in unspents if tx["raw"] is not None]
        self.rpc.multi(
            [("importprunedfunds", tx["raw"], tx["proof"]) for tx in existing]
        )
        # handle missing transactions now
        # if Tor is running, requests will be sent over Tor
        if explorer is not None:
            try:
                requests_session = requests.Session()
                requests_session.proxies["http"] = "socks5h://localhost:9050"
                requests_session.proxies["https"] = "socks5h://localhost:9050"
                requests_session.get(explorer)
            except Exception:
                requests_session = requests.Session()
            # make sure there is no trailing /
            explorer = explorer.rstrip("/")
            try:
                # get raw transactions
                raws = [
                    requests_session.get(f"{explorer}/api/tx/{tx['txid']}/hex").text
                    for tx in missing
                ]
                # get proofs
                proofs = [
                    requests_session.get(
                        f"{explorer}/api/tx/{tx['txid']}/merkleblock-proof"
                    ).text
                    for tx in missing
                ]
                # import funds
                self.rpc.multi(
                    [
                        ("importprunedfunds", raws[i], proofs[i])
                        for i in range(len(raws))
                    ]
                )
            except Exception as e:
                logger.warning(f"Failed to fetch data from block explorer: {e}")

    @property
    def rescan_progress(self):
        """Returns None if rescanblockchain is not launched,
        value between 0 and 1 otherwise
        """
        if "scanning" not in self.info or self.info["scanning"] == False:
            return None
        else:
            return self.info["scanning"]["progress"]

    @property
    def blockheight(self):
        txs = self.rpc.listtransactions("*", 100, 0, True)
        i = 0
        while len(txs) == 100:
            i += 1
            next_txs = self.rpc.listtransactions("*", 100, i * 100, True)
            if len(next_txs) > 0:
                txs = next_txs
            else:
                break
        current_blockheight = self.rpc.getblockcount()
        if len(txs) > 0 and "confirmations" in txs[0]:
            blockheight = (
                current_blockheight - txs[0]["confirmations"] - 101
            )  # To ensure coinbase transactions are indexed properly
            return (
                0 if blockheight < 0 else blockheight
            )  # To ensure regtest don't have negative blockheight
        return current_blockheight

    @property
    def account_map(self):
        return (
            '{ "label": "'
            + self.name.replace("'", "\\'")
            + '", "blockheight": '
            + str(self.blockheight)
            + ', "descriptor": "'
            + self.recv_descriptor.replace("/", "\\/")
            + '" }'
        )

    def getnewaddress(self, change=False, save=True):
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
        if save:
            self.save_to_file()
        return address

    def get_address(self, index, change=False, check_keypool=True):
        if check_keypool:
            pool = self.change_keypool if change else self.keypool
            if pool < index + self.GAP_LIMIT:
                self.keypoolrefill(pool, index + self.GAP_LIMIT, change=change)
        desc = self.change_descriptor if change else self.recv_descriptor
        if self.is_multisig:
            try:
                # first try with sortedmulti
                addr = self.rpc.deriveaddresses(desc, [index, index + 1])[0]
            except Exception:
                # if sortedmulti is not supported
                desc = sort_descriptor(self.rpc, desc, index=index, change=change)
                addr = self.rpc.deriveaddresses(desc)[0]
            return addr
        return self.rpc.deriveaddresses(desc, [index, index + 1])[0]

    def get_descriptor(self, index=None, change=False, address=None):
        """
        Returns address descriptor from index, change
        or from address belonging to the wallet.
        """
        if address is not None:
            return self.rpc.getaddressinfo(address).get("desc", "")
        if index is None:
            index = self.change_index if change else self.address_index
        desc = self.rpc.getaddressinfo(self.get_address(index, change)).get("desc", "")
        result = {"descriptor": desc, "xpubs_descriptor": None}
        if self.is_multisig:
            if address is not None:
                d = self.rpc.getaddressinfo(address)["desc"]
                path = d.split("[")[1].split("]")[0].split("/")
                change = bool(int(path[-2]))
                index = int(path[-1])
            if index is None:
                index = self.change_index if change else self.address_index
            desc = self.change_descriptor if change else self.recv_descriptor
            try:
                result["xpubs_descriptor"] = sort_descriptor(
                    self.rpc, desc, index=index, change=change
                )
            except Exception:
                pass
        return result

    def get_electrum_watchonly(self):
        if len(self.keys) == 1:
            # Single-sig case:
            key = self.keys[0]
            return {
                "keystore": {
                    "derivation": key.derivation.replace("h", "'"),
                    "root_fingerprint": key.fingerprint,
                    "type": "bip32",
                    "xprv": None,
                    "xpub": key.original,
                },
                "wallet_type": "standard",
            }

        # Multisig case

        # Build lookup table to convert from xpub to slip132 encoded xpub (while maintaining sort order)
        LOOKUP_TABLE = {}
        for key in self.keys:
            LOOKUP_TABLE[key.xpub] = key

        desc = Descriptor.parse(
            desc=self.recv_descriptor,
            # assume testnet status is the same across all keys
            testnet=key.is_testnet,
        )
        slip132_keys = []
        for desc_key in desc.base_key:
            # Find corresponding wallet key
            slip132_keys.append(LOOKUP_TABLE[desc_key])

        to_return = {"wallet_type": "{}of{}".format(self.sigs_required, len(self.keys))}
        for cnt, slip132_key in enumerate(slip132_keys):
            to_return["x{}/".format(cnt + 1)] = {
                "derivation": slip132_key.derivation.replace("h", "'"),
                "root_fingerprint": slip132_key.fingerprint,
                "type": "bip32",
                "xprv": None,
                "xpub": slip132_key.original,
            }

        return to_return

    def get_balance(self):
        try:
            balance = self.rpc.getbalances()["watchonly"]
            # calculate available balance
            locked_utxo = self.rpc.listlockunspent()
            available = {}
            available.update(balance)
            for tx in locked_utxo:
                tx_data = self.rpc.gettransaction(tx["txid"])
                raw_tx = self.rpc.decoderawtransaction(tx_data["hex"])
                delta = raw_tx["vout"][tx["vout"]]["value"]
                if "confirmations" not in tx_data or tx_data["confirmations"] == 0:
                    available["untrusted_pending"] -= delta
                else:
                    available["trusted"] -= delta
                    available["trusted"] = round(available["trusted"], 8)
            balance["available"] = available
        except:
            balance = {
                "trusted": 0,
                "untrusted_pending": 0,
                "available": {"trusted": 0, "untrusted_pending": 0},
            }
            available["untrusted_pending"] = round(available["untrusted_pending"], 8)
        self.balance = balance
        return self.balance

    def keypoolrefill(self, start, end=None, change=False):
        if end is None:
            end = start + self.GAP_LIMIT
        desc = self.recv_descriptor if not change else self.change_descriptor
        args = [
            {
                "desc": desc,
                "internal": change,
                "range": [start, end],
                "timestamp": "now",
                "keypool": True,
                "watchonly": True,
            }
        ]
        if not self.is_multisig:
            r = self.rpc.importmulti(args, {"rescan": False})
        # bip67 requires sorted public keys for multisig addresses
        else:
            # try if sortedmulti is supported
            r = self.rpc.importmulti(args, {"rescan": False})
            # doesn't raise, but instead returns "success": False
            if not r[0]["success"]:
                # first import normal multi
                # remove checksum
                desc = desc.split("#")[0]
                # switch to multi
                desc = desc.replace("sortedmulti", "multi")
                # add checksum
                desc = AddChecksum(desc)
                # update descriptor
                args[0]["desc"] = desc
                r = self.rpc.importmulti(args, {"rescan": False})
                # make a batch of single addresses to import
                arg = args[0]
                # remove range key
                arg.pop("range")
                batch = []
                for i in range(start, end):
                    sorted_desc = sort_descriptor(
                        self.rpc, desc, index=i, change=change
                    )
                    # create fresh object
                    obj = {}
                    obj.update(arg)
                    obj.update({"desc": sorted_desc})
                    batch.append(obj)
                r = self.rpc.importmulti(batch, {"rescan": False})
        if change:
            self.change_keypool = end
        else:
            self.keypool = end
        self.rpc.multi(
            [
                (
                    "setlabel",
                    self.get_address(i, change=change, check_keypool=False),
                    "{} #{}".format("Change" if change else "Address", i),
                )
                for i in range(start, end)
            ]
        )
        self.save_to_file()
        return end

    def utxo_on_address(self, address):
        utxo = [tx for tx in self.utxo if tx["address"] == address]
        return len(utxo)

    def balance_on_address(self, address):
        balancelist = [
            utxo["amount"] for utxo in self.utxo if utxo["address"] == address
        ]
        return sum(balancelist)

    def utxo_on_label(self, label):
        return len(
            [tx for tx in self.utxo if self.utxo_labels_list[tx["address"]] == label]
        )

    def balance_on_label(self, label):
        return sum(
            utxo["amount"]
            for utxo in self.utxo
            if self.utxo_labels_list[utxo["address"]] == label
        )

    def addresses_on_label(self, label):
        return list(
            dict.fromkeys(
                [
                    address
                    for address in (self.addresses + self.change_addresses)
                    if self.getlabel(address) == label
                ]
            )
        )

    def utxo_addresses(self, idx=0, wallet_utxo_batch=100):
        return list(
            dict.fromkeys(
                list(
                    reversed(
                        [
                            utxo["address"]
                            for utxo in sorted(self.utxo, key=lambda utxo: utxo["time"])
                        ]
                    )
                )[(wallet_utxo_batch * idx) : (wallet_utxo_batch * (idx + 1))]
            )
        )

    def utxo_labels(self, idx=0, wallet_utxo_batch=100):
        return list(
            dict.fromkeys(
                list(
                    reversed(
                        [
                            self.utxo_labels_list[utxo["address"]]
                            for utxo in sorted(self.utxo, key=lambda utxo: utxo["time"])
                        ]
                    )
                )[(wallet_utxo_batch * idx) : (wallet_utxo_batch * (idx + 1))]
            )
        )

    def setlabel(self, address, label):
        self.rpc.setlabel(address, label)

    def getlabel(self, address):
        labels = self.getlabels([address])
        if address in labels:
            return labels[address]
        else:
            return address

    def getlabels(self, addresses):
        labels = {}
        addresses_infos = self.rpc.multi(
            [("getaddressinfo", address) for address in addresses]
        )
        for address_info in addresses_infos:
            address_info = address_info["result"]
            # Bitcoin Core version 0.20.0 has replaced the `label` field with `labels`, an array currently limited to a single item.
            label = (
                address_info["labels"][0]
                if (
                    "labels" in address_info
                    and (
                        isinstance(address_info["labels"], list)
                        and len(address_info["labels"]) > 0
                    )
                    and "label" not in address_info
                )
                else address_info["address"]
            )
            if label == "":
                label = address_info["address"]
            labels[address_info["address"]] = (
                address_info["label"]
                if "label" in address_info and address_info["label"] != ""
                else label
            )
        return labels

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
        return self.balance["available"]

    @property
    def full_available_balance(self):
        balance = self.available_balance
        return balance["trusted"] + balance["untrusted_pending"]

    @property
    def addresses(self):
        return [self.get_address(idx) for idx in range(0, self.address_index + 1)]

    @property
    def change_addresses(self):
        return [
            self.get_address(idx, change=True)
            for idx in range(0, self.change_index + 1)
        ]

    @property
    def wallet_addresses(self):
        return self.addresses + self.change_addresses

    def createpsbt(
        self,
        addresses: [str],
        amounts: [float],
        subtract: bool = False,
        subtract_from: int = 0,
        fee_rate: float = 1.0,
        selected_coins=[],
        readonly=False,
    ):
        """
        fee_rate: in sat/B or BTC/kB. If set to 0 Bitcoin Core sets feeRate automatically.
        """
        if fee_rate > 0 and fee_rate < self.MIN_FEE_RATE:
            fee_rate = self.MIN_FEE_RATE

        if self.full_available_balance < sum(amounts):
            raise SpecterError(
                "The wallet does not have sufficient funds to make the transaction."
            )

        extra_inputs = []
        if self.available_balance["trusted"] <= sum(amounts):
            txlist = self.rpc.listunspent(0, 0)
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
                raise SpecterError(
                    "Selected coins does not cover Full amount! Please select more coins!"
                )

        # subtract fee from amount of this output:
        # currently only one address is supported, so either
        # empty array (subtract from change) or [0]
        subtract_arr = [subtract_from] if subtract else []

        options = {
            "includeWatching": True,
            "changeAddress": self.change_address,
            "subtractFeeFromOutputs": subtract_arr,
        }

        self.setlabel(self.change_address, "Change #{}".format(self.change_index))

        if fee_rate > 0:
            # bitcoin core needs us to convert sat/B to BTC/kB
            options["feeRate"] = round((fee_rate * 1000) / 1e8, 8)

        # don't reuse change addresses - use getrawchangeaddress instead
        r = self.rpc.walletcreatefundedpsbt(
            extra_inputs,  # inputs
            [{addresses[i]: amounts[i]} for i in range(len(addresses))],  # output
            0,  # locktime
            options,  # options
            True,  # bip32-der
        )

        b64psbt = r["psbt"]
        psbt = self.rpc.decodepsbt(b64psbt)
        if fee_rate > 0.0:
            psbt_fees_sats = int(psbt["fee"] * 1e8)
            # estimate final size: add weight of inputs
            tx_full_size = ceil(
                psbt["tx"]["vsize"] + len(psbt["inputs"]) * self.weight_per_input / 4
            )
            adjusted_fee_rate = (
                fee_rate
                * (fee_rate / (psbt_fees_sats / psbt["tx"]["vsize"]))
                * (tx_full_size / psbt["tx"]["vsize"])
            )
            options["feeRate"] = "%.8f" % round((adjusted_fee_rate * 1000) / 1e8, 8)
            r = self.rpc.walletcreatefundedpsbt(
                extra_inputs,  # inputs
                [{addresses[i]: amounts[i]} for i in range(len(addresses))],  # output
                0,  # locktime
                options,  # options
                True,  # bip32-der
            )

            b64psbt = r["psbt"]
            psbt = self.rpc.decodepsbt(b64psbt)
            psbt["fee_rate"] = options["feeRate"]
        # estimate full size
        tx_full_size = ceil(
            psbt["tx"]["vsize"] + len(psbt["inputs"]) * self.weight_per_input / 4
        )
        psbt["tx_full_size"] = tx_full_size

        psbt["base64"] = b64psbt
        psbt["amount"] = amounts
        psbt["address"] = addresses
        psbt["time"] = time.time()
        psbt["sigs_count"] = 0
        if not readonly:
            self.save_pending_psbt(psbt)

        return psbt

    def fill_psbt(self, b64psbt, non_witness: bool = True, xpubs: bool = True):
        psbt = PSBT()
        psbt.deserialize(b64psbt)
        if non_witness:
            for i, inp in enumerate(psbt.tx.vin):
                txid = inp.prevout.hash.to_bytes(32, "big").hex()
                try:
                    res = self.rpc.gettransaction(txid)
                except:
                    raise SpecterError("Can't find previous transaction in the wallet.")
                stream = BytesIO(bytes.fromhex(res["hex"]))
                prevtx = CTransaction()
                prevtx.deserialize(stream)
                psbt.inputs[i].non_witness_utxo = prevtx
        else:
            # remove non_witness_utxo if we don't want them
            for inp in psbt.inputs:
                if inp.witness_utxo is not None:
                    inp.non_witness_utxo = None

        if xpubs:
            # for multisig add xpub fields
            if len(self.keys) > 1:
                for k in self.keys:
                    key = b"\x01" + decode_base58(k.xpub)
                    if k.fingerprint != "":
                        fingerprint = bytes.fromhex(k.fingerprint)
                    else:
                        fingerprint = get_xpub_fingerprint(k.xpub)
                    if k.derivation != "":
                        der = der_to_bytes(k.derivation)
                    else:
                        der = b""
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
        psbt = self.rpc.decodepsbt(b64psbt)
        psbt["base64"] = b64psbt
        amount = []
        address = []
        # get output address and amount
        for out in psbt["tx"]["vout"]:
            if (
                "addresses" not in out["scriptPubKey"]
                or len(out["scriptPubKey"]["addresses"]) == 0
            ):
                # TODO: we need to handle it somehow differently
                raise SpecterError("Sending to raw scripts is not supported yet")
            addr = out["scriptPubKey"]["addresses"][0]
            info = self.rpc.getaddressinfo(addr)
            # check if it's a change
            if info["iswatchonly"] or info["ismine"]:
                continue
            address.append(addr)
            amount.append(out["value"])
        # detect signatures
        signed_devices = self.get_signed_devices(psbt)
        psbt["devices_signed"] = [dev.alias for dev in signed_devices]
        psbt["amount"] = amount
        psbt["address"] = address
        psbt["time"] = time.time()
        psbt["sigs_count"] = len(signed_devices)
        raw = self.rpc.finalizepsbt(b64psbt)
        if "hex" in raw:
            psbt["raw"] = raw["hex"]
        self.save_pending_psbt(psbt)
        return psbt

    @property
    def weight_per_input(self):
        """Calculates the weight of a signed input"""
        if self.is_multisig:
            input_size = 3  # OP_M OP_N ... OP_CHECKMULTISIG
            # pubkeys
            input_size += 34 * len(self.keys)
            # signatures
            input_size += 75 * self.sigs_required

            if not self.recv_descriptor.startswith("wsh"):
                # P2SH scriptsig: 22 00 20 <32-byte-hash>
                input_size += 35 * 4
            return input_size
        # else: single-sig
        if self.recv_descriptor.startswith("wpkh"):
            # pubkey, signature
            return 75 + 34
        # pubkey, signature, 4* P2SH: 16 00 14 20-byte-hash
        return 75 + 34 + 23 * 4
