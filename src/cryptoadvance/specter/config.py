""" A config module contains static configuration """
import configparser
import datetime
import os
import random
import secrets
from pathlib import Path

from dotenv import load_dotenv

# BASEDIR = os.path.abspath(os.path.dirname(__file__))

# Loading env-vars from .flaskenv (4 levels above this file)
env_path = Path("../../../..") / ".flaskenv"
load_dotenv(env_path)


def _get_bool_env_var(varname, default=None):

    value = os.environ.get(varname, default)

    if value is None:
        return False
    elif isinstance(value, str) and value.lower() == "false":
        return False
    elif bool(value) is False:
        return False
    else:
        return bool(value)


DEFAULT_CONFIG = "cryptoadvance.specter.config.DevelopmentConfig"


class BaseConfig(object):
    PORT = os.getenv("PORT", 25441)
    CONNECT_TOR = _get_bool_env_var(os.getenv("CONNECT_TOR", "False"))
    SPECTER_DATA_FOLDER = os.path.expanduser(
        os.getenv("SPECTER_DATA_FOLDER", "~/.specter")
    )
    SPECTER_API_ACTIVE = _get_bool_env_var("SPECTER_API_ACTIVE", "False")
    # Logging
    # SPECTER_LOGFILE will get created dynamically in server.py
    # using:
    SPECTER_LOGFORMAT = os.getenv(
        "SPECTER_LOGFORMAT", "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    )

    # CERT and KEY is for running self-signed-ssl-certs. Check cli_server for details
    CERT = os.getenv("CERT", None)
    KEY = os.getenv("KEY", None)
    # This will get passed to initialize the specter-object
    DEFAULT_SPECTER_CONFIG = {}

    # only used by cli_bitcoind.py, we want to have that static for the same reason
    BTCD_REGTEST_DATA_DIR = os.getenv(
        "BTCD_REGTEST_DATA_DIR", "/tmp/specter_btc_regtest_plain_datadir"
    )

    # only used by cli_node.py, we want to have that static for the same reason
    ELMD_REGTEST_DATA_DIR = os.getenv(
        "ELMD_REGTEST_DATA_DIR", "/tmp/specter_elm_regtest_plain_datadir"
    )

    # The self-signed ssl-certificate which is lazily created is configurable to a certain extent
    SPECTER_SSL_CERT_SUBJECT_C = os.getenv("SPECTER_SSL_CERT_SUBJECT_C", "DE")
    SPECTER_SSL_CERT_SUBJECT_ST = os.getenv("SPECTER_SSL_CERT_SUBJECT_ST", "BDW")
    SPECTER_SSL_CERT_SUBJECT_L = os.getenv("SPECTER_SSL_CERT_SUBJECT_L", "Freiburg")
    SPECTER_SSL_CERT_SUBJECT_O = os.getenv(
        "SPECTER_SSL_CERT_SUBJECT_O", "Specter Citadel Cert"
    )
    SPECTER_SSL_CERT_SUBJECT_OU = os.getenv(
        "SPECTER_SSL_CERT_SUBJECT_OU", "Specter Citadel Cert"
    )
    SPECTER_SSL_CERT_SUBJECT_CN = os.getenv(
        "SPECTER_SSL_CERT_SUBJECT_CN", "Specter Citadel Cert"
    )
    # For self-signed certs, serial-number collision is a risk, so let's do a random one by default
    SPECTER_SSL_CERT_SERIAL_NUMBER = int(
        os.getenv("SPECTER_SSL_CERT_SERIAL_NUMBER", random.randrange(1, 100000))
    )
    INTERNAL_BITCOIND_VERSION = os.getenv("INTERNAL_BITCOIND_VERSION", "0.21.1")

    # Block explorers URLs
    EXPLORERS_LIST = {
        "MEMPOOL_SPACE": {
            "name": "Mempool.space",
            "url": "https://mempool.space/",
        },
        "MEMPOOL_SPACE_ONION": {
            "name": "Mempool.space Tor hidden service",
            "url": "http://mempoolhqx4isw62xs7abwphsq7ldayuidyx2v2oethdhhj6mlo2r6ad.onion/",
        },
        "BLOCKSTREAM_INFO": {
            "name": "Blockstream.info",
            "url": "https://blockstream.info/",
        },
        "BLOCKSTREAM_INFO_ONION": {
            "name": "Blockstream.info Tor hidden service",
            "url": "http://explorerzydxu5ecjrkwceayqybizmpjjznk5izmitf2modhcusuqlid.onion/",
        },
        "CUSTOM": {
            "name": "Custom",
            "url": "",
        },
    }

    # Babel integration. English listed first; other alphabetical by language code
    LANGUAGES = {
        "en": "English",
        "bg": "Български",
        "de": "Deutsch",
        "el": "Ελληνικά",
        "es": "Español",
        "fr": "Français",
        "he": "עברית",
        "hi": "हिंदी",
        "nl": "Nederlands",
        "pl": "Polski",
        "pt": "Português",
        "ru": "Русский",
        "sv": "Svenska",
        "zh_Hans_CN": "简体中文",
        "zh_Hant_TW": "繁體中文",
    }


class DevelopmentConfig(BaseConfig):
    # https://stackoverflow.com/questions/22463939/demystify-flask-app-secret-key
    SECRET_KEY = "development key"
    SPECTER_DATA_FOLDER = os.path.expanduser(
        os.getenv("SPECTER_DATA_FOLDER", "~/.specter_dev")
    )
    # API active by default in dev-mode
    SPECTER_API_ACTIVE = _get_bool_env_var("SPECTER_API_ACTIVE", "True")

    # Env vars take priority over config settings so ensure that this is set
    os.environ["FLASK_ENV"] = "development"


class TestConfig(BaseConfig):
    SECRET_KEY = "test key"
    # This should never be used as the data-folder is injected at runtime
    # But let's be sure before something horrible happens:
    SPECTER_DATA_FOLDER = os.path.expanduser(
        os.getenv("SPECTER_DATA_FOLDER", "~/.specter_testing")
    )
    # API active by default in test-mode
    SPECTER_API_ACTIVE = _get_bool_env_var("SPECTER_API_ACTIVE", "True")


class CypressTestConfig(TestConfig):
    SPECTER_DATA_FOLDER = os.path.expanduser(
        os.getenv("SPECTER_DATA_FOLDER", "~/.specter_cypress")
    )
    PORT = os.getenv("PORT", 25444)

    # need to be static in order to (un-)tar bitcoind-dirs reliable
    DEFAULT_SPECTER_CONFIG = {"uid": "123456"}

    BTCD_REGTEST_DATA_DIR = os.getenv(
        "BTCD_REGTEST_DATA_DIR", "/tmp/specter_cypress_btc_regtest_plain_datadir"
    )

    BTCD_REGTEST_DATA_DIR = os.getenv(
        "BTCD_REGTEST_DATA_DIR", "/tmp/specter_cypress_elm_regtest_plain_datadir"
    )


class ProductionConfig(BaseConfig):
    SECRET_KEY = secrets.token_urlsafe(16)
