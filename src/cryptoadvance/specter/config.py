''' A config module contains static configuration '''
import datetime
import os
from pathlib import Path

from dotenv import load_dotenv

try:
    # Python 2.7
    import ConfigParser as configparser
except ImportError:
    # Python 3
    import configparser

# BASEDIR = os.path.abspath(os.path.dirname(__file__))

# Loading env-vars from .flaskenv (4 levels above this file)
env_path = Path('../../../..') / '.flaskenv'
load_dotenv(env_path)

def _get_bool_env_var(varname, default=None):

    value = os.environ.get(varname, default)

    if value is None:
        return False
    elif isinstance(value, str) and value.lower() == 'false':
        return False
    elif bool(value) is False:
        return False
    else:
        return bool(value)

class BaseConfig(object):
    PORT=os.getenv("PORT",25441)
    CONNECT_TOR=_get_bool_env_var(os.getenv("CONNECT_TOR","False"))
    pass

class DevelopmentConfig(BaseConfig):
    # https://stackoverflow.com/questions/22463939/demystify-flask-app-secret-key
    SECRET_KEY='development key'

class TestConfig(BaseConfig):
    SECRET_KEY='test key'

class ProductionConfig(BaseConfig):
    pass
