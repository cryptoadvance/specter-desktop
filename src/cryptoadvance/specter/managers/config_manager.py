import logging
import os
import random
import secrets
import threading
import time
from urllib.parse import urlparse


from ..helpers import deep_update
from ..persistence import read_json_file, write_json_file
from ..specter_error import SpecterError
from .genericdata_manager import GenericDataManager

logger = logging.getLogger(__name__)


class ConfigManager(GenericDataManager):
    """
    The ConfigManager manages the configuration persisted in config.json
    It's not suppose to have any side-effects. Setting and getting only
    with a lot of validation and computing while setting/getting
    """

    initial_data = {}
    name_of_json_file = "config.json"
    lock = threading.Lock()

    def __init__(self, data_folder, config={}):
        super().__init__(data_folder)
        self.arg_config = config
        self.data = {
            "auth": {
                "method": "none",
                "password_min_chars": 6,
                "rate_limit": 10,
                "registration_link_timeout": 1,
            },
            "explorers": {"main": "", "test": "", "regtest": "", "signet": ""},
            "explorer_id": {
                "main": "CUSTOM",
                "test": "CUSTOM",
                "regtest": "CUSTOM",
                "signet": "CUSTOM",
            },
            # user-defined asset labels for liquid
            "asset_labels": {
                "liquidv1": {},
            },
            "active_node_alias": "default",
            "proxy_url": "socks5h://localhost:9050",  # Tor proxy URL
            "only_tor": False,
            "tor_control_port": "",
            "tor_status": False,  # Should start Tor hidden service on startup?
            "hwi_bridge_url": "/hwi/api/",
            # unique id that will be used in wallets path in Bitcoin Core
            # empty by default for backward-compatibility
            "uid": "",
            "unit": "btc",
            "price_check": False,
            "alt_rate": 1,
            "alt_symbol": "BTC",
            "price_provider": "",
            "weight_unit": "oz",
            "validate_merkle_proofs": False,
            "fee_estimator": "mempool",
            "fee_estimator_custom_url": "",
            "hide_sensitive_info": False,
            # TODO: remove
            "bitcoind": False,
        }
        self.check_config()

    def check_config(self):
        """
        Updates config if file config have changed.
        Priority (low to high):
        - existing / default config
        - file config from config.json
        - arg_config passed in constructor
        """

        # if config.json file exists - load from it
        if os.path.isfile(self.data_file):
            with self.lock:
                file_config = read_json_file(self.data_file)
                migrate_config(file_config)
                deep_update(self.data, file_config)
            # otherwise - create one and assign unique id
        else:
            # unique id of specter
            if self.data["uid"] == "":
                self.config["uid"] = (
                    random.randint(0, 256 ** 8).to_bytes(8, "big").hex()
                )
            self._save()

        # config from constructor overrides file config
        deep_update(self.data, self.arg_config)

    def update_active_node(self, node_alias):
        """set the current active node to use"""
        self.data["active_node_alias"] = node_alias
        self._save()

    def update_auth(self, method, rate_limit, registration_link_timeout):
        """simply persisting the current auth-choice"""
        auth = self.data["auth"]
        if auth["method"] != method:
            auth["method"] = method
        if auth["rate_limit"] != rate_limit:
            auth["rate_limit"] = rate_limit
        if auth["registration_link_timeout"] != registration_link_timeout:
            auth["registration_link_timeout"] = registration_link_timeout
        self._save()

    def update_asset_label(self, asset, label, chain, user):
        if user.is_admin:
            if "asset_labels" not in self.data:
                self.data["asset_labels"] = {}
            deep_update(self.data["asset_labels"], {chain: {asset: label}})
            self._save()
        else:
            user.update_asset_label(asset, label, chain)

    def update_explorer(self, explorer_id, explorer_data, user, chain):
        """update the block explorers urls"""
        if isinstance(user, str):
            raise Exception("Please pass a real user, not a string-user")
        # we don't know what chain to change
        if not chain:
            return

        if explorer_id == "CUSTOM":
            if explorer_data["url"] and not explorer_data["url"].endswith("/"):
                # make sure the urls end with a "/"
                explorer_data["url"] += "/"
        else:
            chain_name = (
                ""
                if (chain == "main" or chain == "regtest")
                else ("signet/" if self.chain == "signet" else "testnet/")
            )
            explorer_data["url"] += chain_name
        # update the urls in the app config
        if user.is_admin:
            self.data["explorers"][chain] = explorer_data["url"]
            self.data["explorer_id"][chain] = explorer_id
            self._save()
        else:
            user.set_explorer(explorer_id, explorer_data["url"])

    def update_fee_estimator(self, fee_estimator, custom_url, user):
        """update the fee estimator option and its url if custom"""
        if isinstance(user, str):
            raise Exception("Please pass a real user, not a string-user")
        fee_estimator_options = ["mempool", "bitcoin_core", "custom"]

        if fee_estimator not in fee_estimator_options:
            raise SpecterError("Invalid fee estimator option specified.")

        if user.is_admin:
            self.data["fee_estimator"] = fee_estimator
            if fee_estimator == "custom":
                self.data["fee_estimator_custom_url"] = custom_url
            self._save()
        else:
            user.set_fee_estimator(fee_estimator, custom_url)

    def update_proxy_url(self, proxy_url, user):
        """update the Tor proxy url"""
        if self.data["proxy_url"] != proxy_url:
            self.data["proxy_url"] = proxy_url
            self._save()

    def update_tor_type(self, tor_type, user):
        """update the Tor type to use"""
        if self.data.get("tor_type", "builtin") != tor_type:
            self.data["tor_type"] = tor_type
            self._save()

    def toggle_tor_status(self):
        """toggle the Tor status"""
        self.data["tor_status"] = not self.data["tor_status"]
        self._save()

    def update_only_tor(self, only_tor, user):
        """switch whatever to use Tor for all calls"""
        if self.data["only_tor"] != only_tor:
            self.data["only_tor"] = only_tor
            self._save()

    def update_tor_control_port(self, tor_control_port, user):
        """set the control port of the tor daemon"""
        if self.data["tor_control_port"] != tor_control_port:
            self.data["tor_control_port"] = tor_control_port
            self._save()
            self.update_tor_controller()

    def generate_torrc_password(self, overwrite=False):
        if "torrc_password" not in self.data or overwrite:
            self.data["torrc_password"] = secrets.token_urlsafe(16)
            self._save()
            logger.info(f"Generated torrc_password in {self.data_file}")
        else:
            logger.info(
                f"torrc_password in {self.data_file} already set. Skipping generation"
            )

    def update_hwi_bridge_url(self, url, user):
        """update the hwi bridge url to use"""
        if isinstance(user, str):
            raise Exception("Please pass a real user, not a string-user")
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
            self.data["hwi_bridge_url"] = url
            self._save()
        else:
            user.set_hwi_bridge_url(url)

    def update_unit(self, unit, user):
        if isinstance(user, str):
            raise Exception("Please pass a real user, not a string-user")
        if user.is_admin:
            self.data["unit"] = unit
            self._save()
        else:
            user.set_unit(unit)

    # mark
    def update_price_check_setting(self, price_check_bool, user):
        if isinstance(user, str):
            raise Exception("Please pass a real user, not a string-user")
        if user.is_admin:
            self.data["price_check"] = price_check_bool
            self._save()
        else:
            user.set_price_check(price_check_bool)
        # mark This needs to be done in specter
        # if price_check_bool and (self.price_provider and self.user == user):
        #    self.price_checker.start()
        # else:
        #    self.price_checker.stop()

    def update_hide_sensitive_info(self, hide_sensitive_info_bool, user):
        if isinstance(user, str):
            raise Exception("Please pass a real user, not a string-user")
        if user.is_admin:
            self.data["hide_sensitive_info"] = hide_sensitive_info_bool
            self._save()
        else:
            user.set_hide_sensitive_info(hide_sensitive_info_bool)

    def update_price_provider(self, price_provider, user):
        if isinstance(user, str):
            raise Exception("Please pass a real user, not a string-user")
        if user.is_admin:
            self.data["price_provider"] = price_provider
            self._save()
        else:
            user.set_price_provider(price_provider)

    def update_weight_unit(self, weight_unit, user):
        if isinstance(user, str):
            raise Exception("Please pass a real user, not a string-user")
        if user.is_admin:
            self.data["weight_unit"] = weight_unit
            self._save()
        else:
            user.set_weight_unit(weight_unit)

    def update_alt_rate(self, alt_rate, user):
        if isinstance(user, str):
            raise Exception("Please pass a real user, not a string-user")
        alt_rate = round(float(alt_rate), 2)
        if user.is_admin:
            self.data["alt_rate"] = alt_rate
            self._save()
        else:
            user.set_alt_rate(alt_rate)

    def update_alt_symbol(self, alt_symbol, user):
        if isinstance(user, str):
            raise Exception("Please pass a real user, not a string-user")
        if user.is_admin:
            self.data["alt_symbol"] = alt_symbol
            self._save()
        else:
            user.set_alt_symbol(alt_symbol)

    # logic?!
    def update_merkleproof_settings(self, validate_bool):
        self.data["validate_merkle_proofs"] = validate_bool
        self._save()


def migrate_config(config):
    # migrate old "auth" string into new "auth" json subtree
    if "auth" in config:
        if isinstance(config["auth"], str):
            config["auth"] = dict(method=config["auth"])
