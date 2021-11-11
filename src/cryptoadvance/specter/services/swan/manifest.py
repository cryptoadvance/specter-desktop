from ..service_manager import Service


class SwanService(Service):
    id = "swan"
    name = "Swan"
    logo = "img/swan.svg"
    desc = "Swan is the best way to accumulate Bitcoin with automatic recurring buys and instant buys."
    has_blueprint = True
