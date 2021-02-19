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
    # CERT and KEY is for running self-signed-ssl-certs. Check cli_server for details
    CERT = os.getenv("CERT", None)
    KEY = os.getenv("KEY", None)
    # This will get passed to initialize the specter-object
    DEFAULT_SPECTER_CONFIG = {}

    # only used by cli_bitcoind.py, we want to have that static for the same reason
    BTCD_REGTEST_DATA_DIR = os.getenv(
        "BTCD_REGTEST_DATA_DIR", "/tmp/specter_btc_regtest_plain_datadir"
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


class DevelopmentConfig(BaseConfig):
    # https://stackoverflow.com/questions/22463939/demystify-flask-app-secret-key
    SECRET_KEY = "development key"


class TestConfig(BaseConfig):
    SECRET_KEY = "test key"


class CypressTestConfig(TestConfig):
    SPECTER_DATA_FOLDER = os.path.expanduser(
        os.getenv("SPECTER_DATA_FOLDER", "~/.specter-cypress")
    )
    PORT = os.getenv("PORT", 25444)

    # need to be static in order to (un-)tar bitcoind-dirs reliable
    DEFAULT_SPECTER_CONFIG = {"uid": "123456"}

    BTCD_REGTEST_DATA_DIR = os.getenv(
        "BTCD_REGTEST_DATA_DIR", "/tmp/specter_cypress_btc_regtest_plain_datadir"
    )


class ProductionConfig(BaseConfig):
    SECRET_KEY = secrets.token_urlsafe(16)
