class Singleton:
    _instance = None

    def __init__(self):
        # Singleton pattern must prevent normal instantiation
        raise Exception(
            "Cannot directly instantiate a Singleton. Access via get_instance()"
        )

    @classmethod
    def get_instance(cls):
        # This is the only way to access the one and only instance
        if cls._instance is None:
            cls._instance = cls.__new__(cls)
        return cls._instance


class ConfigurableSingletonException(Exception):
    pass


class ConfigurableSingleton(Singleton):
    @classmethod
    def get_instance(cls):
        # This is the only way to access the one and only instance
        if cls._instance:
            return cls._instance
        else:
            raise ConfigurableSingletonException(
                f"Must call {cls.__name__}.configure_instance(config) first"
            )

    @classmethod
    def configure_instance(cls, **kwargs):
        # Must be called before the first get_instance() call
        if cls._instance:
            raise ConfigurableSingletonException(f"{cls.__name__} already configured")

        # Instantiate the one and only instance
        cls._instance = cls.__new__(cls)
