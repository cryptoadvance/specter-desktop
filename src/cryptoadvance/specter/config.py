''' A config module contains static configuration '''
import os
import datetime
try:
    # Python 2.7
    import ConfigParser as configparser
except ImportError:
    # Python 3
    import configparser

# BASEDIR = os.path.abspath(os.path.dirname(__file__))


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
    pass

class DevelopmentConfig(BaseConfig):
    # https://stackoverflow.com/questions/22463939/demystify-flask-app-secret-key
    SECRET_KEY='development key'

class TestConfig(BaseConfig):
    SECRET_KEY='test key'

class ProductionConfig(BaseConfig):
    pass
    
