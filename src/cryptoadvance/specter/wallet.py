import copy, hashlib, json, logging, os, re
import time
from collections import OrderedDict
from .device import Device
from .key import Key
from .util.merkleblock import is_valid_merkle_proof
from .helpers import der_to_bytes, get_address_from_dict
from embit import base58, bip32
from .util.descriptor import Descriptor, sort_descriptor, AddChecksum
from embit.liquid.descriptor import LDescriptor
from embit.descriptor.checksum import add_checksum
from embit.liquid.networks import get_network
from embit.psbt import PSBT, DerivationPath
from embit.transaction import Transaction

from .util.xpub import get_xpub_fingerprint
from .util.tx import decoderawtransaction
from .persistence import write_json_file, delete_file
from io import BytesIO
from .specter_error import SpecterError
import threading
import requests
from math import ceil
from .addresslist import AddressList
from .txlist import TxList

logger = logging.getLogger(__name__)
LISTTRANSACTIONS_BATCH_SIZE = 1000

purposes = OrderedDict(
    {
        None: "General",
        "wpkh": "Single (Segwit)",
        "sh-wpkh": "Single (Nested)",
        "pkh": "Single (Legacy)",
        "wsh": "Multisig (Segwit)",
        "sh-wsh": "Multisig (Nested)",
        "sh": "Multisig (Legacy)",
    }
)

addrtypes = {
    "pkh": "legacy",
    "sh-wpkh": "p2sh-segwit",
    "wpkh": "bech32",
    "sh": "legacy",
    "sh-wsh": "p2sh-segwit",
    "wsh": "bech32",
}


