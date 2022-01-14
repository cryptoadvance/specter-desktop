from ..service import Service, devstatus_alpha


class BitcoinReserveService(Service):
    id = "bitcoinreserve"
    name = "Bitcoin Reserve"
    icon = "img/bitcoinreserve_icon.svg"
    logo = "img/bitcoinreserve_icon.svg"
    desc = "Where Europe buys Bitcoin."
    has_blueprint = True
    devstatus = devstatus_alpha

    # TODO: As more Services are integrated, we'll want more robust categorization and sorting logic
    sort_priority = 2
