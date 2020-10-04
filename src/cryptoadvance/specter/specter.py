import copy
import json
import logging
import os
import random
import time
import zipfile
from io import BytesIO
from .helpers import deep_update, clean_psbt
from .rpc import autodetect_rpc_confs, get_default_datadir, RpcError
from .rpc import BitcoinRPC
from .device_manager import DeviceManager
from .wallet_manager import WalletManager
from flask_login import current_user
import threading

logger = logging.getLogger(__name__)


def get_rpc(conf, old_rpc=None):
    """
    Checks if config have changed,
    compares with old rpc
    and returns new one if necessary
    """
    if "autodetect" not in conf:
        conf["autodetect"] = True
    rpc = None
    if conf["autodetect"]:
        if "port" in conf:
            rpc_conf_arr = autodetect_rpc_confs(
                datadir=os.path.expanduser(conf["datadir"]), port=conf["port"]
            )
        else:
            rpc_conf_arr = autodetect_rpc_confs(
                datadir=os.path.expanduser(conf["datadir"])
            )
        if len(rpc_conf_arr) > 0:
            rpc = BitcoinRPC(**rpc_conf_arr[0])
    else:
        # if autodetect is disabled and port is not defined
        # we use default port 8332
        if not conf.get("port", None):
            conf["port"] = 8332
        rpc = BitcoinRPC(**conf)
    # check if we have something to compare with
    if old_rpc is None:
        logger.info("rpc config have changed.")
        return rpc
    # check if we have something detected
    if rpc is None:
        # check if old rpc is still valid
        return old_rpc if old_rpc.test_connection() else None
    # check if something have changed
    # and return new rpc if so
    if rpc.url == old_rpc.url:
        return old_rpc
    else:
        logger.info("rpc config have changed.")
        return rpc


