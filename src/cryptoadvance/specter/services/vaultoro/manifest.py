import os

from ..service_manager import Service, maturity_beta


class VaultoroService(Service):
    id = "vaultoro"
    name = "vaultoro"
    logo = "img/Vaultoro-logo-white.svg"
    maturity = maturity_beta
    desc = "A Bitcoin and precious metals exchange allows trading Bitcoin against Gold and Silver"

    # The API for the Vaultoro Service
    VAULTORO_API = os.getenv("VAULTORO_API", "https://api.vaultoro.com/v1")
