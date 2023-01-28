"""
Here Configuration of your Extension takes place
"""

import os


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


class BaseConfig:
    """This is a extension-based Config which is used as Base"""

    SPECTER_GRAPHQL_ACTIVE = _get_bool_env_var("SPECTER_GRAPHQL_ACTIVE", "True")


class ProductionConfig(BaseConfig):
    """This is a extension-based Config for Production"""

    SPECTER_GRAPHQL_ACTIVE = _get_bool_env_var("SPECTER_GRAPHQL_ACTIVE", "False")
