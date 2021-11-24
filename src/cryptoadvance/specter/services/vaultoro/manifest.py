import os

from ..service import Service, devstatus_alpha


class VaultoroService(Service):
    id = "vaultoro"
    name = "vaultoro"
    logo = "img/Vaultoro-logo-white.svg"
    devstatus = devstatus_alpha
    desc = "A Bitcoin and precious metals exchange allows trading Bitcoin against Gold and Silver"

    # The API for the Vaultoro Service
    VAULTORO_API = os.getenv("VAULTORO_API", "https://api.vaultoro.com/v1")

    # TODO: As more Services are integrated, we'll want more robust categorization and sorting logic
    sort_priority = 3