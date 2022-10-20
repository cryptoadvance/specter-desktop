"""
Here Configuration of your Extension takes place
"""


class BaseConfig:
    """This is a extension-based Config which is used as Base"""

    DEVELOPER_JAVASCRIPT_PYTHON_CONSOLE = False


class DevelopmentConfig(BaseConfig):
    DEVELOPER_JAVASCRIPT_PYTHON_CONSOLE = True
