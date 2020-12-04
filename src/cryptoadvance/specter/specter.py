import copy
import json
import logging
import os
import traceback
import random
import time
import zipfile
import requests
from io import BytesIO
from .helpers import migrate_config, deep_update, clean_psbt, is_testnet
from .util.checker import Checker
from .rpc import autodetect_rpc_confs, get_default_datadir, RpcError
from urllib3.exceptions import NewConnectionError
from requests.exceptions import ConnectionError
from .rpc import BitcoinRPC
from .device_manager import DeviceManager
from .wallet_manager import WalletManager
from .user_manager import UserManager
from .persistence import write_json_file, read_json_file
from .user import User
from .util.price_providers import update_price
import threading

logger = logging.getLogger(__name__)


def get_rpc(
    conf,
    old_rpc=None,
    return_broken_instead_none=False,
    proxy_url="socks5h://localhost:9050",
    only_tor=False,
):
    """
    Checks if config have changed, compares with old rpc
    and returns new one if necessary
    If there is no working rpc-connection, it has to return None
    If return_broken_instead_none is True, it'll return even a broken connection.
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
            rpc = BitcoinRPC(**rpc_conf_arr[0], proxy_url=proxy_url, only_tor=only_tor)
    else:
        # if autodetect is disabled and port is not defined
        # we use default port 8332
        if not conf.get("port", None):
            conf["port"] = 8332
        rpc = BitcoinRPC(**conf)
    if return_broken_instead_none:
        return rpc
    # check if we have something to compare with
    if old_rpc is None:
        return rpc if rpc and rpc.test_connection() else None
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

    # use this lock for all fs operations
    lock = threading.Lock()

    def __init__(self, data_folder="./data", config={}):
        if data_folder.startswith("~"):
            data_folder = os.path.expanduser(data_folder)
        data_folder = os.path.abspath(data_folder)

        # creating folders if they don't exist
        if not os.path.isdir(data_folder):
            os.makedirs(data_folder)

        self.data_folder = data_folder

        self.rpc = None
        self.user_manager = UserManager(self)

        self.file_config = None  # what comes from config file
        self.arg_config = config  # what comes from arguments

        # wallet that is currently rescnning with utxorescan
        # can be only one at a time
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
            "auth": {
                "method": "none",
                "password_min_chars": 6,
                "rate_limit": 10,
                "registration_link_timeout": 1,
            },
            "explorers": {"main": "", "test": "", "regtest": "", "signet": ""},
            "proxy_url": "socks5h://localhost:9050",  # Tor proxy URL
            "only_tor": False,
            "tor_control_port": "",
            "tor_status": False,
            "hwi_bridge_url": "/hwi/api/",
            # unique id that will be used in wallets path in Bitcoin Core
            # empty by default for backward-compatibility
            "uid": "",
            "unit": "btc",
            "price_check": False,
            "alt_rate": 1,
            "alt_symbol": "BTC",
            "price_provider": "",
            "validate_merkle_proofs": False,
        }

        # health check: loads config, tests rpc
        # also loads and checks wallets for all users
        try:
            self.check(check_all=True)
        except Exception as e:
            logger.error(e)
        self.checker = Checker(lambda: self.check(check_all=True), desc="health")
        self.checker.start()
        self.price_checker = Checker(
            lambda: update_price(self, self.user), desc="price"
        )
        if self.price_check and self.price_provider:
            self.price_checker.start()

    def check(self, user=None, check_all=False):
        """
        Checks and updates everything for a particular user:
        - config if changed
        - rpc including check if it's connected
        - node info
        - wallet manager
        - device manager
        """
        # check if config file have changed
        self.check_config()

        # update rpc if something doesn't work
        rpc = self.rpc
        if rpc is None or not rpc.test_connection():
            rpc = get_rpc(
                self.config["rpc"],
                self.rpc,
                proxy_url=self.proxy_url,
                only_tor=self.only_tor,
            )

        # if rpc is not available
        # do checks more often, once in 20 seconds
        if rpc is None:
            period = 20
        else:
            period = 600
        if hasattr(self, "checker") and self.checker.period != period:
            self.checker.period = period
        self.rpc = rpc

        self.check_node_info()
        if not check_all:
            # find proper user
            user = self.user_manager.get_user(user)
            self.check_for_user(user)
        else:
            for u in self.user_manager.users:
                self.check_for_user(u)

    def check_node_info(self):
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

    def check_blockheight(self):
        current_blockheight = self.rpc.getblockcount()
        if self.info["blocks"] != current_blockheight:
            self.check(check_all=True)

    def get_user_folder_id(self, user=None):
        """
        Returns the suffix for the user wallets and devices.
        User can be either a flask_login user or a string.
        """
        user = self.user_manager.get_user(user)
        if not user.is_admin:
            return "_" + user.id
        return ""

    def check_wallet_manager(self, user=None):
        """Updates wallet manager for a particular user"""
        user = self.user_manager.get_user(user)
        wallets_rpcpath = "specter%s" % self.config["uid"]
        wallets_folder = os.path.join(self.data_folder, f"wallets{user.folder_id}")
        # if chain, user or data folder changed
        wallet_manager = user.wallet_manager
        if (
            wallet_manager is None
            or wallet_manager.data_folder != self.data_folder
            or wallet_manager.rpc_path != wallets_rpcpath
            or wallet_manager.chain != self.chain
        ):
            wallet_manager = WalletManager(
                self.bitcoin_core_version_raw,
                wallets_folder,
                self.rpc,
                self.chain,
                user.device_manager,
                path=wallets_rpcpath,
            )
            user.wallet_manager = wallet_manager
        else:
            wallet_manager.update(wallets_folder, self.rpc, chain=self.chain)

    def check_device_manager(self, user=None):
        """Updates device manager for a particular user"""
        user = self.user_manager.get_user(user)
        devices_folder = os.path.join(self.data_folder, f"devices{user.folder_id}")
        device_manager = user.device_manager
        if device_manager is None:
            device_manager = DeviceManager(devices_folder)
            user.device_manager = device_manager
        else:
            device_manager.update(data_folder=devices_folder)

    def check_config(self):
        """
        Updates config if file config have changed.
        Priority (low to high):
        - existing / default config
        - file config from config.json
        - arg_config passed in constructor
        """

        # if config.json file exists - load from it
        if os.path.isfile(self.config_fname):
            with self.lock:
                self.file_config = read_json_file(self.config_fname)
                migrate_config(self.file_config)
                deep_update(self.config, self.file_config)
            # otherwise - create one and assign unique id
        else:
            # unique id of specter
            if self.config["uid"] == "":
                self.config["uid"] = (
                    random.randint(0, 256 ** 8).to_bytes(8, "big").hex()
                )
            self._save()

        # config from constructor overrides file config
        deep_update(self.config, self.arg_config)

    def check_for_user(self, user=None):
        """
        Performs device and wallet manager check for particular user
        """
        user = self.user_manager.get_user(user)
        self.check_device_manager(user)
        self.check_wallet_manager(user)

    def add_user(self, user):
        if user in self.user_manager.users:
            return
        user.wallet_manager = None
        user.device_manager = None
        self.user_manager.add_user(user)
        self.check_for_user(user)

    def delete_user(self, user):
        if user not in self.user_manager.users:
            return
        user = self.user_manager.get_user(user)
        user.wallet_manager.delete(self)
        user.device_manager.delete(self)
        self.user_manager.delete_user(user)

    @property
    def bitcoin_datadir(self):
        if "datadir" in self.config["rpc"]:
            return os.path.expanduser(self.config["rpc"]["datadir"])
        return get_default_datadir()

    def abortrescanutxo(self):
        self.rpc.scantxoutset("abort", [])
        # Bitcoin Core doesn't catch up right away
        # so app.specter.check() doesn't work
        self._info["utxorescan"] = None
        self.utxorescanwallet = None

    def test_rpc(self, **kwargs):
        conf = copy.deepcopy(self.config["rpc"])
        conf.update(kwargs)

        rpc = get_rpc(
            conf,
            return_broken_instead_none=True,
            proxy_url=self.proxy_url,
            only_tor=self.only_tor,
        )
        if rpc is None:
            return {"out": "", "err": "autodetect failed", "code": -1}
        r = {}
        r["tests"] = {"connectable": False}
        r["err"] = ""
        r["code"] = 0
        try:
            r["tests"]["recent_version"] = (
                int(rpc.getnetworkinfo()["version"]) >= 170000
            )
            if not r["tests"]["recent_version"]:
                r["err"] = "Core Node might be too old"

            r["tests"]["connectable"] = True
            r["tests"]["credentials"] = True
            try:
                rpc.listwallets()
                r["tests"]["wallets"] = True
            except RpcError as rpce:
                logger.error(rpce)
                r["tests"]["wallets"] = False
                r["err"] = "Wallets disabled"

            r["out"] = json.dumps(rpc.getblockchaininfo(), indent=4)
        except ConnectionError as e:
            logger.error("Caught an ConnectionError while test_rpc: %s", e)

            r["tests"]["connectable"] = False
            r["err"] = "Failed to connect!"
            r["code"] = -1
        except RpcError as rpce:
            logger.error("Caught an RpcError while test_rpc: %s", rpce)
            logger.error(rpce.status_code)
            r["tests"]["connectable"] = True
            r["code"] = rpc.r.status_code
            if rpce.status_code == 401:
                r["tests"]["credentials"] = False
                r["err"] = "RPC authentication failed!"
            else:
                r["err"] = str(rpce.status_code)
        except Exception as e:
            logger.error(
                "Caught an exception of type {} while test_rpc: {}".format(
                    type(e), str(e)
                )
            )
            r["out"] = ""
            if rpc.r is not None and "error" in rpc.r:
                r["err"] = rpc.r["error"]
                r["code"] = rpc.r.status_code
            else:
                r["err"] = "Failed to connect"
                r["code"] = -1
        return r

    def _save(self):
        write_json_file(self.config, self.config_fname, lock=self.lock)

    @property
    def config_fname(self):
        return os.path.join(self.data_folder, "config.json")

    def update_rpc(self, **kwargs):
        need_update = False
        for k in kwargs:
            if self.config["rpc"][k] != kwargs[k]:
                self.config["rpc"][k] = kwargs[k]
                need_update = True
        if need_update:
            self.rpc = get_rpc(
                self.config["rpc"],
                None,
                proxy_url=self.proxy_url,
                only_tor=self.only_tor,
            )
            self._save()
            self.check(check_all=True)
        return self.rpc is not None

    def update_auth(self, method, rate_limit, registration_link_timeout):
        """ simply persisting the current auth-choice """
        auth = self.config["auth"]
        if auth["method"] != method:
            auth["method"] = method
        if auth["rate_limit"] != rate_limit:
            auth["rate_limit"] = rate_limit
        if auth["registration_link_timeout"] != registration_link_timeout:
            auth["registration_link_timeout"] = registration_link_timeout
        self._save()

    def update_explorer(self, explorer, user):
        """ update the block explorers urls """
        user = self.user_manager.get_user(user)
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

    def update_proxy_url(self, proxy_url, user):
        """ update the Tor proxy url """
        if self.config["proxy_url"] != proxy_url:
            self.config["proxy_url"] = proxy_url
            self._save()

    def toggle_tor_status(self):
        """ toggle the Tor status """
        self.config["tor_status"] = not self.config["tor_status"]
        self._save()

    def update_only_tor(self, only_tor, user):
        """ switch whatever to use Tor for all calls """
        if self.config["only_tor"] != only_tor:
            self.config["only_tor"] = only_tor
            self._save()

    def update_tor_control_port(self, tor_control_port, user):
        """ set the control port of the tor daemon """
        if self.config["tor_control_port"] != tor_control_port:
            self.config["tor_control_port"] = tor_control_port
            self._save()

    def update_hwi_bridge_url(self, url, user):
        """ update the hwi bridge url to use """
        user = self.user_manager.get_user(user)
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

        if user.is_admin:
            self.config["hwi_bridge_url"] = url
            self._save()
        else:
            user.set_hwi_bridge_url(self, url)

    def update_unit(self, unit, user):
        if user.is_admin:
            self.config["unit"] = unit
            self._save()
        else:
            user.set_unit(self, unit)

    def update_price_check_setting(self, price_check_bool, user):
        if user.is_admin:
            self.config["price_check"] = price_check_bool
            self._save()
        else:
            user.set_price_check(self, price_check_bool)
        if price_check_bool and (self.price_provider and self.user == user):
            self.price_checker.start()
        else:
            self.price_checker.stop()

    def update_price_provider(self, price_provider, user):
        if user.is_admin:
            self.config["price_provider"] = price_provider
            self._save()
        else:
            user.set_price_provider(self, price_provider)

    def update_alt_rate(self, alt_rate, user):
        alt_rate = round(float(alt_rate), 2)
        if user.is_admin:
            self.config["alt_rate"] = alt_rate
            self._save()
        else:
            user.set_alt_rate(self, alt_rate)

    def update_alt_symbol(self, alt_symbol, user):
        if user.is_admin:
            self.config["alt_symbol"] = alt_symbol
            self._save()
        else:
            user.set_alt_symbol(self, alt_symbol)

    def update_merkleproof_settings(self, validate_bool):
        if validate_bool is True and self.info.get("pruned") is True:
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

    def validate_new_user_otp(self, otp):
        """ validates an OTP for user registration and removes it if expired"""
        if "new_user_otps" not in self.config:
            return False
        now = time.time()
        for i, otp_dict in enumerate(self.config["new_user_otps"]):
            if otp_dict["otp"] == otp:
                if (
                    "expiry" in otp_dict
                    and otp_dict["expiry"] < now
                    and otp_dict["expiry"] > 0
                ):
                    del self.config["new_user_otps"][i]
                    self._save()
                    return False
                return True
        return False

    def remove_new_user_otp(self, otp):
        """ removes an OTP for user registration"""
        if "new_user_otps" not in self.config:
            return False
        for i, otp_dict in enumerate(self.config["new_user_otps"]):
            if otp_dict["otp"] == otp:
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
    def bitcoin_core_version_raw(self):
        return self.network_info["version"]

    @property
    def chain(self):
        return self._info["chain"]

    @property
    def is_testnet(self):
        return is_testnet(self.chain)

    @property
    def user_config(self):
        return self.config if self.user.is_admin else self.user.config

    @property
    def explorer(self):
        return self.user_config.get("explorers", {}).get(self.chain, "")

    @property
    def proxy_url(self):
        return self.user_config.get("proxy_url", "socks5h://localhost:9050")

    @property
    def only_tor(self):
        return self.user_config.get("only_tor", False)

    @property
    def tor_control_port(self):
        return self.user_config.get("tor_control_port", "")

    @property
    def hwi_bridge_url(self):
        return self.user_config.get("hwi_bridge_url", "")

    @property
    def unit(self):
        return self.user_config.get("unit", "btc")

    @property
    def price_check(self):
        return self.user_config.get("price_check", False)

    @property
    def price_provider(self):
        return self.user_config.get("price_provider", False)

    @property
    def alt_rate(self):
        return self.user_config.get("alt_rate", 1)

    @property
    def alt_symbol(self):
        return self.user_config.get("alt_symbol", "BTC")

    @property
    def admin(self):
        for u in self.users:
            if u.is_admin:
                return u

    @property
    def user(self):
        return self.user_manager.user

    @property
    def device_manager(self):
        return self.user.device_manager

    @property
    def wallet_manager(self):
        return self.user.wallet_manager

    def requests_session(self, force_tor=False):
        requests_session = requests.Session()
        if self.only_tor or force_tor:
            requests_session.proxies["http"] = self.proxy_url
            requests_session.proxies["https"] = self.proxy_url
        return requests_session

    def specter_backup_file(self):
        memory_file = BytesIO()
        with zipfile.ZipFile(memory_file, "w") as zf:
            if self.wallet_manager:
                for wallet in self.wallet_manager.wallets.values():
                    data = zipfile.ZipInfo("{}.json".format(wallet.alias))
                    data.date_time = time.localtime(time.time())[:6]
                    data.compress_type = zipfile.ZIP_DEFLATED
                    zf.writestr(
                        "wallets/{}.json".format(wallet.alias),
                        json.dumps(wallet.to_json(for_export=True)),
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
