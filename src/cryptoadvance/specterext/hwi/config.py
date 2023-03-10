"""
Here Configuration of your Extension takes place
"""

import os


class BaseConfig:
    """This is a extension-based Config which is used as Base"""

    # Either "bin" or "lib". It'll decide which HWIBridge Impl will be used
    HWI_RPC_IMPL = "lib"


class DevelopmentConfig:
    HWI_RPC_IMPL = os.getenv("HWI_RPC_IMPL", "bin")


class ProductionConfig(BaseConfig):
    """This is a extension-based Config for Production"""

    HWI_RPC_IMPL = "lib"
