class BaseConfig:
    SWAN_API_URL = "https://dev-api.swanbitcoin.com"


class ProductionConfig(BaseConfig):
    SWAN_API_URL = "https://api.swanbitcoin.com"
