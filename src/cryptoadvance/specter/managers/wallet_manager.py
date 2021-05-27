import json
import logging
import os
import pathlib
import shutil
import threading
import traceback
import hashlib
from collections import OrderedDict
from io import BytesIO

from ..helpers import alias, load_jsons, is_liquid
from ..persistence import delete_file, delete_folder
from ..rpc import RpcError, get_default_datadir
from ..specter_error import SpecterError
from ..util.descriptor import AddChecksum
from ..wallet import Wallet

from embit import ec
from embit.descriptor import Descriptor
from embit.liquid.descriptor import LDescriptor
from embit.descriptor.checksum import add_checksum

from embit import ec
from embit.descriptor import Descriptor
from embit.liquid.descriptor import LDescriptor
from embit.descriptor.checksum import add_checksum

from embit import ec
from embit.descriptor import Descriptor
from embit.liquid.descriptor import LDescriptor
from embit.descriptor.checksum import add_checksum

logger = logging.getLogger(__name__)

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


class WalletManager:
    # chain is required to manage wallets when bitcoind is not running
    def __init__(
        self,
        bitcoin_core_version_raw,
        data_folder,
        rpc,
        chain,
        device_manager,
        path="specter",
        allow_threading=True,
    ):
        self.data_folder = data_folder
        self.chain = chain
        self.rpc = rpc
        self.rpc_path = path
        self.device_manager = device_manager
        self.is_loading = False
        self.wallets = {}
        self.wallets_update_list = []
        self.failed_load_wallets = []
        self.bitcoin_core_version_raw = bitcoin_core_version_raw
        self.allow_threading = allow_threading
        self.update(data_folder, rpc, chain)

    def update(self, data_folder=None, rpc=None, chain=None):
        if self.is_loading:
            return
        self.is_loading = True
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
            pathlib.Path(self.working_folder).mkdir(parents=True, exist_ok=True)
        if rpc is not None:
            self.rpc = rpc
        self.wallets_update_list = {}
        if self.working_folder is not None and self.rpc is not None:
            wallets_files = load_jsons(self.working_folder, key="name")
            for wallet in wallets_files:
                wallet_name = wallets_files[wallet]["name"]
                self.wallets_update_list[wallet_name] = wallets_files[wallet]
                self.wallets_update_list[wallet_name]["is_multisig"] = (
                    len(wallets_files[wallet]["keys"]) > 1
                )
                self.wallets_update_list[wallet_name]["keys_count"] = len(
                    wallets_files[wallet]["keys"]
                )
            # remove irrelevant wallets
            for k in list(self.wallets.keys()):
                if k not in self.wallets_update_list:
                    self.wallets.pop(k)
            if self.allow_threading:
                t = threading.Thread(
                    target=self._update,
                    args=(
                        data_folder,
                        rpc,
                        chain,
                    ),
                )
                t.start()
            else:
                self._update(data_folder, rpc, chain)
        else:
            self.is_loading = False
            logger.info(
                "Specter seems to be disconnected from Bitcoin Core. Skipping wallets update."
            )

    def _update(self, data_folder=None, rpc=None, chain=None):
        # list of wallets in the dict
        existing_names = list(self.wallets.keys())
        # list of wallet to keep
        self.failed_load_wallets = []
        try:
            if self.wallets_update_list:
                loaded_wallets = self.rpc.listwallets()
                logger.info("Getting loaded wallets list from Bitcoin Core")
                for wallet in self.wallets_update_list:
                    wallet_alias = self.wallets_update_list[wallet]["alias"]
                    wallet_name = self.wallets_update_list[wallet]["name"]
                    if os.path.join(self.rpc_path, wallet_alias) not in loaded_wallets:
                        try:
                            logger.info(
                                "Loading %s to Bitcoin Core"
                                % self.wallets_update_list[wallet]["alias"]
                            )
                            self.rpc.loadwallet(
                                os.path.join(self.rpc_path, wallet_alias)
                            )
                            logger.info(
                                "Initializing %s Wallet object"
                                % self.wallets_update_list[wallet]["alias"]
                            )
                            loaded_wallet = Wallet.from_json(
                                self.wallets_update_list[wallet],
                                self.device_manager,
                                self,
                            )
                            if not loaded_wallet:
                                raise Exception("Failed to load wallet")
                            # Lock UTXO of pending PSBTs
                            logger.info(
                                "Re-locking UTXOs of wallet %s"
                                % self.wallets_update_list[wallet]["alias"]
                            )
                            if len(loaded_wallet.pending_psbts) > 0:
                                for psbt in loaded_wallet.pending_psbts:
                                    logger.info(
                                        "lock %s " % wallet_alias,
                                        loaded_wallet.pending_psbts[psbt]["tx"]["vin"],
                                    )
                                    loaded_wallet.rpc.lockunspent(
                                        False,
                                        [
                                            utxo
                                            for utxo in loaded_wallet.pending_psbts[
                                                psbt
                                            ]["tx"]["vin"]
                                        ],
                                    )
                            if len(loaded_wallet.frozen_utxo) > 0:
                                loaded_wallet.rpc.lockunspent(
                                    False,
                                    [
                                        {
                                            "txid": utxo.split(":")[0],
                                            "vout": int(utxo.split(":")[1]),
                                        }
                                        for utxo in loaded_wallet.frozen_utxo
                                    ],
                                )
                            self.wallets[wallet_name] = loaded_wallet
                            logger.info(
                                "Finished loading wallet into Bitcoin Core and Specter: %s"
                                % self.wallets_update_list[wallet]["alias"]
                            )
                        except RpcError as e:
                            logger.warning(
                                f"Couldn't load wallet {wallet_alias} into core. Silently ignored! RPC error: {e}"
                            )
                            self.failed_load_wallets.append(
                                {
                                    **self.wallets_update_list[wallet],
                                    "loading_error": str(e).replace("'", ""),
                                }
                            )
                        except Exception as e:
                            logger.warning(
                                f"Couldn't load wallet {wallet_alias}. Silently ignored! Wallet error: {e}"
                            )
                            self.failed_load_wallets.append(
                                {
                                    **self.wallets_update_list[wallet],
                                    "loading_error": str(e).replace("'", ""),
                                }
                            )
                    else:
                        if wallet_name not in existing_names:
                            # ok wallet is already there
                            # we only need to update
                            try:
                                logger.info(
                                    "Wallet already loaded in Bitcoin Core. Initializing %s Wallet object"
                                    % self.wallets_update_list[wallet]["alias"]
                                )
                                loaded_wallet = Wallet.from_json(
                                    self.wallets_update_list[wallet],
                                    self.device_manager,
                                    self,
                                )
                                if loaded_wallet:
                                    self.wallets[wallet_name] = loaded_wallet
                                    logger.info(
                                        "Finished loading wallet into Specter: %s"
                                        % self.wallets_update_list[wallet]["alias"]
                                    )
                                else:
                                    raise Exception("Failed to load wallet")
                            except Exception as e:
                                logger.warning(
                                    f"Failed to load wallet {wallet_name}: {e}"
                                )
                                logger.warning(traceback.format_exc())
                                self.failed_load_wallets.append(
                                    {
                                        **self.wallets_update_list[wallet],
                                        "loading_error": str(e).replace("'", ""),
                                    }
                                )
                        else:
                            # wallet is loaded and should stay
                            logger.info(
                                "Wallet already in Specter, updating wallet: %s"
                                % self.wallets_update_list[wallet]["alias"]
                            )
                            self.wallets[wallet_name].update()
                            logger.info(
                                "Finished updating wallet:  %s"
                                % self.wallets_update_list[wallet]["alias"]
                            )
                            # TODO: check wallet file didn't change
        # only ignore rpc errors
        except RpcError as e:
            logger.error(f"Failed updating wallet manager. RPC error: {e}")
        logger.info("Done updating wallet manager")
        self.wallets_update_list = {}
        self.is_loading = False

    def get_by_alias(self, alias):
        for wallet_name in self.wallets:
            if self.wallets[wallet_name] and self.wallets[wallet_name].alias == alias:
                return self.wallets[wallet_name]
        raise SpecterError("Wallet %s does not exist!" % alias)

    @property
    def wallets_names(self):
        return sorted(self.wallets.keys())

    def create_wallet(self, name, sigs_required, key_type, keys, devices):
        try:
            walletsindir = [
                wallet["name"] for wallet in self.rpc.listwalletdir()["wallets"]
            ]
        except:
            walletsindir = []
        wallet_alias = alias(name)
        i = 2
        while (
            os.path.isfile(os.path.join(self.working_folder, "%s.json" % wallet_alias))
            or os.path.join(self.rpc_path, wallet_alias) in walletsindir
        ):
            wallet_alias = alias("%s %d" % (name, i))
            i += 1

        arr = key_type.split("-")
        descs = [key.metadata["combined"] for key in keys]
        recv_descs = ["%s/0/*" % desc for desc in descs]
        change_descs = ["%s/1/*" % desc for desc in descs]
        if len(keys) > 1:
            recv_descriptor = "sortedmulti({},{})".format(
                sigs_required, ",".join(recv_descs)
            )
            change_descriptor = "sortedmulti({},{})".format(
                sigs_required, ",".join(change_descs)
            )
        else:
            recv_descriptor = recv_descs[0]
            change_descriptor = change_descs[0]
        for el in arr[::-1]:
            recv_descriptor = "%s(%s)" % (el, recv_descriptor)
            change_descriptor = "%s(%s)" % (el, change_descriptor)

        if is_liquid(self.chain):
            blinding_key = ""
            if len(devices) == 1:
                blinding_key = devices[0].blinding_key
            if not blinding_key:
                desc = Descriptor.from_string(recv_descriptor.split("#")[0])
                # For now we use sha256(b"blinding_key", xor(chaincodes)) as a blinding key
                # where chaincodes are corresponding to xpub of the first receiving address
                xor = bytearray(32)
                desc_keys = desc.derive(0).keys
                for k in desc_keys:
                    if k.is_extended:
                        chaincode = k.key.chain_code
                        for i in range(32):
                            xor[i] = xor[i] ^ chaincode[i]
                secret = hashlib.sha256(b"blinding_key" + bytes(xor)).digest()
                blinding_key = ec.PrivateKey(secret).wif()
            recv_descriptor = f"blinded(slip77({blinding_key}),{recv_descriptor})"
            change_descriptor = f"blinded(slip77({blinding_key}),{change_descriptor})"

        recv_descriptor = AddChecksum(recv_descriptor)
        change_descriptor = AddChecksum(change_descriptor)

        # v20.99 is pre-v21 Elements Core for descriptors
        if self.bitcoin_core_version_raw >= 209900:
            # Use descriptor wallet
            self.rpc.createwallet(
                os.path.join(self.rpc_path, wallet_alias), True, True, "", False, True
            )
        else:
            self.rpc.createwallet(os.path.join(self.rpc_path, wallet_alias), True)

        w = Wallet(
            name,
            wallet_alias,
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
            os.path.join(self.working_folder, "%s.json" % wallet_alias),
            self.device_manager,
            self,
        )
        # save wallet file to disk
        if w and self.working_folder is not None:
            w.save_to_file()
        # get Wallet class instance
        if w:
            self.wallets[name] = w
            return w
        else:
            raise ("Failed to create new wallet")

    def delete_wallet(
        self, wallet, bitcoin_datadir=get_default_datadir(), chain="main"
    ):
        logger.info("Deleting {}".format(wallet.alias))
        wallet_rpc_path = os.path.join(self.rpc_path, wallet.alias)
        self.rpc.unloadwallet(wallet_rpc_path)
        # Try deleting wallet folder
        if bitcoin_datadir:
            if chain != "main":
                bitcoin_datadir = os.path.join(bitcoin_datadir, chain)
            candidates = [
                os.path.join(bitcoin_datadir, wallet_rpc_path),
                os.path.join(bitcoin_datadir, "wallets", wallet_rpc_path),
            ]
            for path in candidates:
                if os.path.exists(path):
                    shutil.rmtree(path)
                    break
        # Delete files
        wallet.delete_files()
        del self.wallets[wallet.name]
        self.update()

    def rename_wallet(self, wallet, name):
        logger.info("Renaming {}".format(wallet.alias))
        wallet.name = name
        if self.working_folder is not None:
            wallet.save_to_file()
        self.update()

    def full_txlist(
        self,
        fetch_transactions=True,
        validate_merkle_proofs=False,
        current_blockheight=None,
    ):
        """Returns a list of all transactions in all wallets loaded in the wallet_manager.
        #Parameters:
        #    fetch_transactions (bool): Update the TxList CSV caching by fetching transactions from the Bitcoin RPC
        #    validate_merkle_proofs (bool): Return transactions with validated_blockhash
        #    current_blockheight (int): Current blockheight for calculating confirmations number (None will fetch the block count from the RPC)
        """
        txlists = [
            [
                {**tx, "wallet_alias": wallet.alias}
                for tx in wallet.txlist(
                    fetch_transactions=fetch_transactions,
                    validate_merkle_proofs=validate_merkle_proofs,
                    current_blockheight=current_blockheight,
                )
            ]
            for wallet in self.wallets.values()
        ]
        result = []
        for txlist in txlists:
            for tx in txlist:
                result.append(tx)
        return list(reversed(sorted(result, key=lambda tx: tx["time"])))

    def full_utxo(self):
        """Returns a list of all UTXOs in all wallets loaded in the wallet_manager."""
        txlists = [
            [
                {
                    **utxo,
                    "label": wallet.getlabel(utxo["address"]),
                    "wallet_alias": wallet.alias,
                }
                for utxo in wallet.full_utxo
            ]
            for wallet in self.wallets.values()
        ]
        result = []
        for txlist in txlists:
            for tx in txlist:
                result.append(tx)
        return list(reversed(sorted(result, key=lambda tx: tx["time"])))

    def delete(self, specter):
        """Deletes all the wallets"""
        for w in list(self.wallets.keys()):
            wallet = self.wallets[w]
            self.delete_wallet(wallet, specter.bitcoin_datadir, specter.chain)
        delete_folder(self.data_folder)