class Wallet:
    # if the wallet is old we import 300 addresses
    IMPORT_KEYPOOL = 300
    # a gap of 20 addresses is what many wallets do (not used with descriptor wallets)
    GAP_LIMIT = 20
    # minimal fee rate is slightly above 1 sat/vbyte
    # to avoid rounding errors
    MIN_FEE_RATE = 1.01
    # for inheritance (to simplify LWallet logic)
    AddressListCls = AddressList
    TxListCls = TxList

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
        frozen_utxo,
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
        self.frozen_utxo = frozen_utxo
        self.fullpath = fullpath
        self.manager = manager
        self.rpc = self.manager.rpc.wallet(
            os.path.join(self.manager.rpc_path, self.alias)
        )
        self.last_block = last_block

        addr_path = self.fullpath.replace(".json", "_addr.csv")
        self._addresses = self.AddressListCls(addr_path, self.rpc)
        if not self._addresses.file_exists:
            self.fetch_labels()

        txs_path = self.fullpath.replace(".json", "_txs.csv")
        self._transactions = self.TxListCls(
            txs_path, self.rpc, self._addresses, self.manager.chain
        )

        if address == "":
            self.getnewaddress()
        if change_address == "":
            self.getnewaddress(change=True)

        self.update()
        if old_format_detected or self.last_block != last_block:
            self.save_to_file()

    @classmethod
    def create(
        cls,
        rpc,
        rpc_path,
        working_folder,
        device_manager,
        wallet_manager,
        name,
        alias,
        sigs_required,
        key_type,
        keys,
        devices,
        core_version=None,
    ):
        """Creates a wallet. If core_version is not specified - get it from rpc"""
        # get xpubs in a form [fgp/der]xpub from all keys
        xpubs = [key.metadata["combined"] for key in keys]
        recv_keys = ["%s/0/*" % xpub for xpub in xpubs]
        change_keys = ["%s/1/*" % xpub for xpub in xpubs]
        is_multisig = len(keys) > 1
        # we start by constructing an argument for descriptor wrappers
        if is_multisig:
            recv_descriptor = "sortedmulti({},{})".format(
                sigs_required, ",".join(recv_keys)
            )
            change_descriptor = "sortedmulti({},{})".format(
                sigs_required, ",".join(change_keys)
            )
        else:
            recv_descriptor = recv_keys[0]
            change_descriptor = change_keys[0]
        # now we iterate over script-type in reverse order
        # to get sh(wpkh(xpub)) from sh-wpkh and xpub
        arr = key_type.split("-")
        for el in arr[::-1]:
            recv_descriptor = "%s(%s)" % (el, recv_descriptor)
            change_descriptor = "%s(%s)" % (el, change_descriptor)

        recv_descriptor = AddChecksum(recv_descriptor)
        change_descriptor = AddChecksum(change_descriptor)
        if not recv_descriptor != change_descriptor:
            raise SpecterError(
                f"The recv_descriptor ({recv_descriptor}) is the same than the change_descriptor ({change_descriptor})"
            )

        # get Core version if we don't know it
        if core_version is None:
            core_version = rpc.getnetworkinfo().get("version", 0)

        use_descriptors = core_version >= 210000
        if use_descriptors:
            # Use descriptor wallet
            rpc.createwallet(os.path.join(rpc_path, alias), True, True, "", False, True)
        else:
            rpc.createwallet(os.path.join(rpc_path, alias), True)

        wallet_rpc = rpc.wallet(os.path.join(rpc_path, alias))
        # import descriptors
        args = [
            {
                "desc": desc,
                "internal": change,
                "timestamp": "now",
                "watchonly": True,
            }
            for (change, desc) in [(False, recv_descriptor), (True, change_descriptor)]
        ]
        for arg in args:
            if use_descriptors:
                arg["active"] = True
            else:
                arg["keypool"] = True
                arg["range"] = [0, cls.GAP_LIMIT]

        if not args[0] != args[1]:
            raise SpecterError(f"{args[0]} is equal {args[1]}")

        # Descriptor wallets were introduced in v0.21.0, but upgraded nodes may
        # still have legacy wallets. Use getwalletinfo to check the wallet type.
        # The "keypool" for descriptor wallets is automatically refilled
        if use_descriptors:
            res = wallet_rpc.importdescriptors(args)
        else:
            res = wallet_rpc.importmulti(args, {"rescan": False})

        if not all([r["success"] for r in res]):
            all_issues = " and ".join(
                r["error"]["message"] for r in res if r["success"] == False
            )
            raise SpecterError(all_issues)

        return cls(
            name,
            alias,
            "{} of {} {}".format(sigs_required, len(keys), purposes[key_type])
            if len(keys) > 1
            else purposes[key_type],
            addrtypes[key_type],
            "",
            -1,
            "",
            -1,
            0,
            0,
            recv_descriptor,
            change_descriptor,
            keys,
            devices,
            sigs_required,
            {},
            [],
            os.path.join(working_folder, "%s.json" % alias),
            device_manager,
            wallet_manager,
        )

    def fetch_labels(self):
        """Load addresses and labels to self._addresses"""
        recv = [
            dict(
                address=self.get_address(idx, change=False, check_keypool=False),
                index=idx,
                change=False,
            )
            for idx in range(self.keypool)
        ]
        change = [
            dict(
                address=self.get_address(idx, change=True, check_keypool=False),
                index=idx,
                change=True,
            )
            for idx in range(self.change_keypool)
        ]
        # TODO: load addresses for all txs here as well
        self._addresses.add(recv + change, check_rpc=True)

    def fetch_transactions(self):
        """Load transactions from Bitcoin Core"""
        arr = []
        idx = 0
        # unconfirmed_selftransfers needed since Bitcoin Core does not properly list `selftransfer` txs in `listtransactions` command
        # Until v0.21, it listed there consolidations to a receive address, but not change address
        # Since v0.21, it does not list there consolidations at all
        # Therefore we need to check here if a transaction might got confirmed
        # NOTE: This might be a problem in case of re-org...
        # More details: https://github.com/cryptoadvance/specter-desktop/issues/996
        unconfirmed_selftransfers = [
            txid
            for txid in self._transactions
            if self._transactions[txid].get("category", "") == "selftransfer"
            and not self._transactions[txid].get("blockhash", None)
        ]
        unconfirmed_selftransfers_txs = []
        if unconfirmed_selftransfers:
            unconfirmed_selftransfers_txs = self.rpc.multi(
                [("gettransaction", txid) for txid in unconfirmed_selftransfers]
            )
        while True:
            txlist = (
                self.rpc.listtransactions(
                    "*",
                    LISTTRANSACTIONS_BATCH_SIZE,
                    LISTTRANSACTIONS_BATCH_SIZE * idx,
                    True,
                )
                + [tx["result"] for tx in unconfirmed_selftransfers_txs]
            )
            # list of transactions that we don't know about,
            # or that it has a different blockhash (reorg / confirmed)
            # or doesn't have an address(?)
            # or has wallet conflicts
            res = [
                tx
                for tx in txlist
                if tx["txid"] not in self._transactions
                or not self._transactions[tx["txid"]].get("address", None)
                or self._transactions[tx["txid"]].get("blockhash", None)
                != tx.get("blockhash", None)
                or (
                    self._transactions[tx["txid"]].get("blockhash", None)
                    and not self._transactions[tx["txid"]].get("blockheight", None)
                )  # Fix for Core v19 with Specter v1
                or self._transactions[tx["txid"]].get("conflicts", [])
                != tx.get("walletconflicts", [])
            ]
            # TODO: Looks like Core ignore a consolidation (self-transfer) going into the change address (in listtransactions)
            # This means it'll show unconfirmed for us forever...
            arr.extend(res)
            idx += 1
            # not sure if Core <20 returns last batch or empty array at the end
            if (
                len(res) < LISTTRANSACTIONS_BATCH_SIZE
                or len(arr) < LISTTRANSACTIONS_BATCH_SIZE * idx
            ):
                break
        txs = dict.fromkeys([a["txid"] for a in arr])
        txids = list(txs.keys())
        # get all raw transactions
        res = self.rpc.multi([("gettransaction", txid) for txid in txids])
        for i, r in enumerate(res):
            txid = txids[i]
            # check if we already added it
            if txs.get(txid, None) is not None:
                continue
            txs[txid] = r["result"]
        # This is a fix for Bitcoin Core versions < v0.20
        # These do not return the blockheight as part of the `gettransaction` command
        # So here we check if this property is lacking and if so
        # query the current block height and manually calculate it.
        ##################### Remove from here after dropping Core v0.19 support #####################
        check_blockheight = False
        for tx in txs.values():
            if tx and tx.get("confirmations", 0) > 0 and "blockheight" not in tx:
                check_blockheight = True
                break
        if check_blockheight:
            current_blockheight = self.rpc.getblockcount()
            for tx in txs.values():
                if tx.get("confirmations", 0) > 0:
                    tx["blockheight"] = current_blockheight - tx["confirmations"] + 1
        ##################### Remove until here after dropping Core v0.19 support #####################
        self._transactions.add(txs)
        if self.use_descriptors:
            while (
                len(
                    [
                        tx
                        for tx in self._transactions
                        if self._transactions[tx]["category"] != "send"
                        and not self._transactions[tx]["address"]
                    ]
                )
                != 0
            ):
                addresses = [
                    dict(
                        address=self.get_address(
                            idx, change=False, check_keypool=False
                        ),
                        index=idx,
                        change=False,
                    )
                    for idx in range(
                        self._addresses.max_index(change=False),
                        self._addresses.max_index(change=False) + self.GAP_LIMIT,
                    )
                ]
                change_addresses = [
                    dict(
                        address=self.get_address(idx, change=True, check_keypool=False),
                        index=idx,
                        change=True,
                    )
                    for idx in range(
                        self._addresses.max_index(change=True),
                        self._addresses.max_index(change=True) + self.GAP_LIMIT,
                    )
                ]
                self._addresses.add(addresses, check_rpc=False)
                self._addresses.add(change_addresses, check_rpc=False)

    def update(self):
        self.getdata()
        self.get_balance()
        self.check_addresses()

    def check_unused(self):
        """Check current receive address is unused and get new if needed"""
        addr = self.address
        try:
            while self.rpc.getreceivedbyaddress(addr, 0) != 0:
                addr = self.getnewaddress()
        except Exception as e:
            logger.error(f"Failed to check for address reuse: {e}")

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
        addresses = [tx["address"] for tx in txs if "address" in tx]
        # remove duplicates
        addresses = list(dict.fromkeys(addresses))
        max_recv = self.address_index - 1
        max_change = self.change_index - 1
        # get max used from addresses list
        max_recv = max(max_recv, self._addresses.max_used_index(False))
        max_change = max(max_change, self._addresses.max_used_index(True))
        # from tx list
        for addr in addresses:
            if addr in self._addresses:
                a = self._addresses[addr]
                if a.index is not None:
                    if a.change:
                        max_change = max(max_change, a.index)
                    else:
                        max_recv = max(max_recv, a.index)
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
            new_dict["recv_descriptor"] = add_checksum(
                new_dict["recv_descriptor"]
                .replace("multi", "sortedmulti")
                .split("#")[0]
            )
            old_format_detected = True
        if (
            len(new_dict["keys"]) > 1
            and "sortedmulti" not in new_dict["change_descriptor"]
        ):
            new_dict["change_descriptor"] = add_checksum(
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
                logger.error("A device used by this wallet could not have been found!")
                return
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
        frozen_utxo = wallet_dict.get("frozen_utxo", [])
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
            logger.error("Could not construct a Wallet object from the data provided.")
            return

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
            frozen_utxo,
            fullpath,
            device_manager,
            manager,
            old_format_detected=wallet_dict["old_format_detected"],
            last_block=last_block,
        )

    def get_info(self):
        try:
            self.info = self.rpc.getwalletinfo()
        except Exception as e:
            raise SpecterError(e)
        return self.info

    def check_utxo(self):
        try:
            locked_utxo = self.rpc.listlockunspent()
            if locked_utxo:
                self.rpc.lockunspent(True, locked_utxo)
            utxo = self.rpc.listunspent(0)
            if locked_utxo:
                self.rpc.lockunspent(False, locked_utxo)
                for tx in utxo:
                    if [
                        _tx
                        for _tx in locked_utxo
                        if _tx["txid"] == tx["txid"] and _tx["vout"] == tx["vout"]
                    ]:
                        tx["locked"] = True
            # list only the ones we know (have descriptor for it)
            utxo = [tx for tx in utxo if tx.get("desc", "")]
            for tx in utxo:
                tx_data = self.gettransaction(tx["txid"], 0, full=False)
                tx["time"] = tx_data["time"]
                tx["category"] = "send"
                if "locked" not in tx:
                    tx["locked"] = False
                try:
                    # get category from the descriptor - recv or change
                    idx = tx["desc"].split("[")[1].split("]")[0].split("/")[-2]
                    if idx == "0":
                        tx["category"] = "receive"
                except:
                    pass
            self.full_utxo = sorted(utxo, key=lambda utxo: utxo["time"], reverse=True)
        except Exception as e:
            self.full_utxo = []
            raise SpecterError(f"Failed to load utxos, {e}")

    def getdata(self):
        self.fetch_transactions()
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
                f"Didn't get transactions on change address {self.change_address}. Refilling keypool."
            )
            self.keypoolrefill(0, end=self.keypool, change=False)
            self.keypoolrefill(0, end=self.change_keypool, change=True)
            value_on_address = 0

        # if not - just return
        if value_on_address > 0:
            self.change_index += 1
            self.getnewaddress(change=True)

    @property
    def utxo(self):
        return [utxo for utxo in self.full_utxo if not utxo["locked"]]

    @property
    def json(self):
        return self.to_json()

    def to_json(self, for_export=False):
        o = {
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
            "blockheight": self.blockheight,
        }
        if for_export:
            o["labels"] = self.export_labels()
        else:
            o["pending_psbts"] = self.pending_psbts
            o["frozen_utxo"] = self.frozen_utxo
            o["last_block"] = self.last_block
        return o

    def save_to_file(self):
        write_json_file(self.to_json(), self.fullpath)
        self.manager.update()

    def delete_files(self):
        delete_file(self.fullpath)
        delete_file(self.fullpath + ".bkp")
        delete_file(self._addresses.path)
        delete_file(self._transactions.path)

    @property
    def use_descriptors(self):
        if not hasattr(self, "info") or self.info != {}:
            self.get_info()
        return "descriptors" in self.info and self.info["descriptors"] == True

    @property
    def is_multisig(self):
        return len(self.keys) > 1

    @property
    def keys_count(self):
        return len(self.keys)

    @property
    def locked_amount(self):
        amount = 0
        for psbt in self.pending_psbts:
            amount += sum(
                [
                    utxo.get("witness_utxo", {}).get("amount", 0)
                    or utxo.get("value", 0)
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

    def toggle_freeze_utxo(self, utxo_list):
        # utxo = ["txid:vout", "txid:vout"]
        for utxo in utxo_list:
            if utxo in self.frozen_utxo:
                try:
                    self.rpc.lockunspent(
                        True,
                        [{"txid": utxo.split(":")[0], "vout": int(utxo.split(":")[1])}],
                    )
                except Exception as e:
                    # UTXO was spent
                    print(e)
                    pass
                self.frozen_utxo.remove(utxo)
            else:
                try:
                    self.rpc.lockunspent(
                        False,
                        [{"txid": utxo.split(":")[0], "vout": int(utxo.split(":")[1])}],
                    )
                except Exception as e:
                    # UTXO was spent
                    print(e)
                    pass
                self.frozen_utxo.append(utxo)

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
        try:
            self.rpc.lockunspent(False, psbt["tx"]["vin"])
        except:
            logger.debug(
                "Failed to lock UTXO for transaction, might be fine if the transaction is an RBF."
            )
        self.save_to_file()

    def txlist(
        self,
        fetch_transactions=True,
        validate_merkle_proofs=False,
        current_blockheight=None,
    ):
        """Returns a list of all transactions in the wallet's CSV cache - processed with information to display in the UI in the transactions list
        #Parameters:
        #    fetch_transactions (bool): Update the TxList CSV caching by fetching transactions from the Bitcoin RPC
        #    validate_merkle_proofs (bool): Return transactions with validated_blockhash
        #    current_blockheight (int): Current blockheight for calculating confirmations number (None will fetch the block count from the RPC)
        """
        if fetch_transactions or (
            self.use_descriptors
            and len(
                [
                    tx
                    for tx in self._transactions
                    if self._transactions[tx]["category"] != "send"
                    and not self._transactions[tx]["address"]
                ]
            )
            != 0
        ):
            self.fetch_transactions()
        try:
            _transactions = [
                tx.__dict__().copy()
                for tx in self._transactions.values()
                if tx["ismine"]
            ]
            transactions = sorted(
                _transactions, key=lambda tx: tx["time"], reverse=True
            )
            transactions = [
                tx
                for tx in transactions
                if (
                    not tx["conflicts"]
                    or max(
                        [
                            self.gettransaction(conflicting_tx, 0, full=False)["time"]
                            for conflicting_tx in tx["conflicts"]
                        ]
                    )
                    < tx["time"]
                )
            ]
            if not current_blockheight:
                current_blockheight = self.rpc.getblockcount()
            result = []
            blocks = {}
            for tx in transactions:
                if not tx.get("blockheight", 0):
                    tx["confirmations"] = 0
                else:
                    tx["confirmations"] = current_blockheight - tx["blockheight"] + 1

                # coinbase tx
                if tx["category"] == "generate":
                    if tx["confirmations"] <= 100:
                        category = "immature"

                if (
                    tx.get("confirmations") == 0
                    and tx.get("bip125-replaceable", "no") == "yes"
                ):
                    rpc_tx = self.rpc.gettransaction(tx["txid"])
                    tx["fee"] = rpc_tx.get("fee", 1)
                    tx["confirmations"] = rpc_tx.get("confirmations", 0)

                if isinstance(tx["address"], str):
                    tx["label"] = self.getlabel(tx["address"])
                elif isinstance(tx["address"], list):
                    tx["label"] = [self.getlabel(address) for address in tx["address"]]
                else:
                    tx["label"] = None

                # TODO: validate for unique txids only
                tx["validated_blockhash"] = ""  # default is assume unvalidated
                if validate_merkle_proofs is True and tx["confirmations"] > 0:
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
                        logger.debug(
                            f"Merkle proof of { tx['txid'] } validation success"
                        )
                        tx["validated_blockhash"] = tx["blockhash"]
                    else:
                        logger.warning(
                            f"Attempted merkle proof validation on {tx['txid']} but failed. This is likely a configuration error but perhaps your node is compromised! Details: {proof_hex}"
                        )

                result.append(tx)
            return result
        except Exception as e:
            logging.error("Exception while processing txlist: {}".format(e))
            return []

    def gettransaction(self, txid, blockheight=None, decode=False, full=True):
        """Gets transaction from cache
        If full=True it will also contain "hex" key with full hex transaction.
        If decode=True it will decode the transaction similar to Core decoderawtransaction call
        """
        try:
            return self._transactions.gettransaction(
                txid, blockheight, full=full, decode=decode
            )
        except Exception as e:
            logger.warning("Could not get transaction {}, error: {}".format(txid, e))

    def is_tx_purged(self, txid):
        # Is tx unconfirmed and no longer in the mempool?
        try:
            tx = self.rpc.gettransaction(txid)

            # Do this quick test first to avoid the costlier rpc call
            if tx["confirmations"] > 0:
                return False

            return txid not in self.rpc.getrawmempool()
        except Exception as e:
            logger.warning("Could not check is_tx_purged {}, error: {}".format(txid, e))

    def abandontransaction(self, txid):
        # Sanity checks: tx must be unconfirmed and cannot be in the mempool
        tx = self.rpc.gettransaction(txid)
        if tx["confirmations"] != 0:
            raise SpecterError("Cannot abandon a transaction that has a confirmation.")
        elif txid in self.rpc.getrawmempool():
            raise SpecterError(
                "Cannot abandon a transaction that is still in the mempool."
            )
        self.rpc.abandontransaction(txid)

    def rescanutxo(self, explorer=None, requests_session=None, only_tor=False):
        delete_file(self._transactions.path)
        self.fetch_transactions()
        t = threading.Thread(
            target=self._rescan_utxo_thread,
            args=(
                explorer,
                requests_session,
                only_tor,
            ),
        )
        t.start()

    def export_labels(self):
        return self._addresses.get_labels()

    def import_labels(self, labels):
        # format:
        #   {
        #       'label1': ['address1', 'address2'],
        #       'label2': ['address3', 'address4']
        #   }
        #
        for label, addresses in labels.items():
            if not label:
                continue
            for address in addresses:
                self._addresses.set_label(address, label)

    def _rescan_utxo_thread(self, explorer=None, requests_session=None, only_tor=False):
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
                # retry if using requests_session failed
                if not only_tor:
                    try:
                        # get raw transactions
                        raws = [
                            requests.get(f"{explorer}/api/tx/{tx['txid']}/hex").text
                            for tx in missing
                        ]
                        # get proofs
                        proofs = [
                            requests.get(
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
                    except:
                        logger.warning(f"Failed to fetch data from block explorer: {e}")
        self.fetch_transactions()
        self.check_addresses()

    @property
    def rescan_progress(self):
        """Returns None if rescanblockchain is not launched,
        value between 0 and 1 otherwise
        """
        if self.info.get("scanning", False) == False:
            return None
        else:
            return self.info["scanning"]["progress"]

    @property
    def blockheight(self):
        self.fetch_transactions()
        MAX_BLOCKHEIGHT = 999999999999  # Replace before we reach this height
        first_tx = sorted(
            self._transactions.values(),
            key=lambda tx: tx.get("blockheight", None)
            if tx.get("blockheight", None)
            else MAX_BLOCKHEIGHT,
        )
        first_tx_blockheight = (
            first_tx[0].get("blockheight", None) if first_tx else None
        )
        if first_tx:
            if first_tx_blockheight and first_tx_blockheight - 101 > 0:
                return (
                    first_tx_blockheight - 101
                )  # Give tiny margin to catch edge case of mined coins
        return 481824 if self.manager.chain == "main" else 0

    @property
    def account_map(self):
        account_map_dict = {
            "label": self.name,
            "blockheight": self.blockheight,
            "descriptor": self.recv_descriptor,
            "devices": [{"type": d.device_type, "label": d.name} for d in self.devices],
        }
        return json.dumps(account_map_dict)

    def getnewaddress(self, change=False, save=True):
        if change:
            self.change_index += 1
            index = self.change_index
        else:
            self.address_index += 1
            index = self.address_index
        address = self.get_address(index, change=change)
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
        return (
            LDescriptor.from_string(desc)
            .derive(index)
            .address(get_network(self.manager.chain))
        )

    def get_descriptor(self, index=None, change=False, address=None):
        """
        Returns address descriptor from index, change
        or from address belonging to the wallet.
        """
        if address is not None:
            # only ask rpc if address is not known directly
            if address not in self._addresses:
                return self.rpc.getaddressinfo(address).get("desc", "")
            else:
                a = self._addresses[address]
                index = a.index
                change = a.change
        if index is None:
            index = self.change_index if change else self.address_index
        desc = self.change_descriptor if change else self.recv_descriptor
        derived_desc = Descriptor.parse(desc).derive(index).serialize()
        derived_desc_xpubs = (
            Descriptor.parse(desc).derive(index, keep_xpubs=True).serialize()
        )
        return {"descriptor": derived_desc, "xpubs_descriptor": derived_desc_xpubs}

    def get_address_info(self, address):
        return self._addresses.get(address)

    def is_address_mine(self, address):
        addrinfo = self.get_address_info(address)
        return addrinfo and not addrinfo.is_external

    def get_electrum_file(self):
        """Exports the wallet data as Electrum JSON format"""
        electrum_devices = [
            "bitbox02",
            "coldcard",
            "digitalbitbox",
            "keepkey",
            "ledger",
            "safe_t",
            "trezor",
        ]
        if len(self.keys) == 1:
            # Single-sig case:
            key = self.keys[0]
            if self.devices[0].device_type in electrum_devices:
                return {
                    "keystore": {
                        "ckcc_xfp": int(
                            "".join(list(reversed(re.findall("..?", key.fingerprint)))),
                            16,
                        ),
                        "ckcc_xpub": key.xpub,
                        "derivation": key.derivation.replace("h", "'"),
                        "root_fingerprint": key.fingerprint,
                        "hw_type": self.devices[0].device_type,
                        "label": self.devices[0].name,
                        "type": "hardware",
                        "soft_device_id": None,
                        "xpub": key.original,
                    },
                    "wallet_type": "standard",
                }
            else:
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

        to_return = {"wallet_type": "{}of{}".format(self.sigs_required, len(self.keys))}
        for cnt, device in enumerate(self.devices):
            keys_matched = [key for key in device.keys if key in self.keys]
            if keys_matched:
                key = keys_matched[0]
            else:
                return {"error": "Missing key couldn't be found in any device"}
            if device.device_type in electrum_devices:
                to_return["x{}/".format(cnt + 1)] = {
                    "ckcc_xfp": int(
                        "".join(list(reversed(re.findall("..?", key.fingerprint)))), 16
                    ),
                    "ckcc_xpub": key.xpub,
                    "derivation": key.derivation.replace("h", "'"),
                    "root_fingerprint": key.fingerprint,
                    "hw_type": device.device_type,
                    "label": device.name,
                    "type": "hardware",
                    "soft_device_id": None,
                    "xpub": key.original,
                }
            else:
                to_return["x{}/".format(cnt + 1)] = {
                    "derivation": key.derivation.replace("h", "'"),
                    "root_fingerprint": key.fingerprint,
                    "type": "bip32",
                    "xprv": None,
                    "xpub": key.original,
                }

        return to_return

    def get_balance(self):
        try:
            balance = (
                self.rpc.getbalances()["mine"]
                if self.use_descriptors
                else self.rpc.getbalances()["watchonly"]
            )
            # calculate available balance
            locked_utxo = self.rpc.listlockunspent()
            available = {}
            available.update(balance)
            for tx in locked_utxo:
                tx_data = self.gettransaction(tx["txid"])
                raw_tx = decoderawtransaction(tx_data["hex"], self.manager.chain)
                delta = raw_tx["vout"][tx["vout"]]["value"]
                if "confirmations" not in tx_data or tx_data["confirmations"] == 0:
                    available["untrusted_pending"] -= delta
                else:
                    available["trusted"] -= delta
                    available["trusted"] = round(available["trusted"], 8)
            available["untrusted_pending"] = round(available["untrusted_pending"], 8)
            balance["available"] = available
        except Exception as e:
            raise SpecterError(f"was not able to get wallet_balance because {e}")
        self.balance = balance
        return self.balance

    def keypoolrefill(self, start, end=None, change=False):
        if end is None:
            # end is ignored for descriptor wallets
            end = start + self.GAP_LIMIT

        desc = self.recv_descriptor if not change else self.change_descriptor
        args = [
            {
                "desc": desc,
                "internal": change,
                "timestamp": "now",
                "watchonly": True,
            }
        ]
        if self.use_descriptors:
            args[0]["active"] = True
        else:
            args[0]["keypool"] = True
            args[0]["range"] = [start, end]

        try:
            addresses = [
                dict(
                    address=self.get_address(idx, change=change, check_keypool=False),
                    index=idx,
                    change=change,
                )
                for idx in range(start, end)
            ]
            self._addresses.add(addresses, check_rpc=False)
        except Exception as e:
            logger.warn(f"Error while calculating addresses: {e}")

        # Descriptor wallets were introduced in v0.21.0, but upgraded nodes may
        # still have legacy wallets. Use getwalletinfo to check the wallet type.
        # The "keypool" for descriptor wallets is automatically refilled
        if not self.use_descriptors:
            r = self.rpc.importmulti(args, {"rescan": False})

        if change:
            self.change_keypool = end
        else:
            self.keypool = end

        self.save_to_file()
        return end

    def setlabel(self, address, label):
        self._addresses.set_label(address, label)

    def getlabel(self, address):
        if address in self._addresses:
            return self._addresses[address].label
        else:
            return address

    def getlabels(self, addresses):
        labels = {}
        for addr in addresses:
            labels[addr] = self.getlabel(addr)
        return labels

    def get_address_name(self, address, addr_idx):
        # TODO: remove
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
        rbf=True,
        existing_psbt=None,
        rbf_edit_mode=False,
    ):
        """
        fee_rate: in sat/B or BTC/kB. If set to 0 Bitcoin Core sets feeRate automatically.
        """
        if fee_rate > 0 and fee_rate < self.MIN_FEE_RATE:
            fee_rate = self.MIN_FEE_RATE

        options = {"includeWatching": True, "replaceable": rbf}
        extra_inputs = []

        if not existing_psbt:
            if not rbf_edit_mode:
                if self.full_available_balance < sum(amounts):
                    raise SpecterError(
                        f"Wallet {self.name} does not have sufficient funds to make the transaction."
                    )

            if selected_coins != []:
                still_needed = sum(amounts)
                for coin in selected_coins:
                    coin_txid = coin.split(",")[0]
                    coin_vout = int(coin.split(",")[1])
                    coin_amount = self.gettransaction(coin_txid, decode=True)["vout"][
                        coin_vout
                    ]["value"]
                    extra_inputs.append({"txid": coin_txid, "vout": coin_vout})
                    still_needed -= coin_amount
                    if still_needed < 0:
                        break
                if still_needed > 0:
                    raise SpecterError(
                        "Selected coins does not cover Full amount! Please select more coins!"
                    )
            elif self.available_balance["trusted"] <= sum(amounts):
                txlist = self.rpc.listunspent(0, 0)
                b = sum(amounts) - self.available_balance["trusted"]
                for tx in txlist:
                    extra_inputs.append({"txid": tx["txid"], "vout": tx["vout"]})
                    b -= tx["amount"]
                    if b < 0:
                        break

            # subtract fee from amount of this output:
            # currently only one address is supported, so either
            # empty array (subtract from change) or [0]
            subtract_arr = [subtract_from] if subtract else []

            options = {
                "includeWatching": True,
                "changeAddress": self.change_address,
                "subtractFeeFromOutputs": subtract_arr,
                "replaceable": rbf,
            }

            if self.manager.bitcoin_core_version_raw >= 210000:
                options["add_inputs"] = selected_coins == []

            if fee_rate > 0:
                # bitcoin core needs us to convert sat/B to BTC/kB
                options["feeRate"] = round((fee_rate * 1000) / 1e8, 8)

            r = self.rpc.walletcreatefundedpsbt(
                extra_inputs,  # inputs
                [{addresses[i]: amounts[i]} for i in range(len(addresses))],  # output
                0,  # locktime
                options,  # options
                True,  # bip32-der
            )

            b64psbt = r["psbt"]
            psbt = self.rpc.decodepsbt(b64psbt)
        else:
            psbt = existing_psbt
            extra_inputs = [
                {"txid": tx["txid"], "vout": tx["vout"]} for tx in psbt["tx"]["vin"]
            ]
            if "changeAddress" in psbt:
                options["changeAddress"] = psbt["changeAddress"]
            if "base64" in psbt:
                b64psbt = psbt["base64"]

        if fee_rate > 0.0:
            if not existing_psbt:
                psbt_fees_sats = int(psbt["fee"] * 1e8)
                # estimate final size: add weight of inputs
                tx_full_size = ceil(
                    psbt["tx"]["vsize"]
                    + len(psbt["inputs"]) * self.weight_per_input / 4
                )
                adjusted_fee_rate = (
                    fee_rate
                    * (fee_rate / (psbt_fees_sats / psbt["tx"]["vsize"]))
                    * (tx_full_size / psbt["tx"]["vsize"])
                )
                options["feeRate"] = "%.8f" % round((adjusted_fee_rate * 1000) / 1e8, 8)
            else:
                options["feeRate"] = "%.8f" % round((fee_rate * 1000) / 1e8, 8)
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

    def get_rbf_utxo(self, rbf_tx_id):
        decoded_tx = self.decode_tx(rbf_tx_id)
        selected_coins = [
            f"{utxo['txid']}, {utxo['vout']}" for utxo in decoded_tx["used_utxo"]
        ]
        rbf_utxo = [
            {
                "txid": tx["txid"],
                "vout": tx["vout"],
                "details": self.gettransaction(tx["txid"], decode=True)["vout"][
                    tx["vout"]
                ],
            }
            for tx in decoded_tx["used_utxo"]
        ]
        return [
            {
                "txid": utxo["txid"],
                "vout": utxo["vout"],
                "amount": utxo["details"]["value"],
                "address": get_address_from_dict(utxo["details"]),
                "label": self.getlabel(get_address_from_dict(utxo["details"])),
            }
            for utxo in rbf_utxo
        ]

    def decode_tx(self, txid):
        raw_tx = self.gettransaction(txid)["hex"]
        raw_psbt = self.rpc.utxoupdatepsbt(
            self.rpc.converttopsbt(raw_tx, True),
            [self.recv_descriptor, self.change_descriptor],
        )

        psbt = self.rpc.decodepsbt(raw_psbt)
        return {
            "addresses": [
                get_address_from_dict(vout["scriptPubKey"])
                for i, vout in enumerate(psbt["tx"]["vout"])
                if not self.get_address_info(
                    get_address_from_dict(vout["scriptPubKey"])
                )
                or not self.get_address_info(
                    get_address_from_dict(vout["scriptPubKey"])
                ).change
            ],
            "amounts": [
                vout["value"]
                for i, vout in enumerate(psbt["tx"]["vout"])
                if not self.get_address_info(
                    get_address_from_dict(vout["scriptPubKey"])
                )
                or not self.get_address_info(
                    get_address_from_dict(vout["scriptPubKey"])
                ).change
            ],
            "used_utxo": [
                {"txid": vin["txid"], "vout": vin["vout"]} for vin in psbt["tx"]["vin"]
            ],
        }

    def canceltx(self, txid, fee_rate):
        self.check_unused()
        raw_tx = self.gettransaction(txid)["hex"]
        raw_psbt = self.rpc.utxoupdatepsbt(
            self.rpc.converttopsbt(raw_tx, True),
            [self.recv_descriptor, self.change_descriptor],
        )

        psbt = self.rpc.decodepsbt(raw_psbt)
        decoded_tx = self.decode_tx(txid)
        selected_coins = [
            f"{utxo['txid']}, {utxo['vout']}" for utxo in decoded_tx["used_utxo"]
        ]
        return self.createpsbt(
            addresses=[self.address],
            amounts=[
                sum(
                    vout["witness_utxo"]["amount"]
                    for i, vout in enumerate(psbt["inputs"])
                )
            ],
            subtract=True,
            fee_rate=float(fee_rate),
            selected_coins=selected_coins,
            readonly=False,
            rbf=True,
            rbf_edit_mode=True,
        )

    def bumpfee(self, txid, fee_rate):
        raw_tx = self.gettransaction(txid)["hex"]
        raw_psbt = self.rpc.utxoupdatepsbt(
            self.rpc.converttopsbt(raw_tx, True),
            [self.recv_descriptor, self.change_descriptor],
        )

        psbt = self.rpc.decodepsbt(raw_psbt)
        psbt["changeAddress"] = [
            get_address_from_dict(vout["scriptPubKey"])
            for i, vout in enumerate(psbt["tx"]["vout"])
            if self.get_address_info(get_address_from_dict(vout["scriptPubKey"]))
            and self.get_address_info(
                get_address_from_dict(vout["scriptPubKey"])
            ).change
        ]
        if psbt["changeAddress"]:
            psbt["changeAddress"] = psbt["changeAddress"][0]
        else:
            raise Exception("Cannot RBF a transaction with no change output")
        return self.createpsbt(
            addresses=[
                get_address_from_dict(vout["scriptPubKey"])
                for i, vout in enumerate(psbt["tx"]["vout"])
                if not self.get_address_info(
                    get_address_from_dict(vout["scriptPubKey"])
                )
                or not self.get_address_info(
                    get_address_from_dict(vout["scriptPubKey"])
                ).change
            ],
            amounts=[
                vout["value"]
                for i, vout in enumerate(psbt["tx"]["vout"])
                if not self.get_address_info(
                    get_address_from_dict(vout["scriptPubKey"])
                )
                or not self.get_address_info(
                    get_address_from_dict(vout["scriptPubKey"])
                ).change
            ],
            fee_rate=fee_rate,
            readonly=False,
            rbf=True,
            existing_psbt=psbt,
        )

    def fill_psbt(self, b64psbt, non_witness: bool = True, xpubs: bool = True):
        psbt = PSBT.from_string(b64psbt)

        if non_witness:
            for inp in psbt.inputs:
                # we don't need to fill what is already filled
                if inp.non_witness_utxo is not None:
                    continue
                txid = inp.txid.hex()
                try:
                    res = self.gettransaction(txid)
                    inp.non_witness_utxo = Transaction.from_string(res["hex"])
                except Exception as e:
                    logger.error(
                        f"Can't find previous transaction in the wallet. Signing might not be possible for certain devices... Txid: {txid}, Exception: {e}"
                    )
        else:
            # remove non_witness_utxo if we don't want them
            for inp in psbt.inputs:
                if inp.witness_utxo is not None:
                    inp.non_witness_utxo = None

        if xpubs:
            # for multisig add xpub fields
            if len(self.keys) > 1:
                for k in self.keys:
                    key = bip32.HDKey.from_string(k.xpub)
                    if k.fingerprint != "":
                        fingerprint = bytes.fromhex(k.fingerprint)
                    else:
                        fingerprint = get_xpub_fingerprint(k.xpub)
                    if k.derivation != "":
                        der = bip32.parse_path(k.derivation)
                    else:
                        der = []
                    psbt.xpubs[key] = DerivationPath(fingerprint, der)
        else:
            psbt.xpubs = {}
        return psbt.to_string()

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
            ) and "address" not in out["scriptPubKey"]:
                # TODO: we need to handle it somehow differently
                raise SpecterError("Sending to raw scripts is not supported yet")
            addr = get_address_from_dict(out["scriptPubKey"])
            info = self.get_address_info(addr)
            # check if it's a change
            if info and info.change:
                continue
            address.append(addr)
            amount.append(out["value"])

        psbt = self.createpsbt(
            addresses=address,
            amounts=amount,
            fee_rate=0.0,
            readonly=False,
            existing_psbt=psbt,
        )

        signed_devices = self.get_signed_devices(psbt)
        psbt["devices_signed"] = [dev.alias for dev in signed_devices]
        psbt["sigs_count"] = len(signed_devices)
        raw = self.rpc.finalizepsbt(b64psbt)
        if "hex" in raw:
            psbt["raw"] = raw["hex"]

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

    def addresses_info(self, is_change):
        """Create a list of (receive or change) addresses from cache and retrieve the
        related UTXO and amount.
        Parameters: is_change: if true, return the change addresses else the receive ones.
        """

        addresses_info = []

        addresses_cache = [
            v for _, v in self._addresses.items() if v.change == is_change
        ]

        for addr in addresses_cache:

            addr_utxo = 0
            addr_amount = 0

            for utxo in [
                utxo for utxo in self.full_utxo if utxo["address"] == addr.address
            ]:
                addr_amount = addr_amount + utxo["amount"]
                addr_utxo = addr_utxo + 1

            addresses_info.append(
                {
                    "index": addr.index,
                    "address": addr.address,
                    "label": addr.label,
                    "amount": addr_amount,
                    "used": bool(addr.used),
                    "utxo": addr_utxo,
                    "type": "change" if is_change else "receive",
                }
            )

        return addresses_info

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name } alias={self.alias}>"
