import os, json, logging, shutil, time, zipfile
from io import BytesIO
from collections import OrderedDict
from .util.descriptor import AddChecksum
from .helpers import alias, load_jsons
from .rpc import get_default_datadir, RpcError
from .specter_error import SpecterError
from .wallet import Wallet
from .persistence import delete_json_file, delete_folder


logger = logging.getLogger()

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
    def __init__(self, data_folder, rpc, chain, device_manager, path="specter"):
        self.data_folder = data_folder
        self.chain = chain
        self.rpc = rpc
        self.rpc_path = path
        self.device_manager = device_manager
        self.is_loading = False
        self.wallets = {}
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
        if self.working_folder is not None and not os.path.isdir(self.working_folder):
            os.mkdir(self.working_folder)
        if rpc is not None:
            self.rpc = rpc

        wallets = {}
        # list of wallets in the dict
        existing_names = list(self.wallets.keys())
        # list of wallet to keep
        keep_wallets = []
        try:
            if self.working_folder is not None and self.rpc is not None:
                wallets_files = load_jsons(self.working_folder, key="name")
                try:
                    existing_wallets = [
                        w["name"] for w in self.rpc.listwalletdir()["wallets"]
                    ]
                except:
                    existing_wallets = None
                loaded_wallets = self.rpc.listwallets()
                for wallet in wallets_files:
                    wallet_alias = wallets_files[wallet]["alias"]
                    wallet_name = wallets_files[wallet]["name"]
                    if (
                        existing_wallets is None
                        or os.path.join(self.rpc_path, wallet_alias) in existing_wallets
                    ):
                        if (
                            os.path.join(self.rpc_path, wallet_alias)
                            not in loaded_wallets
                        ):
                            try:
                                logger.debug(
                                    "loading %s " % wallets_files[wallet]["alias"]
                                )
                                self.rpc.loadwallet(
                                    os.path.join(self.rpc_path, wallet_alias)
                                )
                                wallets[wallet_name] = Wallet.from_json(
                                    wallets_files[wallet], self.device_manager, self
                                )
                                # Lock UTXO of pending PSBTs
                                if len(wallets[wallet_name].pending_psbts) > 0:
                                    for psbt in wallets[wallet_name].pending_psbts:
                                        logger.debug(
                                            "lock %s " % wallet_alias,
                                            wallets[wallet_name].pending_psbts[psbt][
                                                "tx"
                                            ]["vin"],
                                        )
                                        wallets[wallet_name].rpc.lockunspent(
                                            False,
                                            [
                                                utxo
                                                for utxo in wallets[
                                                    wallet_name
                                                ].pending_psbts[psbt]["tx"]["vin"]
                                            ],
                                        )
                            except RpcError as e:
                                logger.warn(
                                    f"Couldn't load wallet {wallet_alias} into core.\
Silently ignored! RPC error: {e}"
                                )
                            except Exception as e:
                                logger.warn(
                                    f"Couldn't load wallet {wallet_alias}.\
Silently ignored! Wallet error: {e}"
                                )
                        else:
                            if wallet_name not in existing_names:
                                # ok wallet is already there
                                # we only need to update
                                try:
                                    wallets[wallet_name] = Wallet.from_json(
                                        wallets_files[wallet], self.device_manager, self
                                    )
                                except Exception as e:
                                    logger.warn(
                                        f"Failed to load wallet {wallet_name}: {e}"
                                    )
                            else:
                                # wallet is loaded and should stay
                                keep_wallets.append(wallet_name)
                                # TODO: check wallet file didn't change
                    else:
                        logger.warn(
                            "Couldn't find wallet %s in core's wallets.\
Silently ignored!"
                            % wallet_alias
                        )
        # only ignore rpc errors
        except RpcError as e:
            logger.error(f"Failed updating wallet manager. RPC error: {e}")
        # add new wallets
        for k in wallets:
            self.wallets[k] = wallets[k]
        # remove irrelevant wallets
        for k in existing_names:
            if k in keep_wallets:
                self.wallets[k].update()
            else:
                self.wallets.pop(k)
        self.is_loading = False

    def get_by_alias(self, alias):
        for wallet_name in self.wallets:
            if self.wallets[wallet_name].alias == alias:
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
        recv_descriptor = AddChecksum(recv_descriptor)
        change_descriptor = AddChecksum(change_descriptor)

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
            os.path.join(self.working_folder, "%s.json" % wallet_alias),
            self.device_manager,
            self,
        )
        # save wallet file to disk
        if self.working_folder is not None:
            w.save_to_file()
        # get Wallet class instance
        self.wallets[name] = w
        return w

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
                print(path, os.path.exists(path))
                if os.path.exists(path):
                    shutil.rmtree(path)
                    break
        # Delete JSON
        delete_json_file(wallet.fullpath)
        del self.wallets[wallet.name]
        self.update()

    def rename_wallet(self, wallet, name):
        logger.info("Renaming {}".format(wallet.alias))
        wallet.name = name
        if self.working_folder is not None:
            wallet.save_to_file()
        self.update()

    def full_txlist(self, idx, validate_merkle_proofs=False):
        txlists = [
            [
                {**tx, "wallet_alias": wallet.alias}
                for tx in wallet.txlist(
                    idx,
                    wallet_tx_batch=100 // len(self.wallets),
                    validate_merkle_proofs=validate_merkle_proofs,
                )
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
        for w in self.wallets:
            wallet = self.wallets[w]
            self.delete_wallet(wallet, specter.bitcoin_datadir, specter.chain)
        delete_folder(self.data_folder)
