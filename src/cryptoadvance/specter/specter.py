import copy
import json
import logging
import os
import platform
import random
import secrets
import signal
import threading
import time
import traceback
import zipfile
from io import BytesIO
from sys import exit
from urllib.parse import urlparse

import requests
from requests.exceptions import ConnectionError
from stem.control import Controller
from urllib3.exceptions import NewConnectionError

from .helpers import clean_psbt, deep_update, is_liquid, is_testnet, get_asset_label
from .internal_node import InternalNode
from .liquid.rpc import LiquidRPC
from .managers.config_manager import ConfigManager
from .managers.node_manager import NodeManager
from .managers.otp_manager import OtpManager
from .managers.user_manager import UserManager
from .managers.wallet_manager import WalletManager
from .node import Node
from .persistence import read_json_file, write_json_file, write_node
from .process_controller.bitcoind_controller import BitcoindPlainController
from .rpc import (
    BitcoinRPC,
    RpcError,
    autodetect_rpc_confs,
    detect_rpc_confs,
    get_default_datadir,
)
from .specter_error import ExtProcTimeoutException, SpecterError
from .tor_daemon import TorDaemonController
from .user import User
from .util.checker import Checker
from .util.price_providers import update_price
from .util.setup_states import SETUP_STATES
from .util.tor import get_tor_daemon_suffix

logger = logging.getLogger(__name__)


