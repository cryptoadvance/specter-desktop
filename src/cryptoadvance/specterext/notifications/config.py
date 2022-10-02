"""
Here Configuration of your Extension takes place
"""


class BaseConfig:
    """This is a extension-based Config which is used as Base"""

    SPECTER_NOTIFICATIONS_WEBSOCKETS_ENABLED = True


class ProductionConfig(BaseConfig):
    """This is a extension-based Config for Production"""

    pass


class TestConfig(BaseConfig):
    """This is a extension-based Config for Production"""

    SPECTER_NOTIFICATIONS_WEBSOCKETS_ENABLED = False


class CypressTestConfig(TestConfig):
    SPECTER_NOTIFICATIONS_WEBSOCKETS_ENABLED = True