class Specter:
    """ A central Object mostly holding app-settings """

    CONFIG_FILE_NAME = "config.json"
    # use this lock for all fs operations
    lock = threading.Lock()

    def __init__(self, data_folder="./data", config={}):
        if data_folder.startswith("~"):
            data_folder = os.path.expanduser(data_folder)
        data_folder = os.path.abspath(data_folder)
        self.data_folder = data_folder
        self.rpc = None
        self.device_manager = None
        self.wallet_manager = None
        self._current_version = None

        self.file_config = None  # what comes from config file
        self.arg_config = config  # what comes from arguments
        self.utxorescanwallet = None

        # default config
        self.config = {
            "rpc": {
                "autodetect": True,
                "datadir": get_default_datadir(),
                "user": "",
                "password": "",
                "port": "",
                "host": "localhost",  # localhost
                "protocol": "http",  # https for the future
            },
            "auth": "none",
            "explorers": {"main": "", "test": "", "regtest": "", "signet": ""},
            "hwi_bridge_url": "/hwi/api/",
            # unique id that will be used in wallets path in Bitcoin Core
            # empty by default for backward-compatibility
            "uid": "",
            "unit": "btc",
            "validate_merkle_proofs": False,
        }

        # creating folders if they don't exist
        if not os.path.isdir(data_folder):
            os.makedirs(data_folder)

        self.is_checking = False
        # health check: loads config and tests rpc
        self.check()

    @property
    def bitcoin_datadir(self):
        if "datadir" in self.config["rpc"]:
            return os.path.expanduser(self.config["rpc"]["datadir"])
        return get_default_datadir()

    def check(self, user=current_user):
        # if config.json file exists - load from it
        if os.path.isfile(os.path.join(self.data_folder, "config.json")):
            with self.lock:
                with open(os.path.join(self.data_folder, "config.json"), "r") as f:
                    self.file_config = json.load(f)
                    deep_update(self.config, self.file_config)
            # otherwise - create one and assign unique id
        else:
            if self.config["uid"] == "":
                self.config["uid"] = (
                    random.randint(0, 256 ** 8).to_bytes(8, "big").hex()
                )
            self._save()

        # init arguments
        deep_update(self.config, self.arg_config)  # override loaded config

        # update rpc if something doesn't work
        if self.rpc is None or not self.rpc.test_connection():
            self.rpc = get_rpc(self.config["rpc"], self.rpc)
        self._is_configured = self.rpc is not None
        self._is_running = False
        if self._is_configured:
            try:
                res = [
                    r["result"]
                    for r in self.rpc.multi(
                        [
                            ("getblockchaininfo", None),
                            ("getnetworkinfo", None),
                            ("getmempoolinfo", None),
                            ("uptime", None),
                            ("getblockhash", 0),
                            ("scantxoutset", "status", []),
                        ]
                    )
                ]
                self._info = res[0]
                self._network_info = res[1]
                self._info["mempool_info"] = res[2]
                self._info["uptime"] = res[3]
                try:
                    self.rpc.getblockfilter(res[4])
                    self._info["blockfilterindex"] = True
                except:
                    self._info["blockfilterindex"] = False
                self._info["utxorescan"] = (
                    res[5]["progress"]
                    if res[5] is not None and "progress" in res[5]
                    else None
                )
                if self._info["utxorescan"] is None:
                    self.utxorescanwallet = None
                self._is_running = True
            except Exception as e:
                self._info = {"chain": None}
                self._network_info = {"subversion": "", "version": 999999}
                logger.error("Exception %s while specter.check()" % e)
                pass
        else:
            self._info = {"chain": None}
            self._network_info = {"subversion": "", "version": 999999}

        if not self._is_running:
            self._info["chain"] = None

        chain = self._info["chain"]
        if hasattr(user, "is_admin"):
            user_folder_id = "_" + user.id if user and not user.is_admin else ""
        else:
            user_folder_id = ""

        if self.config["auth"] != "usernamepassword" or (
            user and not user.is_anonymous
        ):
            if self.device_manager is None:
                self.device_manager = DeviceManager(
                    os.path.join(self.data_folder, "devices{}".format(user_folder_id))
                )
            else:
                self.device_manager.update(
                    data_folder=os.path.join(
                        self.data_folder, "devices{}".format(user_folder_id)
                    )
                )

            wallets_path = "specter%s" % self.config["uid"]
            # if chain, user or data folder changed
            if (
                self.wallet_manager is None
                or self.wallet_manager.data_folder != self.data_folder
                or self.wallet_manager.rpc_path != wallets_path
                or self.wallet_manager.chain != chain
            ):
                self.wallet_manager = WalletManager(
                    os.path.join(self.data_folder, "wallets{}".format(user_folder_id)),
                    self.rpc,
                    chain,
                    self.device_manager,
                    path=wallets_path,
                )
            else:
                self.wallet_manager.update(
                    os.path.join(self.data_folder, "wallets{}".format(user_folder_id)),
                    self.rpc,
                    chain=chain,
                )

    def abortrescanutxo(self):
        self.rpc.scantxoutset("abort", [])
        # Bitcoin Core doesn't catch up right away
        # so app.specter.check() doesn't work
        self._info["utxorescan"] = None
        self.utxorescanwallet = None

    def clear_user_session(self):
        self.device_manager = None
        self.wallet_manager = None

    def test_rpc(self, **kwargs):
        conf = copy.deepcopy(self.config["rpc"])
        conf.update(kwargs)
        rpc = get_rpc(conf)
        if rpc is None:
            return {"out": "", "err": "autodetect failed", "code": -1}
        r = {}
        r["tests"] = {}
        try:
            r["tests"]["recent_version"] = (
                int(rpc.getnetworkinfo()["version"]) >= 170000
            )
            r["tests"]["connectable"] = True
            r["tests"]["credentials"] = True
            try:
                rpc.listwallets()
                r["tests"]["wallets"] = True
            except RpcError as rpce:
                logger.error(rpce)
                r["tests"]["wallets"] = False

            r["out"] = json.dumps(rpc.getblockchaininfo(), indent=4)
            r["err"] = ""
            r["code"] = 0
        except ConnectionError as e:
            logger.error(e)
            r["tests"]["connectable"] = False
            r["err"] = "Failed to connect!"
            r["code"] = -1
        except RpcError as rpce:
            logger.error(rpce)
            if rpce.status_code == 401:
                r["tests"]["credentials"] = False
            else:
                raise rpce
        except Exception as e:
            logger.error(e)
            r["out"] = ""
            if rpc.r is not None and "error" in rpc.r:
                r["err"] = rpc.r["error"]
                r["code"] = rpc.r.status_code
            else:
                r["err"] = "Failed to connect"
                r["code"] = -1
        return r

    def _save(self):
        with self.lock:
            with open(os.path.join(self.data_folder, self.CONFIG_FILE_NAME), "w") as f:
                json.dump(self.config, f, indent=4)

    def update_rpc(self, **kwargs):
        need_update = False
        for k in kwargs:
            if self.config["rpc"][k] != kwargs[k]:
                self.config["rpc"][k] = kwargs[k]
                need_update = True
        if need_update:
            self.rpc = get_rpc(self.config["rpc"], None)
            self._save()
            self.check()
        return self.rpc is not None

    def update_auth(self, auth):
        """ simply persisting the current auth-choice """
        if self.config["auth"] != auth:
            self.config["auth"] = auth
        self._save()

    def update_explorer(self, explorer, user):
        """ update the block explorers urls """
        # we don't know what chain to change
        if not self.chain:
            return
        if explorer and not explorer.endswith("/"):
            # make sure the urls end with a "/"
            explorer += "/"
        # update the urls in the app config
        if user.id == "admin":
            if self.config["explorers"][self.chain] != explorer:
                self.config["explorers"][self.chain] = explorer
            self._save()
        else:
            user.set_explorer(self, explorer)

    def update_hwi_bridge_url(self, url, user):
        """ update the hwi bridge url to use """
        if url and not url.endswith("/"):
            # make sure the urls end with a "/"
            url += "/"
        # a few dummy checks:
        # no schema and not local
        if "://" not in url and not url.startswith("/"):
            url = "http://" + url
        # wrong ending:
        if url.endswith("/hwi/settings/"):
            url = url.replace("/hwi/settings/", "/hwi/api/")
        # no ending
        if not url.endswith("/hwi/api/"):
            url += "hwi/api/"

        if user.id == "admin":
            self.config["hwi_bridge_url"] = url
            self._save()
        else:
            user.set_hwi_bridge_url(self, url)

    def update_unit(self, unit, user):
        if user.id == "admin":
            self.config["unit"] = unit
            self._save()
        else:
            user.set_unit(self, unit)

    def update_merkleproof_settings(self, validate_bool):
        if validate_bool is True and self._info.get("pruned") is True:
            validate_bool = False
            logger.warning("Cannot enable merkleproof setting on pruned node.")

        self.config["validate_merkle_proofs"] = validate_bool
        self._save()

    def add_new_user_otp(self, otp_dict):
        """ adds an OTP for user registration """
        if "new_user_otps" not in self.config:
            self.config["new_user_otps"] = []
        self.config["new_user_otps"].append(otp_dict)
        self._save()

    def burn_new_user_otp(self, otp):
        """ validates an OTP for user registration and removes it if valid"""
        if "new_user_otps" not in self.config:
            return False
        for i, otp_dict in enumerate(self.config["new_user_otps"]):
            # TODO: Validate OTP did not expire based on created_at
            if otp_dict["otp"] == int(otp):
                del self.config["new_user_otps"][i]
                self._save()
                return True
        return False

    def combine(self, psbt_arr):
        # backward compatibility with current Core psbt parser
        psbt_arr = [clean_psbt(psbt) for psbt in psbt_arr]
        final_psbt = self.rpc.combinepsbt(psbt_arr)
        return final_psbt

    def finalize(self, psbt):
        final_psbt = self.rpc.finalizepsbt(psbt)
        return final_psbt

    def broadcast(self, raw):
        res = self.rpc.sendrawtransaction(raw)
        return res

    def estimatesmartfee(self, blocks):
        return self.rpc.estimatesmartfee(blocks)

    def get_default_explorer(self):
        """
        Returns a blockexplorer url:
        user-defined if it's set, otherwise
        blockstream.info for main and testnet,
        bc-2.jp for signet
        """
        # not None or ""
        if self.explorer:
            return self.explorer
        if self.chain == "main":
            return "https://blockstream.info/"
        elif self.chain == "test":
            return "https://blockstream.info/testnet/"
        elif self.chain == "signet":
            return "https://explorer.bc-2.jp/"

    @property
    def is_running(self):
        return self._is_running

    @property
    def is_configured(self):
        return self._is_configured

    @property
    def info(self):
        return self._info

    @property
    def network_info(self):
        return self._network_info

    @property
    def bitcoin_core_version(self):
        return self.network_info["subversion"].replace("/", "").replace("Satoshi:", "")

    @property
    def chain(self):
        return self._info["chain"]

    @property
    def explorer(self):
        # TODO: Unify for user and admin
        if (not current_user or current_user.is_anonymous) or current_user.is_admin:
            if "explorers" in self.config and self.chain in self.config["explorers"]:
                return self.config["explorers"][self.chain]
            else:
                return ""
        else:
            if (
                "explorers" in current_user.config
                and self.chain in current_user.config["explorers"]
            ):
                return current_user.config["explorers"][self.chain]
            else:
                return ""

    @property
    def hwi_bridge_url(self):
        # TODO: Unify for user and admin
        if (not current_user or current_user.is_anonymous) or current_user.is_admin:
            if "hwi_bridge_url" in self.config:
                return self.config["hwi_bridge_url"]
            else:
                return ""
        else:
            if "hwi_bridge_url" in current_user.config:
                return current_user.config["hwi_bridge_url"]
            else:
                return ""

    @property
    def unit(self):
        # TODO: Unify for user and admin
        if (not current_user or current_user.is_anonymous) or current_user.is_admin:
            if "unit" in self.config:
                return self.config["unit"]
            else:
                return "btc"
        else:
            if "unit" in current_user.config:
                return current_user.config["unit"]
            else:
                return "btc"

    def specter_backup_file(self):
        memory_file = BytesIO()
        with zipfile.ZipFile(memory_file, "w") as zf:
            if self.wallet_manager:
                for wallet in self.wallet_manager.wallets.values():
                    data = zipfile.ZipInfo("{}.json".format(wallet.alias))
                    data.date_time = time.localtime(time.time())[:6]
                    data.compress_type = zipfile.ZIP_DEFLATED
                    zf.writestr(
                        "wallets/{}.json".format(wallet.alias), json.dumps(wallet.json)
                    )
            if self.device_manager:
                for device in self.device_manager.devices.values():
                    data = zipfile.ZipInfo("{}.json".format(device.alias))
                    data.date_time = time.localtime(time.time())[:6]
                    data.compress_type = zipfile.ZIP_DEFLATED
                    zf.writestr(
                        "devices/{}.json".format(device.alias), json.dumps(device.json)
                    )
        memory_file.seek(0)
        return memory_file
