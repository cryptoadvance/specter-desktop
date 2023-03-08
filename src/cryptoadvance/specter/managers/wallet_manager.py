import logging
from datetime import datetime
import os
import sys
import pathlib
import sys

from typing import Dict, List
from flask_babel import lazy_gettext as _
from flask import copy_current_request_context
from cryptoadvance.specter.rpc import BitcoinRPC
from cryptoadvance.specter.key import Key

from ..helpers import add_dicts, alias, is_liquid, load_jsons
from ..liquid.wallet import LWallet
from ..persistence import delete_folder
from ..rpc import RpcError, get_default_datadir, BrokenCoreConnectionException
from ..specter_error import SpecterError, SpecterInternalException, handle_exception
from ..util.flask import FlaskThread
from ..wallet import (  # TODO: `purposes` unused here, but other files rely on this import
    Wallet,
    purposes,
)


logger = logging.getLogger(__name__)


class WalletManager:
    """Manages Wallets. Depending on the chain"""

    # chain is required to manage wallets when bitcoind is not running
    def __init__(
        self,
        data_folder,
        rpc,
        chain,
        device_manager,
        path="specter",
        allow_threading_for_testing=False,
    ):
        self.data_folder = data_folder
        self.chain = chain
        self.rpcs = {}
        self.rpc = rpc
        self.rpc_path = path
        self.device_manager = device_manager
        # sort of lock to prevent threads to update in parallel
        self.is_loading = False
        # key is the name of the wallet, value is the actual instance

        self.wallets = {}
        self.allow_threading_for_testing = allow_threading_for_testing
        # define different wallet classes for liquid and bitcoin
        self.WalletClass = LWallet if is_liquid(chain) else Wallet
        self.update(data_folder, rpc, chain)

    def update(
        self,
        data_folder: str = None,
        rpc: BitcoinRPC = None,
        chain: str = None,
        use_threading=True,
        comment="",
    ):
        """Restructures the instance, specifically if chain/rpc changed
        The _update internal method will resync the internal status with Bitcoin Core
        use_threading : for the _update method which is heavily communicating with Bitcoin Core
        """
        logger.debug(
            f"starting update of wallet_manager (threading: {use_threading} , comment: {comment})"
        )
        if self.is_loading:
            logger.debug("update in progress, aborting!")
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
                os.makedirs(data_folder, exist_ok=True)
        if rpc is not None and rpc.test_connection():
            self.rpc = rpc
        else:
            if rpc:
                logger.error(
                    f"Prevented trying to update Wallet Manager with broken {rpc}"
                )
        # wallets_update_list is something like:
        # {'Specter': {'name': 'Specter', 'alias': 'pacman', ... }, 'another_wallet': { ... } }
        # It contains the same data as the JSON on disk
        wallets_update_list = {}

        if self.working_folder is not None:
            wallets_files = load_jsons(self.working_folder, key="name")
            logger.info(
                f"Iterating over {len(wallets_files.values())} wallet files in {self.working_folder}"
            )
            for wallet in wallets_files:
                wallet_name = wallets_files[wallet]["name"]
                wallets_update_list[wallet_name] = wallets_files[wallet]
                wallets_update_list[wallet_name]["is_multisig"] = (
                    len(wallets_files[wallet]["keys"]) > 1
                )
                wallets_update_list[wallet_name]["keys_count"] = len(
                    wallets_files[wallet]["keys"]
                )
        else:
            logger.info(
                f"Skipping further update because self.working_folder is {self.working_folder} (and data_folder = {self.data_folder})"
            )
        if (
            self.working_folder is not None
            and self.rpc is not None
            and self.chain is not None
        ):
            if "pytest" in sys.modules:
                if self.allow_threading_for_testing:
                    logger.info("Using threads in updating the wallet manager.")
                    t = FlaskThread(
                        target=self._update,
                        args=(wallets_update_list,),
                    )
                    t.start()
                else:
                    logger.info("Not using threads in updating the wallet manager.")
                    self._update(wallets_update_list)
            else:
                if use_threading:
                    logger.info("Using threads in updating the wallet manager.")
                    t = FlaskThread(
                        target=self._update,
                        args=(wallets_update_list,),
                    )

                    t.start()
                else:
                    logger.info("Not using threads in updating the wallet manager.")
                    self._update(wallets_update_list)
        else:
            self.is_loading = False
            logger.warning(
                "Specter seems to be disconnected from Bitcoin Core. Skipping wallets update."
            )

    def _update(self, wallets_update_list: Dict):
        """Effectively a three way sync. The three data sources are:
        * the json on disk (wallets_update_list)
        * the current wallet instances (existing_names)
        * the loaded wallets from Bitcoin Core (loaded_wallets)
        So, if we have data on disk
        * we get a list of loaded wallets from Bitcoin Core
        * the unloaded wallets are loaded in Bitcoin Core
        * and, on the Specter side, the wallet objects of those unloaded wallets are reinitialised
        """
        logger.info(
            f"Started updating wallets with {len(wallets_update_list.values())} wallets"
        )
        timestamp = datetime.now()
        # list of wallets in the dict
        existing_names = list(self.wallets.keys())
        # list of wallet to keep
        self._failed_load_wallets = []
        try:
            if wallets_update_list:
                loaded_wallets = self.rpc.listwallets()
                for wallet in wallets_update_list:

                    wallet_alias = wallets_update_list[wallet]["alias"]
                    wallet_name = wallets_update_list[wallet]["name"]
                    logger.info(f"Updating wallet {wallet_name}")
                    # wallet from json not yet loaded in Bitcoin Core?!
                    if os.path.join(self.rpc_path, wallet_alias) not in loaded_wallets:
                        try:
                            logger.debug(f"Loading {wallet_name} to Bitcoin Core")
                            self.rpc.loadwallet(
                                os.path.join(self.rpc_path, wallet_alias)
                            )
                            logger.debug("Initializing {wallet_name} Wallet object")
                            loaded_wallet = self.WalletClass.from_json(
                                wallets_update_list[wallet],
                                self.device_manager,
                                self,
                            )
                            # Lock UTXO of pending PSBTs
                            logger.debug(
                                "Re-locking UTXOs of wallet %s"
                                % wallets_update_list[wallet]["alias"]
                            )
                            if len(loaded_wallet.pending_psbts) > 0:
                                for psbt in loaded_wallet.pending_psbts:
                                    logger.info(
                                        f"lock {wallet_alias} {loaded_wallet.pending_psbts[psbt].utxo_dict()}"
                                    )
                                    loaded_wallet.rpc.lockunspent(
                                        False,
                                        loaded_wallet.pending_psbts[psbt].utxo_dict(),
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
                            # logger.info(
                            #     "Finished loading wallet into Bitcoin Core and Specter: %s"
                            #     % wallets_update_list[wallet]["alias"]
                            # )
                        except RpcError as e:
                            logger.warning(
                                f"Couldn't load wallet {wallet_alias} into Bitcoin Core. Silently ignored! RPC error: {e}"
                            )
                            self._failed_load_wallets.append(
                                {
                                    **wallets_update_list[wallet],
                                    "loading_error": str(e).replace("'", ""),
                                }
                            )
                        except Exception as e:
                            logger.warning(
                                f"Couldn't load wallet {wallet_alias}. Silently ignored! Wallet error: {e}"
                            )
                            logger.exception(e)
                            self._failed_load_wallets.append(
                                {
                                    **wallets_update_list[wallet],
                                    "loading_error": str(e).replace("'", ""),
                                }
                            )
                    else:
                        if wallet_name not in existing_names:
                            # ok wallet is not yet in the dict, create one
                            try:
                                loaded_wallet = self.WalletClass.from_json(
                                    wallets_update_list[wallet],
                                    self.device_manager,
                                    self,
                                )
                                self.wallets[wallet_name] = loaded_wallet
                            except Exception as e:
                                logger.exception(e)
                                self._failed_load_wallets.append(
                                    {
                                        **wallets_update_list[wallet],
                                        "loading_error": str(e).replace("'", ""),
                                    }
                                )
                        else:
                            # Wallet is already there
                            # we only need to update
                            self.wallets[wallet_name].update()
        # only ignore rpc errors
        except RpcError as e:
            logger.error(f"Failed updating wallet manager. RPC error: {e}")
        finally:
            self.is_loading = False
            timediff_ms = int((datetime.now() - timestamp).total_seconds() * 1000)
            logger.info(
                "Updating wallet manager done in {: >5}ms. Result:".format(timediff_ms)
            )
            logger.info(f"  * loaded_wallets: {len(self.wallets)}")
            logger.info(f"  * failed_load_wallets: {len(self._failed_load_wallets)}")
            for wallet in self._failed_load_wallets:
                logger.info(f"    * {wallet['name']} : {wallet['loading_error']}")

    def get_by_alias(self, alias):
        for wallet_name in self.wallets:
            if self.wallets[wallet_name] and self.wallets[wallet_name].alias == alias:
                return self.wallets[wallet_name]
        raise SpecterError(
            "Wallet %s could not be loaded. Are you connected with Bitcoin Core?"
            % alias
        )

    @property
    def failed_load_wallets(self) -> list:
        """A list of wallets failed where not loaded"""
        if not hasattr(self, "_failed_load_wallets"):
            self._failed_load_wallets = []
        return self._failed_load_wallets

    @property
    def working_folder(self):
        if self.data_folder is None or self.chain is None:
            return None
        working_folder = os.path.join(self.data_folder, self.chain)
        pathlib.Path(working_folder).mkdir(parents=True, exist_ok=True)
        return working_folder

    @property
    def wallets_names(self) -> List:
        return sorted(self.wallets.keys())

    @property
    def wallets_aliases(self) -> List:
        return [wallet.alias for wallet in self.wallets.values()]

    @property
    def rpc(self):
        """returns a BitcoinRpc depending on the chain"""
        return self.rpcs[self.chain]

    @rpc.setter
    def rpc(self, value):
        """sets a BitcoinRpc depending on the chain. This is an internal property. Don't use it from outside. ToDo: Refactor"""
        self.rpcs[self.chain] = value

    @property
    def wallets(self) -> Dict[str, Dict]:
        """returns wallets depending on the chain"""
        if not hasattr(self, "_wallets"):
            self._wallets = {}
        if not self._wallets.get(self.chain):
            self._wallets[self.chain] = {}
        # _wallets should look like something:
        # { "regtest" : {
        #       "wallet_name_1": {...},
        #       "wallet_name_2": {...},
        #    },
        #   "main": ...
        # }}
        return self._wallets[self.chain]

    @wallets.setter
    def wallets(self, value):
        if not hasattr(self, "_wallets"):
            self._wallets = {}
        if not self._wallets.get(self.chain):
            self._wallets[self.chain] = {}
        self._wallets[self.chain] = value

    @property
    def bitcoin_core_version_raw(self):
        try:
            bitcoin_core_version_raw = self.rpc.getnetworkinfo()["version"]
            return bitcoin_core_version_raw or 200000
        except BrokenCoreConnectionException:
            # In good faith and in order to keep the tests running, we assume
            # a reasonable core version
            return 200000

    def create_wallet(self, name, sigs_required, key_type, keys, devices, **kwargs):
        try:
            walletsindir = [
                wallet["name"] for wallet in self.rpc.listwalletdir()["wallets"]
            ]
        except:
            walletsindir = []
        self._check_duplicate_keys(keys)
        wallet_alias = alias(name)

        w = self.WalletClass.create(
            self.rpc,
            self.rpc_path,
            self.working_folder,
            self.device_manager,
            self,
            name,
            wallet_alias,
            sigs_required,
            key_type,
            keys,
            devices,
            self.bitcoin_core_version_raw,
            **kwargs,
        )
        # save wallet file to disk
        w.save_to_file()
        # get Wallet class instance
        if w:
            self.wallets[name] = w
            logger.info(f"Successfully created Wallet {name}")
            return w
        else:
            raise ("Failed to create new wallet")

    def delete_wallet(self, wallet, node=None) -> tuple:
        """Returns a tuple with two Booleans, indicating whether the wallet was deleted on the Specter side and/or on the node side."""
        logger.info(f"Deleting {wallet.alias}")
        specter_wallet_deleted = False
        node_wallet_file_deleted = False
        # Make first sure that we can unload the wallet in Bitcoin Core
        try:
            wallet_rpc_path = os.path.join(
                self.rpc_path, wallet.alias
            )  # e.g. specter/jade_wallet
            logger.debug(f"The wallet_rpc_path is: {wallet_rpc_path}")
            self.rpc.unloadwallet(wallet_rpc_path)
            # Delete the wallet.json and backups
            try:
                wallet.delete_files()
                # Remove the wallet instance
                del self.wallets[wallet.name]
                specter_wallet_deleted = True
            except KeyError:
                raise SpecterError(
                    f"The wallet {wallet.name} has already been deleted."
                )
            except SpecterInternalException as sie:
                logger.exception(
                    f"Could not delete the wallet {wallet.name} in Specter due to {sie}"
                )
            # Also delete the wallet file on the node if possible
            if node:
                if node.delete_wallet_file(wallet):
                    node_wallet_file_deleted = True
        except RpcError:
            raise SpecterError(
                "Unable to unload the wallet on the node. Aborting the deletion of the wallet ..."
            )
        deleted = (specter_wallet_deleted, node_wallet_file_deleted)
        return deleted

    def rename_wallet(self, wallet, name):
        logger.info("Renaming {}".format(wallet.alias))
        if wallet.name not in self.wallets_names:
            raise Exception(
                f"Wallet {wallet.name} is not managed by this WalletManager or the wallet is on a different chain than {self.chain}"
            )
        self.wallets.pop(wallet.name)
        wallet.name = name
        if self.working_folder is not None:
            wallet.save_to_file()
        self.wallets[name] = wallet

    def joined_balance(self):
        """
        Joined balance of all wallets.
        I don't call it full balance because
        full balance is different - see wallet.fullbalance...
        """
        balance = {}
        for wallet in self.wallets.values():
            add_dicts(balance, wallet.balance)
        return balance

    def full_txlist(
        self,
        fetch_transactions=True,
        validate_merkle_proofs=False,
        current_blockheight=None,
        service_id=None,
    ):
        """Returns a list of all transactions in all wallets loaded in the wallet_manager.
        #Parameters:
        #    fetch_transactions (bool): Update the TxList CSV caching by fetching transactions from the Bitcoin RPC
        #    validate_merkle_proofs (bool): Return transactions with validated_blockhash
        #    current_blockheight (int): Current blockheight for calculating confirmations number (None will fetch the block count from the RPC)
        #    service_id (str): Filters results for just the specified Service
        """
        # Nested comprehensions:
        txlists = [
            [
                # Inner comprehension: Return each tx and all its attrs as a list of dicts...
                # TODO: Simplify this by adding an `as_dict` option to `Wallet.txlist()`?
                {**tx, "wallet_alias": wallet.alias}
                for tx in wallet.txlist(
                    fetch_transactions=fetch_transactions,
                    validate_merkle_proofs=validate_merkle_proofs,
                    current_blockheight=current_blockheight,
                    service_id=service_id,
                )
            ]
            # Outer comprehension: ...from each wallet, each returning their own tx list.
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

    def full_addresses_info(self, is_change: bool = False, service_id: str = None):
        """Mimics full_txlist in concept, but is really only expected to be used for
        retrieving all addresses across all Wallets that are associated with a
        Service.

        Not currently used yet."""
        addresses_info = []
        for wallet_alias, wallet in self.wallets.items():
            addresses_info.extend(
                wallet.addresses_info(
                    is_change=is_change,
                    service_id=service_id,
                    include_wallet_alias=True,
                )
            )
        return addresses_info

    def delete(self, specter):
        """Deletes all the wallets"""
        for w in list(self.wallets.keys()):
            wallet = self.wallets[w]
            self.delete_wallet(wallet)
        delete_folder(self.data_folder)

    @classmethod
    def _check_duplicate_keys(cls, keys):
        """raise a SpecterError when a xpub in the passed KeyList is listed twice. Should prevent MultisigWallets where
        xpubs are used twice.
        """
        # normalizing xpubs in order to ignore slip132 differences
        xpubs = [Key.parse_xpub(key.original).xpub for key in keys]
        for xpub in xpubs:
            if xpubs.count(xpub) > 1:
                raise SpecterError(_(f"xpub {xpub} seem to be used at least twice!"))
