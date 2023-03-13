"""
Here Configuration of your Extension takes place
"""

import os


class BaseConfig:
    """This is a extension-based Config which is used as Base"""

    # Either "bin" or "lib". It'll decide which HWIBridge Impl will be used
    HWI_RPC_IMPL = "lib"

    HWI_BIN_VERSION = "2.2.1"
    HWI_BIN_HASH = "93ed5fc6eb7d66a466e84d3fd0601fd30b312c8bed4576cd3e78e9e281976816"


class DevelopmentConfig(BaseConfig):
    HWI_RPC_IMPL = os.getenv("HWI_RPC_IMPL", "bin")


class ProductionConfig(BaseConfig):
    """This is a extension-based Config for Production"""

    HWI_RPC_IMPL = "lib"
