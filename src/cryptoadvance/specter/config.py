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
    # You got redirected here if you hit "/". This doesn't work anymore (at least for "/") if you modify APP_URL_PREFIX
    ROOT_URL_REDIRECT = "/spc"

    # Some notes to all three *_URL_PREFIX
    # For all of them, either set them to "" or "/something". Never "/".
    # SESSION_COOKIE_PATH is critical to control if you change any *_URL_PREFIX
    # Especially true if you overwrite one of them in a derivation-class.
    # In doubt, always do this in the end:
    # SESSION_COOKIE_PATH = SPECTER_URL_PREFIX

    # Enables mounting the specter including extensions somewhere else as "/"
    APP_URL_PREFIX = os.getenv("APP_URL_PREFIX", "")
    # The prefix for mounting all Specter-Core-blueprints (and non isolated_client extensions)
    SPECTER_URL_PREFIX = "/spc"
    # This enables the isolated_client-extensions, SECURITY-CRITICAL
    SESSION_COOKIE_PATH = SPECTER_URL_PREFIX
    # should be "strong" until you're running specter behind a loadbalancer which accesses specter with more than one IP
    SESSION_PROTECTION = os.getenv("SESSION_PROTECTION", "strong")
    SESSION_PROTECTION = None if SESSION_PROTECTION == "none" else SESSION_PROTECTION
    # The prefix for extensions which get access to the session cookie
    EXT_URL_PREFIX = "/spc/ext"
    # The prefix for extensions which don't get access to the session cookie (if SPECTER_URL_PREFIX isn't compromised)
    ISOLATED_CLIENT_EXT_URL_PREFIX = "/ext"

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

    # the default timeout for Bitcoin/Liquid RPC-calls
    BITCOIN_RPC_TIMEOUT = int(os.getenv("BITCOIN_RPC_TIMEOUT", "10"))
    LIQUID_RPC_TIMEOUT = int(os.getenv("LIQUID_RPC_TIMEOUT", "10"))

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
    # in seconds, tor is slow, so let's choose 10 seconds
    FEEESTIMATION_REQUEST_TIMEOUT = int(
        os.getenv("FEEESTIMATION_REQUEST_TIMEOUT", "10")
    )

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

    # Babel integration. List of languages written from right to left for RTL support in the UI
    RTL_LANGUAGES = ["he"]

    # One of "prod", "beta" or "alpha". Every Service below will be not available
    SERVICES_DEVSTATUS_THRESHOLD = os.getenv("SERVICES_DEVSTATUS_THRESHOLD", "prod")

    # If the Current Working Directory doesn't look like a Specter-desktop Source-Dir
    # it will try to load Services from that directory if True
    # THIS MIGHT BE A SECURITY_CRITICAL SETTING. DON'T SWITH TO TRUE IN PROD
    SERVICES_LOAD_FROM_CWD = False

    # List of extensions (services) to potentially load
    EXTENSION_LIST = [
        "cryptoadvance.specter.services.swan.service",
        "cryptoadvance.specterext.liquidissuer.service",
        "cryptoadvance.specter.services.bitcoinreserve.service",
        "cryptoadvance.specterext.devhelp.service",
    ]

    # This is just a placeholder in order to be aware that you cannot set this
    # It'll be filled up with the fully qualified Classname the Config is derived from
    SPECTER_CONFIGURATION_CLASS_FULLNAME = None
    # The user will get a warning if a request takes longer than this threshold
    REQUEST_TIME_WARNING_THRESHOLD = int(
        os.getenv("REQUEST_TIME_WARNING_THRESHOLD", "20")
    )

    # As described in https://github.com/cryptoadvance/specter-desktop/pull/1579#issuecomment-1049895972
    # This should get removed after v1.9.0 is out.
    SPECTER_URL_PREFIX = ""
    EXT_URL_PREFIX = "/svc"
    SESSION_COOKIE_PATH = SPECTER_URL_PREFIX


class DevelopmentConfig(BaseConfig):
    # https://stackoverflow.com/questions/22463939/demystify-flask-app-secret-key
    SECRET_KEY = "development key"

    # EXPLAIN_TEMPLATE_LOADING = os.getenv("EXPLAIN_TEMPLATE_LOADING", "False")

    SPECTER_DATA_FOLDER = os.path.expanduser(
        os.getenv("SPECTER_DATA_FOLDER", "~/.specter_dev")
    )
    # API active by default in dev-mode
    SPECTER_API_ACTIVE = _get_bool_env_var("SPECTER_API_ACTIVE", "True")

    # One of "prod", "beta" or "alpha". Every Service below will be not available
    SERVICES_DEVSTATUS_THRESHOLD = os.getenv("SERVICES_DEVSTATUS_THRESHOLD", "alpha")

    # Developing Extensions should be possible in DevelopmentConfig
    SERVICES_LOAD_FROM_CWD = True


class TestConfig(BaseConfig):
    # ToDo: remove the below line to test a scenario more close to the default-setup
    SPECTER_URL_PREFIX = ""
    SESSION_COOKIE_PATH = SPECTER_URL_PREFIX

    SECRET_KEY = "test key"
    # This should never be used as the data-folder is injected at runtime
    # But let's be sure before something horrible happens:
    SPECTER_DATA_FOLDER = os.path.expanduser(
        os.getenv("SPECTER_DATA_FOLDER", "~/.specter_testing")
    )
    # API active by default in test-mode
    SPECTER_API_ACTIVE = _get_bool_env_var("SPECTER_API_ACTIVE", "True")

    # See #1316 since Bitcoin v0.21.1 (not only) the importmulti-call takes longer than 10 seconds on cirrus
    BITCOIN_RPC_TIMEOUT = 60
    LIQUID_RPC_TIMEOUT = 60


class CypressTestConfig(TestConfig):
    SPECTER_URL_PREFIX = ""
    # For some reason cypress doesn't work with a scoped down session so we're setting here the unscoped again
    SESSION_COOKIE_PATH = SPECTER_URL_PREFIX
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
    BITCOIN_RPC_TIMEOUT = 30
    LIQUID_RPC_TIMEOUT = 40


class ProductionConfig(BaseConfig):
    # Injectable, as having a random SECRET-KEY won't work for gunicorn using more than one worker (might have more issues with multiple workers, though)
    SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(16))
    # There are some really slow machines out there. Creating a 2/4 multisig on an older MacBookAir
    # Take already >30secs
    BITCOIN_RPC_TIMEOUT = float(os.getenv("BITCOIN_RPC_TIMEOUT", "60"))
    LIQUID_RPC_TIMEOUT = float(os.getenv("LIQUID_RPC_TIMEOUT", "120"))

    # Repeating it here as it's SECURITY CRITICAL. Check comments in BaseConfig
    SERVICES_LOAD_FROM_CWD = False
    # SPECTER_URL_PREFIX = "/spc"
    # EXT_URL_PREFIX = "/spc/ext"
    # EXTERNAT_EXT_URL_PREFIX = "/ext"
    # SESSION_COOKIE_PATH = SPECTER_URL_PREFIX
