import json, logging, os, re, csv
import requests
import threading
import time

from collections import OrderedDict
from csv import Error
from embit import bip32
from embit.descriptor import Descriptor
from embit.descriptor.checksum import add_checksum
from embit.ec import PublicKey
from embit.liquid.networks import get_network
from embit.psbt import DerivationPath
from embit.transaction import Transaction
from io import StringIO
from typing import List

from cryptoadvance.specter.commands.utxo_scanner import UtxoScanner

from .addresslist import Address, AddressList
from .device import Device
from .key import Key
from .util.merkleblock import is_valid_merkle_proof
from .helpers import get_address_from_dict
from .persistence import write_json_file, delete_file, delete_folder
from .specter_error import SpecterError, handle_exception
from .txlist import TxList
from .util.psbt import SpecterPSBT
from .util.tx import decoderawtransaction
from .util.xpub import get_xpub_fingerprint

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
        "tr": "Taproot",
    }
)

addrtypes = {
    "pkh": "legacy",
    "sh-wpkh": "p2sh-segwit",
    "wpkh": "bech32",
    "sh": "legacy",
    "sh-wsh": "p2sh-segwit",
    "wsh": "bech32",
    "tr": "taproot",  # not sure it'll work, but I don't think we are using it anyway
}


class Wallet:
    # if the wallet is old we import 300 addresses
    IMPORT_KEYPOOL = 300
    # a gap of 20 addresses is what many wallets do (not used with descriptor wallets)
    GAP_LIMIT = 20
    MIN_FEE_RATE = 1
    # for inheritance (to simplify LWallet logic)
    AddressListCls = AddressList
    TxListCls = TxList
    TxCls = Transaction
    PSBTCls = SpecterPSBT
    DescriptorCls = Descriptor

    def __init__(
        self,
        name: str,
        alias: str,
        description: str,
        address_type: str,
        address: str,
        address_index: int,
        change_address: str,
        change_index: int,
        keypool: int,
        change_keypool: int,
        descriptor: str,
        keys: list,
        devices: list,
        sigs_required,
        pending_psbts,
        frozen_utxo,
        fullpath,
        device_manager,
        manager,
        old_format_detected=False,
        last_block=None,
    ):
        """creates a wallet. Very inconvenient to call as it has a lot of mandatory Parameters.
            You better use either the Wallet.from_json() or the WalletManager.create_wallet() method.
        :param string name: a not necessarily unique name
        :param string alias: A unique alias. Might get modified automatically if not unique
        :param string: irrelevan description
        :param string address_type: one of bech32, p2sh-segwit, taproot
        :param string address: the current free recv_address
        :param int address_index: the current index for self.address
        :param string change_address: the current free change_address
        :param int change_index: the current index for self.change_address

        """
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
        self.info = {}
        # just to make sure we can accept both descriptor instance and string
        if not isinstance(descriptor, str):
            descriptor = str(descriptor)
        self.descriptor = self.DescriptorCls.from_string(descriptor)
        if self.descriptor.num_branches != 2:
            raise SpecterError(
                f"Descriptor has {self.descriptor.num_branches} branches, but we need 2."
            )

        self.keys = keys

        self.device_manager = device_manager
        self.manager = manager
        self.rpc = self.manager.rpc.wallet(
            os.path.join(self.manager.rpc_path, self.alias)
        )
        self._devices = devices
        # check that all of the devices exist
        if None in self.devices:
            raise SpecterError(
                "A device used by this wallet could not have been found!"
            )
        self.sigs_required = int(sigs_required)
        self.pending_psbts = {
            psbtid: self.PSBTCls.from_dict(
                psbtobj,
                self.descriptor,
                self.network,
                devices=list(zip(self.keys, self._devices)),
            )
            for psbtid, psbtobj in pending_psbts.items()
        }
        self.frozen_utxo = frozen_utxo
        self.fullpath = fullpath
        self.last_block = last_block

        addr_path = self.fullpath.replace(".json", "_addr.csv")
        self._addresses = self.AddressListCls(addr_path, self.rpc)
        if not self._addresses.file_exists:
            self.fetch_labels()

        txs_path = self.fullpath.replace(".json", "_txs.csv")
        self._transactions = self.TxListCls(txs_path, self, self._addresses)

        if address == "":
            self.address = self.get_address(0, change=False)
            self.address_index = 0
        if change_address == "":
            self.change_address = self.get_address(0, change=True)
            self.change_index = 0

        self.update()
        if (
            old_format_detected
            or self.last_block != last_block
            or "" in [address, change_address]
        ):
            self.save_to_file()

    @property
    def recv_descriptor(self):
        return add_checksum(str(self.descriptor.branch(0)))

    @property
    def change_descriptor(self):
        return add_checksum(str(self.descriptor.branch(1)))

    @property
    def devices(self):
        return [
            (
                device
                if isinstance(device, Device)
                else self.device_manager.get_by_alias(device)
            )
            for device in self._devices
        ]

    @property
    def chain(self) -> str:
        """String name of the chain"""
        return self.manager.chain

    @property
    def network(self) -> dict:
        """Dictionary with network constants"""
        return get_network(self.chain)

    @classmethod
    def construct_descriptor(cls, sigs_required, key_type, keys, devices):
        """
        Creates a wallet descriptor from arguments.
        We need to pass `devices` for Liquid wallet, here it's not used.
        """
        # get xpubs in a form [fgp/der]xpub from all keys
        xpubs = [key.metadata["combined"] for key in keys]
        # all keys joined with comma
        desc_keys = ",".join(["%s/{0,1}/*" % xpub for xpub in xpubs])
        is_multisig = len(keys) > 1

        # we start by constructing a base argument for descriptor wrappers
        if is_multisig:
            desc = f"sortedmulti({sigs_required},{desc_keys})"
        else:
            desc = desc_keys

        # now we iterate over script-type in reverse order
        # to get sh(wpkh(xpub)) from sh-wpkh and xpub
        arr = key_type.split("-")
        for wrapper in arr[::-1]:
            desc = f"{wrapper}({desc})"
        return cls.DescriptorCls.from_string(desc)

    @classmethod
    def merge_descriptors(cls, recv_descriptor: str, change_descriptor=None) -> str:
        """Parses string with descriptors (change is optional) and creates a combined one"""
        if change_descriptor is None and "/0/*" not in recv_descriptor:
            raise SpecterError("Receive descriptor has strange derivation path")
        if change_descriptor is None:
            change_descriptor = recv_descriptor.split("#").replace("/0/*", "/1/*")
        # remove checksums
        recv_descriptor = recv_descriptor.split("#")[0]
        change_descriptor = change_descriptor.split("#")[0]
        if recv_descriptor.replace("/0/*", "/1/*") != change_descriptor:
            raise SpecterError("Descriptors don't respect BIP-44")
        combined = recv_descriptor.replace("/0/*", "/{0,1}/*")
        # check it is valid
        try:
            cls.DescriptorCls.from_string(combined)
        except Exception as e:
            raise SpecterError(f"Invalid descriptor: {e}")
        return combined

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
        **kwargs,
    ):
        """Creates a wallet. If core_version is not specified - gets it from rpc"""
        # we pass unknown kwargs here for inherited classes (see LWallet - there is a blinding key arg)
        descriptor = cls.construct_descriptor(
            sigs_required, key_type, keys, devices, **kwargs
        )

        # get Core version if we don't know it
        if core_version is None:
            core_version = rpc.getnetworkinfo().get("version", 0)

        # Descriptor wallets were introduced in v0.21.0, but upgraded nodes may
        # still have legacy wallets or can be compiled without sqlite support.
        # Use getwalletinfo to check the wallet type.
        # The "keypool" for descriptor wallets is automatically refilled
        use_descriptors = core_version >= 210000
        created = False
        if use_descriptors:
            # Use descriptor wallet
            try:
                rpc.createwallet(
                    os.path.join(rpc_path, alias), True, True, "", False, True
                )
                created = True
            except Exception as e:
                logger.warning(e)
        # if we failed to create or didn't try - create without descriptors
        if not created:
            rpc.createwallet(os.path.join(rpc_path, alias), True)
            use_descriptors = False

        wallet_rpc = rpc.wallet(os.path.join(rpc_path, alias))
        # import descriptors
        args = [
            {
                "desc": add_checksum(str(descriptor.branch(change))),
                "internal": bool(change),
                "timestamp": "now",
                "watchonly": True,
            }
            for change in [0, 1]
        ]
        for arg in args:
            if use_descriptors:
                arg["active"] = True
            else:
                arg["keypool"] = True
                arg["range"] = [0, cls.GAP_LIMIT]

        if not args[0] != args[1]:
            raise SpecterError(f"{args[0]} is equal {args[1]}")

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
            str(descriptor),
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
        arr = [tx["result"] for tx in unconfirmed_selftransfers_txs if tx.get("result")]
        while True:
            txlist = self.rpc.listtransactions(
                "*",
                LISTTRANSACTIONS_BATCH_SIZE,  # count
                LISTTRANSACTIONS_BATCH_SIZE * idx,  # skip
                True,
            )
            # list of transactions that we don't know about,
            # or that it has a different blockhash (reorg / confirmed)
            # or doesn't have an address(?)
            # or has wallet conflicts
            res = [
                tx
                for tx in txlist
                # we don't know about tx
                if tx["txid"] not in self._transactions
                # we don't know addresses
                or not self._transactions[tx["txid"]].get("address", None)
                # blockhash is different (reorg / unconfirmed)
                or self._transactions[tx["txid"]].get("blockhash", None)
                != tx.get("blockhash", None)
                # we have conflicts
                or self._transactions[tx["txid"]].get("conflicts", [])
                != tx.get("walletconflicts", [])
            ]
            arr.extend(res)
            idx += 1
            # stop if we reached known transactions
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
        if self.use_descriptors:
            # Get all used addresses that belong to the wallet
            addresses_info_multi = self.rpc.multi(
                [
                    ("getaddressinfo", address)
                    for address in [
                        tx["details"][0].get("address")
                        for tx in txs.values()
                        if tx
                        and tx.get("details")
                        and (
                            tx.get("details")[0].get("category") != "send"
                            and tx["details"][0].get("address") not in self._addresses
                        )
                    ]
                    if address
                ]
            )
            addresses_info = [
                r["result"]
                for r in addresses_info_multi
                if r["result"].get("ismine", False)
            ]

            # Gets max index used receiving and change addresses
            max_used_receiving = self._addresses.max_used_index(change=False)
            max_used_change = self._addresses.max_used_index(change=True)

            for address in addresses_info:
                desc = self.DescriptorCls.from_string(address["desc"])
                indexes = [
                    {
                        "idx": k.origin.derivation[-1],
                        "change": k.origin.derivation[-2],
                    }
                    for k in desc.keys
                ]
                for idx in indexes:
                    if int(idx["change"]) == 0:
                        max_used_receiving = max(max_used_receiving, int(idx["idx"]))
                    elif int(idx["change"]) == 1:
                        max_used_change = max(max_used_change, int(idx["idx"]))

            # If max receiving address bigger than current max receiving index minus the gap limit - self._addresses.max_index(change=False)
            if max_used_receiving + self.GAP_LIMIT > self._addresses.max_index(
                change=False
            ):
                # Add receiving addresses until the new max address plus the GAP_LIMIT
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
                        max_used_receiving + self.GAP_LIMIT,
                    )
                ]
                self._addresses.add(addresses, check_rpc=False)

            # If max change address bigger than current max change index minus the gap limit  - self._addresses.max_index(change=True)
            if max_used_change + self.GAP_LIMIT > self._addresses.max_index(
                change=True
            ):
                # Add change addresses until the new max address plus the GAP_LIMIT
                change_addresses = [
                    dict(
                        address=self.get_address(idx, change=True, check_keypool=False),
                        index=idx,
                        change=True,
                    )
                    for idx in range(
                        self._addresses.max_index(change=True),
                        max_used_change + self.GAP_LIMIT,
                    )
                ]
                self._addresses.add(change_addresses, check_rpc=False)

        # only delete with confirmed txs
        self.delete_spent_pending_psbts(
            [
                tx["hex"]
                for tx in txs.values()
                if tx.get("confirmations", 0) > 0 or tx.get("blockheight")
            ]
        )
        self._transactions.add(txs)

    def import_address_labels(self, address_labels):
        """
        Imports address_labels given in the formats:
            - Specter JSON
            - Electrum JSON
            - Specter CSV
        Returns the number of imported address labels
        """
        if not address_labels:
            logger.warning(f"No argument was passed.")
            raise SpecterError("Looks like you didn't input any data. Try again!")
        try:
            # Specter JSON
            if "alias" in json.loads(
                address_labels
            ):  # Key that is only present in Specter JSON
                logger.debug("In the Specter JSON part.")
                raw_dictionary = json.loads(address_labels)
                labeled_addresses = {}
                for label, address in raw_dictionary["labels"].items():
                    labeled_addresses[address[0]] = label
                logger.info(f"Specter JSON was converted to {labeled_addresses}.")
            # Electrum JSON
            else:
                logger.debug("In the Electrum JSON part.")
                labeled_addresses = json.loads(address_labels)
                # write tx_label to address_label in labels
                for txitem in self._transactions.values():
                    if txitem["txid"] not in labeled_addresses:
                        continue
                    address_list = (
                        [txitem["address"]]
                        if isinstance(txitem["address"], str)
                        else txitem["address"]
                    )
                    for one_address in address_list:
                        if labeled_addresses.get(one_address):
                            continue  # if there is an address label and it is not empty, it supercedes the tx label
                        labeled_addresses[one_address] = labeled_addresses[
                            txitem["txid"]
                        ]
                logger.info(f"Electrum JSON was converted to {labeled_addresses}.")
        # Specter CSV
        except ValueError:  # If json.loads is not possible it throws a ValueError
            logger.debug("In the Specter CSV part.")
            labeled_addresses = {}
            logger.debug(address_labels)
            try:
                f = StringIO(
                    address_labels
                )  # Drag & drop / pasting of CSV results in one giant string
                dialect = csv.Sniffer().sniff(
                    address_labels
                )  # Delimiter is not always the same
                reader = csv.DictReader(f, delimiter=dialect.delimiter)
                reader.fieldnames = [name.lower() for name in reader.fieldnames]
                for row in reader:
                    if not row["label"].startswith(
                        "Address #"
                    ):  # Avoids importing addresses with standard "Address #X" description
                        labeled_addresses[row["address"]] = row["label"]
                logger.info(f"Specter label CSV was converted to {labeled_addresses}.")
            except (Error, KeyError) as e:
                raise SpecterError(
                    f"Labels import failed. Check the import info box for the expected formats. Error: {e}"
                )
        # Convert labeled_addresses to arr (for AddressList.set_labels)
        arr = [
            {"address": address, "label": label}
            for address, label in labeled_addresses.items()
            if address in self._addresses
        ]
        logger.info(f"Array for set_labels is: {arr}")
        self._addresses.set_labels(arr)
        return len(arr)

    def update(self):
        self.getdata()
        self.update_balance()
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
            except Exception as e:
                handle_exception(e)
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
        if max_recv >= self.address_index:
            self.address = self.get_address(max_recv + 1, change=False)
            self.address_index = max_recv + 1
            updated = True
        if max_change >= self.change_index:
            self.change_address = self.get_address(max_change + 1, change=True)
            self.change_index = max_change + 1
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
        except Exception as e:
            logger.error(
                f"Could not construct a Wallet object from the data provided: {wallet_dict}. Reraise {e}"
            )
            raise e

        combined_descriptor = cls.merge_descriptors(recv_descriptor, change_descriptor)

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
            combined_descriptor,
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
        self.info = self.rpc.getwalletinfo()
        return self.info

    def check_utxo(self):
        try:
            # listunspent only lists not locked utxos
            # so we need to unlock, then list, then lock back
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
                tx["category"] = tx_data.get("category") or "send"
                if "locked" not in tx:
                    tx["locked"] = False
            self._full_utxo = sorted(utxo, key=lambda utxo: utxo["time"], reverse=True)
        except Exception as e:
            self._full_utxo = []
            raise SpecterError(f"Failed to load utxos, {e}")

    def getdata(self):
        self.fetch_transactions()
        self.check_utxo()
        self.get_info()
        # TODO: Should do the same for the non change address (?)
        # check if address was used already
        try:
            value_on_address = self.rpc.getreceivedbyaddress(self.change_address, 0)
        except Exception as e:
            handle_exception(e)
            # Could happen if address not in wallet (wallet was imported)
            # try adding keypool
            logger.info(
                f"Didn't get transactions on change address {self.change_address}. Refilling keypool."
            )
            self.keypoolrefill(0, end=self.keypool, change=False)
            self.keypoolrefill(0, end=self.change_keypool, change=True)
            value_on_address = 0

        # if it was - update change address and save
        if value_on_address > 0:
            self._addresses.set_used(self.change_address)
            self.change_index += 1
            self.change_address = self.get_address(self.change_index, change=True)
            self.save_to_file()

    @property
    def full_utxo(self):
        if hasattr(self, "_full_utxo"):
            return self._full_utxo
        else:
            self.check_utxo()
            return self._full_utxo

    @property
    def utxo(self):
        return [utxo for utxo in self._full_utxo if not utxo["locked"]]

    @property
    def locked_utxo(self):
        return [utxo for utxo in self._full_utxo if utxo["locked"]]

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
            # we still store two descriptors so it can directly copy-pasted from the file
            # and to maintain backward compatibility
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
            o["pending_psbts"] = self.pending_psbts_dict()
            o["frozen_utxo"] = self.frozen_utxo
            o["last_block"] = self.last_block
        return o

    def pending_psbts_dict(self):
        return {
            psbtid: psbtobj.to_dict() for psbtid, psbtobj in self.pending_psbts.items()
        }

    def save_to_file(self):
        write_json_file(self.to_json(), self.fullpath)
        self.update_balance()

    def delete_files(self):
        delete_file(self.fullpath)
        delete_file(self.fullpath + ".bkp")
        delete_file(self._addresses.path)
        delete_file(self._transactions.path)
        # the folder might not exist
        try:
            delete_folder(self._transactions.rawdir)
        except:
            pass

    @property
    def use_descriptors(self):
        if not self.info:
            self.get_info()
        return self.info.get("descriptors", False)

    @property
    def is_multisig(self):
        return len(self.keys) > 1

    @property
    def is_singlesig(self):
        return len(self.keys) == 1

    @property
    def keys_count(self):
        return len(self.keys)

    @property
    def locked_amount(self):
        """Deprecated, please use amount_locked_unsigned"""
        return self.amount_locked_unsigned

    def delete_spent_pending_psbts(self, txs: list):
        """
        Gets all inputs from the txs list (txid, vout),
        checks if pending psbts try to spent them,
        if so - unlocks other inputs and deletes these psbts.
        """
        # check if we have pending psbts
        if len(self.pending_psbts) == 0:
            return
        # make sure None didn't get here
        txs = [tx for tx in txs if tx is not None]
        # all inputs in transactions
        inputs = sum([self.TxCls.from_string(hextx).vin for hextx in txs], [])
        # all unique utxos spent in these transactions
        utxos = set([(vin.txid, vin.vout) for vin in inputs])
        # get psbt ids we need to delete
        psbtids = []
        for psbtid, psbt in self.pending_psbts.items():
            psbtutxos = [(inp.txid, inp.vout) for inp in psbt.inputs]
            for utxo in psbtutxos:
                if utxo in utxos:
                    psbtids.append(psbtid)
                    break
        if len(psbtids) > 0:
            for psbtid in psbtids:
                self.delete_pending_psbt(psbtid, save=False)
            self.save_to_file()

    def delete_pending_psbt(self, txid, save=True):
        if txid and txid in self.pending_psbts:
            try:
                self.rpc.lockunspent(True, self.pending_psbts[txid].utxo_dict())
            except Exception as e:
                # UTXO was spent
                logger.warning(str(e))
            del self.pending_psbts[txid]
            if save:
                self.save_to_file()

    def toggle_freeze_utxo(self, utxo_list):
        # utxo = ["txid:vout", "txid:vout"]
        utxo_list_done = []  # Preventing Duplicates server-side
        for utxo in utxo_list:
            if utxo in utxo_list_done:
                continue
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
                logger.info(f"Unfreeze {utxo}")
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
                logger.info(f"Freeze {utxo}")
                self.frozen_utxo.append(utxo)
            utxo_list_done.append(utxo)

        self.save_to_file()

    def update_pending_psbt(self, psbt, txid, raw):
        if txid not in self.pending_psbts:
            raise SpecterError("Can't find pending PSBT with this txid")

        cur_psbt = self.pending_psbts[txid]
        cur_psbt.update(psbt, raw)
        self.save_to_file()
        return cur_psbt.to_dict()

    def save_pending_psbt(self, psbt):
        self.pending_psbts[psbt.txid] = psbt
        try:
            self.rpc.lockunspent(False, psbt.utxo_dict())
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
        service_id: str = None,
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
                    tx["vsize"] = decoderawtransaction(rpc_tx["hex"]).get("vsize")

                if isinstance(tx["address"], str):
                    tx["label"] = self.getlabel(tx["address"])
                    addr_obj = self.get_address_obj(tx["address"])
                    if addr_obj and addr_obj.get("service_id"):
                        tx["service_id"] = addr_obj["service_id"]
                elif isinstance(tx["address"], list):
                    # TODO: Handle services integration w/batch txs
                    tx["label"] = [self.getlabel(address) for address in tx["address"]]
                else:
                    tx["label"] = None

                if service_id and (
                    "service_id" not in tx or tx["service_id"] != service_id
                ):
                    # We only want `service_id`-related txs returned
                    continue

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
        """rescans the utxo via a thread. internally calls _rescan_utxo_thread
        explorer: something like https://mempool.space/testnet/
        """
        delete_file(self._transactions.path)
        self.fetch_transactions()
        command = UtxoScanner(self, requests_session, explorer, only_tor)
        command.execute(asyncc=True)

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

    @property
    def rescan_progress(self):
        """Returns None if rescanblockchain is not launched,
        value between 0 and 1 otherwise
        """
        if not self.info.get("scanning", False):
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
            addr_obj = self.get_address_obj(address)
            if addr_obj["service_id"]:
                # Skip addresses reserved for a Service
                return self.getnewaddress(change, save)
            self.address = address
        if save:
            self.save_to_file()
        return address

    def get_address(self, index, change=False, check_keypool=True) -> str:
        if check_keypool:
            pool = self.change_keypool if change else self.keypool
            # logger.debug(
            #    f"get_address index={index} pool={pool} gapLIMIT={self.GAP_LIMIT} change={change} will_keypoolrefill={pool < index + self.GAP_LIMIT}"
            # )
            if pool < index + self.GAP_LIMIT:
                self.keypoolrefill(pool, index + self.GAP_LIMIT, change=change)
        return self.descriptor.derive(index, branch_index=int(change)).address(
            self.network
        )

    def get_address_obj(self, address: str) -> Address:
        return self._addresses.get(address)

    def derive_descriptor(self, index: int, change: bool, keep_xpubs=False):
        """
        Derives descriptor for receiving or change address with `index`.
        For sortedmulti descriptor also sorts keys.
        keep_xpubs=False will replace xpubs with sec-serialized pubkeys,
        keep_xpubs=True will fill derivation after xpub without actually deriving the key.
        In both cases keys are sorted as will appear in witness script.
        """
        branch = int(change)
        if keep_xpubs:
            # get receiving or change branch
            desc = self.descriptor.branch(branch)
            # sort keys
            if desc.is_basic_multisig and desc.is_sorted:
                args = desc.miniscript.args
                # sort by derived sec(), first arg is a threshold
                desc.miniscript.args = [args[0]] + sorted(
                    args[1:], key=lambda k: k.derive(index).sec()
                )
            # fill indexes in allowed derivations
            for k in desc.keys:
                k.allowed_derivation.indexes = k.allowed_derivation.fill(index)
        else:
            desc = self.descriptor.derive(index, branch_index=branch)
            # replace xpubs with pubkeys
            for k in desc.keys:
                k.key = k.key.get_public_key()
            # sort keys
            if desc.is_basic_multisig and desc.is_sorted:
                args = desc.miniscript.args
                desc.miniscript.args = [args[0]] + sorted(
                    args[1:], key=lambda k: k.sec()
                )
        return desc

    def get_descriptor(
        self,
        index=None,
        change=False,
        address=None,
        keep_xpubs=False,
        to_string=False,
        with_checksum=False,
    ):
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
        if not to_string:
            return self.derive_descriptor(index, change, keep_xpubs)
        else:
            desc_string = self.derive_descriptor(index, change, keep_xpubs).to_string()
            if with_checksum:
                return add_checksum(desc_string)
            else:
                return desc_string

    def get_address_info(self, address) -> Address:
        # TODO: This is a misleading name. This is really fetching an Address obj
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

    def update_balance(self):
        try:
            balance = (
                self.rpc.getbalances()["mine"]
                if self.use_descriptors
                else self.rpc.getbalances()["watchonly"]
            )
        except Exception as e:
            raise SpecterError(f"was not able to get wallet_balance because {e}")
        self.balance = balance
        return self.balance

    def keypoolrefill(self, start, end=None, change=False):
        if end is None:
            # end is ignored for descriptor wallets
            end = start + self.GAP_LIMIT
        if end - start < self.GAP_LIMIT:
            # avoid too many calls
            end = start + self.GAP_LIMIT * 2

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
            logger.warning(f"Error while calculating addresses: {e}")

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

    def associate_address_with_service(
        self, address: str, service_id: str, label: str, autosave: bool = True
    ):
        """
        Links the Address to the specified Service.id
        """
        self._addresses.associate_with_service(
            address=address, service_id=service_id, label=label, autosave=autosave
        )

    def deassociate_address(self, address: str, autosave: bool = True):
        """
        Clears any Service associations on the Address.
        """
        self._addresses.deassociate(address=address, autosave=autosave)

    def get_associated_addresses(
        self, service_id: str, unused_only: bool = False
    ) -> List[Address]:
        """
        Return the Wallet's Address objs that are associated with the specified Service.id
        """
        addrs = []
        for addr, addr_obj in self._addresses.items():
            if addr_obj["service_id"] == service_id:
                if not unused_only or not addr_obj["used"]:
                    addrs.append(addr_obj)
        return addrs

    def setlabel(self, address, label):
        self._addresses.set_label(address, label)

    def getlabel(self, address):
        # TODO: This is confusing. The Address["label"] attr may be blank but the
        # Address.label property will auto-populate a value (e.g. "Address #4").
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
    def amount_confirmed(self):
        """Confirmed outputs (and outputs created by the wallet for Bitcoin Core Hot Wallets)"""
        return round(self.balance["trusted"], 8)

    @property
    def amount_unconfirmed(self):
        """Unconfirmed outputs"""
        return round(self.balance["untrusted_pending"], 8)

    @property
    def amount_frozen(self):
        """Only frozen outputs, no outputs locked in unsigned PSBTS"""
        amount = 0
        frozen_txid = [utxo.split(":")[0] for utxo in self.frozen_utxo]
        for utxo in self.locked_utxo:
            if utxo["txid"] in frozen_txid:
                amount += utxo["amount"]
        return amount

    @property
    def amount_locked_unsigned(self):
        """Outputs locked in unsigned PSBTs"""
        amount = 0
        for psbt in self.pending_psbts.values():
            amount += sum([inp.float_amount for inp in psbt.inputs])
        return amount

    @property
    def amount_immature(self):
        """Immature coinbase outputs"""
        return round(self.balance["immature"], 8)

    @property
    def amount_total(self):
        """All outputs, including unconfirmed outputs, except for immature outputs"""
        return self.amount_confirmed + self.amount_unconfirmed

    @property
    def amount_available(self):
        """All outputs minus UTXO locked in unsigned transactions and frozen outputs"""
        return self.amount_total - self.amount_locked_unsigned - self.amount_frozen

    @property
    def fullbalance(self):
        """Deprecated, please use amount_total"""
        balance = self.balance
        return round(balance["trusted"], 8)

    @property
    def full_available_balance(self):
        """Deprecated, please use amount_available"""
        return round(self.balance["trusted"] + self.balance["untrusted_pending"], 8)

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
        addresses: List[str],
        amounts: List[float],
        subtract: bool = False,
        subtract_from: int = 0,
        fee_rate: float = 0,  # fee rate to use, if less than MIN_FEE_RATE will use MIN_FEE_RATE, 0 for automatic
        selected_coins=[],  # list of dicts [{"txid": txid, "vout": vout}]
        readonly=False,  # fee estimation
        rbf=True,
        rbf_edit_mode=False,
    ):
        """
        fee_rate: in sat/B or BTC/kB. If set to 0 Bitcoin Core sets feeRate automatically.
        """
        if fee_rate != 0 and fee_rate < self.MIN_FEE_RATE:
            fee_rate = self.MIN_FEE_RATE

        options = {"includeWatching": True, "replaceable": rbf}
        extra_inputs = []
        total_btc = round(sum(amounts), 8)
        total_sats = round(sum(amounts) * 1e8)

        # if creating new tx - check we have enough balance
        if not rbf_edit_mode and self.amount_available < total_btc:
            raise SpecterError(
                f"Wallet {self.name} does not have sufficient funds to make the transaction."
            )

        if selected_coins:
            # check we have enough balance in selected coins
            sats_in_coins = sum(
                [
                    self._transactions.getfetch(coin["txid"])
                    .tx.vout[coin["vout"]]
                    .value
                    for coin in selected_coins
                ]
            )
            if sats_in_coins < total_sats:
                raise SpecterError(
                    "Selected coins do not cover full amount. Please select more coins!"
                )
            extra_inputs = selected_coins

        elif self.balance["trusted"] <= total_btc:
            # if we don't have enough in confirmed txs - add unconfirmed outputs
            txlist = self.rpc.listunspent(0, 0)
            b = total_btc - self.balance["trusted"]
            for tx in txlist:
                extra_inputs.append({"txid": tx["txid"], "vout": int(tx["vout"])})
                b -= tx["amount"]
                if b < 0:
                    break

        # subtract fee from amount of this output:
        subtract_arr = [subtract_from] if subtract else []

        options.update(
            {
                "changeAddress": self.change_address,
                "subtractFeeFromOutputs": subtract_arr,
            }
        )

        if self.manager.bitcoin_core_version_raw >= 210000:
            options["add_inputs"] = not selected_coins

        if fee_rate > 0:
            # bitcoin core needs us to convert sat/B to BTC/kB
            options["feeRate"] = round((fee_rate * 1000) / 1e8, 8)

        try:
            locktime = min([tip["height"] for tip in self.rpc.getchaintips()])
        except:
            locktime = 0

        # first run to get estimate
        r = self.rpc.walletcreatefundedpsbt(
            extra_inputs,  # inputs
            [{addresses[i]: amounts[i]} for i in range(len(addresses))],  # outputs
            locktime,
            options,
            True,  # bip32-der
        )

        b64psbt = r["psbt"]
        psbt = self.PSBTCls(
            b64psbt,
            self.descriptor,
            self.network,
            devices=list(zip(self.keys, self._devices)),
        )

        # Core's fee rate is wrong so we need to "adjust" it
        if fee_rate > 0:
            # scale by which Core misses the fee rate
            scale = fee_rate / psbt.fee_rate
            adjusted_fee_rate = fee_rate * scale
            options["feeRate"] = round((adjusted_fee_rate * 1000) / 1e8, 8)

            r = self.rpc.walletcreatefundedpsbt(
                extra_inputs,  # inputs
                [{addresses[i]: amounts[i]} for i in range(len(addresses))],  # outputs
                locktime,
                options,
                True,  # bip32-der
            )

            b64psbt = r["psbt"]
            psbt = self.PSBTCls(
                b64psbt,
                self.descriptor,
                self.network,
                devices=list(zip(self.keys, self._devices)),
            )

        if not readonly:
            self.save_pending_psbt(psbt)
        return psbt.to_dict()

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
            }
            for utxo in rbf_utxo
        ]

    def decode_tx(self, txid):
        psbt = self.psbt_from_txid(txid)
        outputs = [out for out in psbt.outputs if not out.is_change]
        return {
            "addresses": [out.address for out in outputs],
            "amounts": [out.float_amount for out in outputs],
            "used_utxo": psbt.utxo_dict(),
        }

    def psbt_from_txid(self, txid):
        """Converts a transaction with txid to PSBT instance"""
        raw_tx = self.gettransaction(txid)["hex"]
        # fill derivation info
        raw_psbt = self.rpc.utxoupdatepsbt(
            self.rpc.converttopsbt(raw_tx, True),
            [self.recv_descriptor, self.change_descriptor],
        )
        return self.PSBTCls(
            raw_psbt,
            self.descriptor,
            self.network,
            devices=list(zip(self.keys, self._devices)),
        )

    def canceltx(self, txid, fee_rate):
        self.check_unused()
        psbt = self.psbt_from_txid(txid)
        # find change output
        change_index = None
        for i, out in enumerate(psbt.outputs):
            if out.is_change:
                change_index = i
                break
        sum_outputs = sum([out.value for out in psbt.psbt.outputs])
        old_fee = psbt.fee
        if change_index is not None:
            change_out = psbt.psbt.outputs[change_index]
        else:
            # create fresh output and replace script_pubkey in output
            desc = self.descriptor.branch(1).derive(self.change_index)
            change_out = psbt.psbt.PSBTOUT_CLS(vout=psbt.psbt.outputs[0].vout)
            change_out.script_pubkey = desc.script_pubkey()
            self.PSBTCls.fill_output(change_out, desc)
        # set new value - everything to us
        change_out.value = sum_outputs
        # set new outputs in psbt - only us
        psbt.psbt.outputs = [change_out]
        # how much we need to subtract?
        fee_delta = psbt.full_size * fee_rate - old_fee
        # we must use larger fees by at least the txsize * min
        if fee_delta < psbt.full_size * self.MIN_FEE_RATE:
            fee_delta = psbt.full_size * self.MIN_FEE_RATE
        if change_out.value <= round(fee_delta):
            raise SpecterError("Not enough funds in the transaction")
        change_out.value -= round(fee_delta)
        # fill derivation info
        self.save_pending_psbt(psbt)
        return psbt.to_dict()

    def bumpfee(self, txid, fee_rate):
        psbt = self.psbt_from_txid(txid)
        fee_delta = fee_rate * psbt.full_size - psbt.fee
        if fee_delta < self.MIN_FEE_RATE * psbt.full_size:
            raise SpecterError(
                "Fee difference is too small to relay the RBF transaction"
            )
        # find change output
        change_index = None
        for i, out in enumerate(psbt.outputs):
            if out.is_change:
                change_index = i
                break
        if change_index is None:
            raise SpecterError("Can't bump fee in a transaction without change outputs")
        psbt.psbt.outputs[i].value -= round(fee_delta)
        if psbt.psbt.outputs[i].value <= 0:
            # if we went negative - just drop the change output
            psbt.psbt.outputs.remove(psbt.psbt.outputs[i])
        self.save_pending_psbt(psbt)
        return psbt.to_dict()

    @property
    def is_taproot(self):
        return self.descriptor.is_taproot

    def fill_psbt(
        self,
        b64psbt,
        non_witness: bool = True,
        xpubs: bool = True,
        taproot_derivations: bool = False,
    ):
        psbt = self.PSBTCls.from_string(b64psbt)

        # Core doesn't fill derivations yet, so we do it ourselves
        if taproot_derivations and self.is_taproot:

            net = self.network
            for sc in psbt.inputs + psbt.outputs:
                addr = sc.script_pubkey.address(net)
                info = self._addresses.get(addr)
                if info and not info.is_external:
                    d = self.descriptor.derive(
                        info.index, branch_index=int(info.change)
                    )
                    for k in d.keys:
                        sc.bip32_derivations[PublicKey.parse(k.sec())] = DerivationPath(
                            k.origin.fingerprint, k.origin.derivation
                        )

        if non_witness:
            for inp in psbt.inputs:
                # we don't need to fill what is already filled
                if inp.non_witness_utxo is not None:
                    continue
                txid = inp.txid.hex()
                try:
                    res = self.gettransaction(txid)
                    inp.non_witness_utxo = self.TxCls.from_string(res["hex"])
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
        # TODO: check if some of the inputs are already locked
        psbt = self.PSBTCls(
            b64psbt,
            self.descriptor,
            self.network,
            devices=list(zip(self.keys, self._devices)),
        )
        raw = self.rpc.finalizepsbt(b64psbt)
        if "hex" in raw:
            psbt.update(None, raw)

        self.save_pending_psbt(psbt)
        return psbt.to_dict()

    def addresses_info(
        self,
        is_change: bool = False,
        service_id: str = None,
        include_wallet_alias: bool = False,
    ):
        """Create a list of (receive or change) addresses from cache and retrieve the
        related UTXO and amount.
        Parameters:
            * is_change: if true, return the change addresses else the receive ones.
            * service_id: just return addresses associated for the given Service
            * include_wallet_alias: adds `wallet_alias` to each output (useful when this
                is called by WalletManager.full_addresses_info() across all Wallets)
        """

        addresses_info = []

        addresses_cache = [
            v for _, v in self._addresses.items() if v.change == is_change and v.is_mine
        ]

        for addr in addresses_cache:
            addr_utxo = 0
            addr_amount = 0

            for utxo in [
                utxo for utxo in self._full_utxo if utxo["address"] == addr.address
            ]:
                addr_amount = addr_amount + utxo["amount"]
                addr_utxo = addr_utxo + 1

            if service_id and (
                "service_id" not in addr or addr["service_id"] != service_id
            ):
                # Filter this address out
                continue

            addr_info = {
                "index": addr.index,
                "address": addr.address,
                "label": addr.label,
                "amount": addr_amount,
                "used": bool(addr.used),
                "utxo": addr_utxo,
                "type": "change" if is_change else "receive",
                "service_id": addr.service_id,
            }
            if include_wallet_alias:
                addr_info["wallet_alias"] = self.alias

            addresses_info.append(addr_info)

        return addresses_info

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name } alias={self.alias}>"
