"""
Swan API uses PKCE OAuth2. Per Swan's API team: The client secret here is not considered
to be a real secret. There is no reasonable attack vector for this secret being public.
"""


class BaseConfig:
    # Unfortunately this setup is currently broken
    # It worked for the original and now legacy api-dev.swanbitcoin.com
    # But the new one doesn't have that configuration configured.
    SWAN_CLIENT_ID = "specter-dev"
    SWAN_CLIENT_SECRET = (
        "BcetcVcmueWf5P3UPJnHhCBMQ49p38fhzYwM7t3DJGzsXSjm89dDR5URE46SY69j"
    )
    SWAN_API_URL = "https://api.dev.swanbitcoin.com"
    SWAN_FRONTEND_URL = "https://app.dev.swanbitcoin.com/signup"

    # There is a whitelist at the oauth2-infra of swan which is hopefully in sync with this list:
    SWAN_ALLOWED_SPECTER_HOSTNAMES = [
        "localhost:25441",
        "umbrel.local:25441",
        "citadel.local:25441",
        "specter.local:25441",
    ]


class ProductionConfig(BaseConfig):
    SWAN_CLIENT_ID = "specter"
    SWAN_CLIENT_SECRET = (
        "UcqMZw3D70#E*Zo1hnC8f8P^Ils^6wligXMB*vL1fX@DYm6zloDI#p9Eemk8!y9#"
    )
    SWAN_API_URL = "https://api.swanbitcoin.com"
    SWAN_FRONTEND_URL = "https://www.swanbitcoin.com/Specter/"