class Specter:
    """A central Object mostly holding app-settings"""

    # use this lock for all fs operations
    lock = threading.Lock()
    _default_asset = None

    def __init__(self, data_folder="./data", config={}, internal_bitcoind_version=""):
        if data_folder.startswith("~"):
            data_folder = os.path.expanduser(data_folder)
        data_folder = os.path.abspath(data_folder)

        # creating folders if they don't exist
        if not os.path.isdir(data_folder):
            os.makedirs(data_folder)

        self.data_folder = data_folder

        self.user_manager = UserManager(self)

        self._config_manager = ConfigManager(self.data_folder, config)

        self.internal_bitcoind_version = internal_bitcoind_version

        # Migrating from Specter 1.3.1 and lower (prior to the node manager)
        self.migrate_old_node_format()

        self.node_manager = NodeManager(
            proxy_url=self.proxy_url,
            only_tor=self.only_tor,
            active_node=self.active_node_alias,
            bitcoind_path=self.bitcoind_path,
            internal_bitcoind_version=internal_bitcoind_version,
            data_folder=os.path.join(self.data_folder, "nodes"),
        )

        self.torbrowser_path = os.path.join(
            self.data_folder, f"tor-binaries/tor{get_tor_daemon_suffix()}"
        )

        self._tor_daemon = None

        self.setup_status = {
            "stage": "start",
            "bitcoind": {
                "stage_progress": -1,
                "stage": "",
                "error": "",
            },
            "torbrowser": {
                "stage_progress": -1,
                "stage": "",
                "error": "",
            },
        }
        # health check: loads config, tests rpc
        # also loads and checks wallets for all users
        try:
            self.check(check_all=True)

            if os.path.isfile(self.torbrowser_path):
                self.tor_daemon.start_tor_daemon()
        except Exception as e:
            logger.error(e)

        self.update_tor_controller()
        self.checker = Checker(lambda: self.check(check_all=True), desc="health")
        self.checker.start()
        self.price_checker = Checker(
            lambda: update_price(self, self.user), desc="price"
        )
        if self.price_check and self.price_provider:
            self.price_checker.start()

        # This is for CTRL-C --> SIGINT
        signal.signal(signal.SIGINT, self.cleanup_on_exit)
        # This is for kill $pid --> SIGTERM
        signal.signal(signal.SIGTERM, self.cleanup_on_exit)

    def cleanup_on_exit(self, signum=0, frame=0):
        if self._tor_daemon:
            logger.info("Specter exit cleanup: Stopping Tor daemon")
            self._tor_daemon.stop_tor_daemon()

        for node in self.node_manager.nodes.values():
            if not node.external_node:
                node.stop()

        logger.info("Closing Specter after cleanup")
        # For some reason we need to explicitely exit here. Otherwise it will hang
        exit(0)

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

        self.node.update_rpc()

        # if rpc is not available
        # do checks more often, once in 20 seconds
        if self.rpc is None or self.node.info.get("initialblockdownload", True):
            period = 20
        else:
            period = 600
        if hasattr(self, "checker") and self.checker.period != period:
            self.checker.period = period

        if not check_all:
            # find proper user
            user = self.user_manager.get_user(user)
            user.check()
        else:
            for u in self.user_manager.users:
                u.check()

    @property
    def node(self):
        try:
            return self.node_manager.active_node
        except SpecterError as e:
            logger.error("SpecterError while accessing active_node")
            logger.exception(e)
            self.update_active_node(list(self.node_manager.nodes.values())[0].alias)
            return self.node_manager.active_node

    @property
    def default_node(self):
        return self.node_manager.default_node()

    @property
    def rpc(self):
        return self.node.rpc

    @property
    def utxorescanwallet(self):
        return self.node.utxorescanwallet

    @utxorescanwallet.setter
    def utxorescanwallet(self, value):
        self.node.utxorescanwallet = value

    @property
    def config(self):
        """A convenience property simply redirecting to the config_manager"""
        return self.config_manager.data

    def check_blockheight(self):
        if self.node.check_blockheight():
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

    def check_config(self):
        """
        Updates config if file config have changed.
        Priority (low to high):
        - existing / default config
        - file config from config.json
        - arg_config passed in constructor
        """
        self.config_manager.check_config()

    def delete_user(self, user):
        if user not in self.user_manager.users:
            return
        user = self.user_manager.get_user(user)
        user.wallet_manager.delete(self)
        user.device_manager.delete(self)
        self.user_manager.delete_user(user)

    # mark
    @property
    def bitcoin_datadir(self):
        return self.node.datadir

    # mark
    def _save(self):
        write_json_file(self.config, self.config_fname, lock=self.lock)

    @property
    def config_fname(self):
        return os.path.join(self.data_folder, "config.json")

    # mark
    def update_active_node(self, node_alias):
        """update the current active node to use"""
        self.config_manager.update_active_node(node_alias)
        self.node_manager.switch_node(node_alias)
        self.check()

    def update_setup_status(self, software_name, stage):
        self.setup_status[software_name]["error"] = ""
        if stage in SETUP_STATES:
            self.setup_status[software_name]["stage"] = SETUP_STATES[stage].get(
                software_name, stage
            )
        else:
            self.setup_status[software_name]["stage"] = stage
        self.setup_status[software_name]["stage_progress"] = 0

    def update_setup_download_progress(self, software_name, progress):
        self.setup_status[software_name]["error"] = ""
        self.setup_status[software_name]["stage_progress"] = progress

    def update_setup_error(self, software_name, error):
        self.setup_status[software_name]["error"] = error
        self.setup_status[software_name]["stage_progress"] = -1

    def reset_setup(self, software_name):
        self.setup_status[software_name]["error"] = ""
        self.setup_status[software_name]["stage"] = ""
        self.setup_status[software_name]["stage_progress"] = -1

    def get_setup_status(self, software_name):
        if software_name == "bitcoind":
            installed = os.path.isfile(self.bitcoind_path)
        elif software_name == "torbrowser":
            installed = os.path.isfile(self.torbrowser_path)
        else:
            installed = False

        return {"installed": installed, **self.setup_status[software_name]}

    # mark
    def update_auth(self, method, rate_limit, registration_link_timeout):
        """simply persisting the current auth-choice"""
        self.config_manager.update_auth(method, rate_limit, registration_link_timeout)

    # mark
    def update_explorer(self, explorer_id, explorer_data, user):
        """update the block explorers urls"""
        self.config_manager.update_explorer(
            explorer_id, explorer_data, user, self.chain
        )

    # mark
    def update_fee_estimator(self, fee_estimator, custom_url, user):
        """update the fee estimator option and its url if custom"""
        self.config_manager.update_fee_estimator(fee_estimator, custom_url, user)

    # mark
    def update_tor_type(self, tor_type, user):
        """update the Tor proxy url"""
        if tor_type == "builtin":
            self.update_proxy_url("socks5h://localhost:9050", user)
            self.update_tor_control_port("", user)
        self.config_manager.update_tor_type(tor_type, user)

    # mark
    def update_proxy_url(self, proxy_url, user):
        """update the Tor proxy url"""
        self.config_manager.update_proxy_url(proxy_url, user)

    # mark
    def toggle_tor_status(self):
        """toggle the Tor status"""
        self.config_manager.toggle_tor_status()

    # mark
    def update_only_tor(self, only_tor, user):
        """switch whatever to use Tor for all calls"""
        self.config_manager.update_only_tor(only_tor, user)

    # mark
    def update_tor_control_port(self, tor_control_port, user):
        """set the control port of the tor daemon"""
        if self.config_manager.update_tor_control_port:
            self.update_tor_controller()

    # mark
    def generate_torrc_password(self, overwrite=False):
        self.config_manager.generate_torrc_password(overwrite)

    def update_tor_controller(self):
        if "torrc_password" not in self.config:
            # Will be missing if the user did not go through the built-in Tor setup
            self.generate_torrc_password()
        try:
            tor_control_address = urlparse(self.proxy_url).netloc.split(":")[0]
            if tor_control_address == "localhost":
                tor_control_address = "127.0.0.1"
            self._tor_controller = Controller.from_port(
                address=tor_control_address,
                port=int(self.tor_control_port) if self.tor_control_port else "default",
            )
            self._tor_controller.authenticate(
                password=self.config.get("torrc_password", "")
            )
        except Exception as e:
            logger.warning(f"Failed to connect to Tor control port. Error: {e}")
            self._tor_controller = None

    @property
    def tor_daemon(self):
        if os.path.isfile(self.torbrowser_path) and os.path.join(
            self.data_folder, "torrc"
        ):
            if not self._tor_daemon:
                self._tor_daemon = TorDaemonController(
                    tor_daemon_path=self.torbrowser_path,
                    tor_config_path=os.path.join(self.data_folder, "torrc"),
                )
            return self._tor_daemon
        raise SpecterError(
            "Tor daemon files missing. Make sure Tor is installed within Specter"
        )

    def is_tor_dameon_running(self):
        return self._tor_daemon and self._tor_daemon.is_running()

    @property
    def tor_controller(self):
        if self._tor_controller:
            return self._tor_controller
        self.update_tor_controller()
        if self._tor_controller:
            return self._tor_controller
        raise SpecterError(
            "Failed to connect to the Tor daemon. Make sure ControlPort is properly configured."
        )

    # mark
    def update_hwi_bridge_url(self, url, user):
        """update the hwi bridge url to use"""
        self.config_manager.update_hwi_bridge_url(url, user)

    # mark
    def update_unit(self, unit, user):
        self.config_manager.update_unit(unit, user)

    # mark
    def update_hide_sensitive_info(self, hide_sensitive_info_bool, user):
        self.config_manager.update_hide_sensitive_info(hide_sensitive_info_bool, user)

    # mark
    def update_price_check_setting(self, price_check_bool, user):
        self.config_manager.update_price_check_setting(price_check_bool, user)

    # mark
    def update_price_provider(self, price_provider, user):
        self.config_manager.update_price_provider(price_provider, user)

    # mark needs User-Type injection
    def update_weight_unit(self, weight_unit, user):
        self.config_manager.update_weight_unit(weight_unit, user)

    # mark needs User-Type injection
    def update_alt_rate(self, alt_rate, user):
        self.config_manager.update_alt_rate(alt_rate, user)

    # mark
    def update_alt_symbol(self, alt_symbol, user):
        self.config_manager.update_alt_symbol(alt_symbol, user)

    # mark logic!
    def update_merkleproof_settings(self, validate_bool):
        if validate_bool is True and self.info.get("pruned") is True:
            validate_bool = False
            logger.warning("Cannot enable merkleproof setting on pruned node.")
        self.config_manager.update_merkleproof_settings(validate_bool)

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
        res = self.rpc.estimatesmartfee(blocks)
        if "feerate" not in res and self.is_liquid:
            return 0.000001
        return res

    @property
    def bitcoind_path(self):
        bitcoind_path = os.path.join(self.data_folder, "bitcoin-binaries/bin/bitcoind")

        if platform.system() == "Windows":
            bitcoind_path += ".exe"
        return bitcoind_path

    @property
    def info(self):
        return self.node.info

    @property
    def network_info(self):
        return self.node.network_info

    @property
    def bitcoin_core_version(self):
        return self.node.bitcoin_core_version

    @property
    def bitcoin_core_version_raw(self):
        return self.node.bitcoin_core_version_raw

    @property
    def chain(self):
        return self.node.chain

    @property
    def network_parameters(self):
        return self.node.network_parameters

    @property
    def is_testnet(self):
        return self.node.is_testnet

    @property
    def is_liquid(self):
        return is_liquid(self.chain)

    @property
    def user_config(self):
        return self.config if self.user.is_admin else self.user.config

    @property
    def active_node_alias(self):
        return self.user_config.get("active_node_alias", "default")

    @property
    def explorer(self):
        return self.user_config.get("explorers", {}).get(self.chain, "")

    @property
    def explorer_id(self):
        return self.user_config.get("explorer_id", {}).get(self.chain, "CUSTOM")

    @property
    def asset_labels(self):
        user_assets = self.user_config.get("asset_labels", {}).get(self.chain, {})
        node_assets = self.node.asset_labels
        asset_labels = {}
        deep_update(asset_labels, node_assets)
        deep_update(asset_labels, user_assets)
        return asset_labels

    @property
    def default_asset(self):
        """returns hash of LBTC"""
        if self._default_asset is None:
            for asset, lbl in self.asset_labels.items():
                if lbl == "LBTC":
                    self._default_asset = asset
                    return asset
        return self._default_asset

    def asset_label(self, asset):
        if asset == "":
            return ""
        return get_asset_label(asset, known_assets=self.asset_labels)

    def update_asset_label(self, asset, label):
        if asset == self.default_asset:
            raise SpecterError("LBTC should stay LBTC")
        self.config_manager.update_asset_label(asset, label, self.chain, self.user)

    @property
    def fee_estimator(self):
        return self.user_config.get("fee_estimator", "mempool")

    @property
    def tor_type(self):
        return self.user_config.get("tor_type", "builtin")

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
    def weight_unit(self):
        return self.user_config.get("weight_unit", "oz")

    @property
    def alt_rate(self):
        return self.user_config.get("alt_rate", 1)

    @property
    def alt_symbol(self):
        return self.user_config.get("alt_symbol", "BTC")

    @property
    def admin(self):
        for u in self.user_manager.users:
            if u.is_admin:
                return u

    @property
    def user(self):
        return self.user_manager.user

    @property
    def config_manager(self):
        if not hasattr(self, "_config_manager"):
            self._config_manager = ConfigManager(self.data_folder)
        return self._config_manager

    @property
    def device_manager(self):
        return self.user.device_manager

    @property
    def wallet_manager(self):
        return self.user.wallet_manager

    @property
    def otp_manager(self):
        if not hasattr(self, "_otp_manager"):
            self._otp_manager = OtpManager(self.data_folder)
        return self._otp_manager

    @property
    def hide_sensitive_info(self):
        return self.user_config.get("hide_sensitive_info", False)

    def requests_session(self, force_tor=False):
        requests_session = requests.Session()
        if self.only_tor or force_tor:
            proxy_url = self.proxy_url
            proxy_parsed_url = urlparse(self.proxy_url)
            proxy_url = proxy_parsed_url._replace(
                netloc="{}:{}@{}".format(
                    str(random.randint(10000, 0x7FFFFFFF)),
                    "random",
                    proxy_parsed_url.netloc,
                )
            ).geturl()
            requests_session.proxies["http"] = proxy_url
            requests_session.proxies["https"] = proxy_url
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

    # Migrating RPC nodes from Specter 1.3.1 and lower (prior to the node manager)
    def migrate_old_node_format(self):
        if not os.path.isdir(os.path.join(self.data_folder, "nodes")):
            os.mkdir(os.path.join(self.data_folder, "nodes"))
        old_rpc = self.config.get("rpc", None)
        old_internal_rpc = self.config.get("internal_node", None)
        if old_internal_rpc and os.path.isfile(self.bitcoind_path):
            internal_node = InternalNode(
                "Specter Bitcoin",
                "specter_bitcoin",
                old_internal_rpc.get("autodetect", False),
                old_internal_rpc.get("datadir", get_default_datadir()),
                old_internal_rpc.get("user", ""),
                old_internal_rpc.get("password", ""),
                old_internal_rpc.get("port", 8332),
                old_internal_rpc.get("host", "localhost"),
                old_internal_rpc.get("protocol", "http"),
                os.path.join(
                    os.path.join(self.data_folder, "nodes"), "specter_bitcoin.json"
                ),
                self,
                self.bitcoind_path,
                "mainnet",
                "0.20.1",
            )
            logger.info(f"persisting {internal_node} in migrate_old_node_format")
            write_node(
                internal_node,
                os.path.join(
                    os.path.join(self.data_folder, "nodes"), "specter_bitcoin.json"
                ),
            )
            del self.config["internal_node"]
            if not old_rpc or not old_rpc.get("external_node", True):
                self.config_manager.update_active_node("specter_bitcoin")

        if old_rpc:
            node = Node(
                "Bitcoin Core",
                "default",
                old_rpc.get("autodetect", True),
                old_rpc.get("datadir", get_default_datadir()),
                old_rpc.get("user", ""),
                old_rpc.get("password", ""),
                old_rpc.get("port", None),
                old_rpc.get("host", "localhost"),
                old_rpc.get("protocol", "http"),
                True,
                os.path.join(os.path.join(self.data_folder, "nodes"), "default.json"),
                self,
            )
            logger.info(f"persisting {node} in migrate_old_node_format")
            write_node(
                node,
                os.path.join(os.path.join(self.data_folder, "nodes"), "default.json"),
            )
            del self.config["rpc"]
        self._save()


class SpecterConfiguration:
    """An abstract class which only holds functionality relevant for storage of information mostly
    deferring to ConfigManager.
    Do not put logic in here, which is not directly relevant for the config.json.
    Do not deal with the config.json directly but implement that in the ConfigManager
    """

    pass
    # ToDo: move all the methods above here.
