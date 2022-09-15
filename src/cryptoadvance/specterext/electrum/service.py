import logging

from cryptoadvance.specter.services.service import (
    Service,
    devstatus_prod,
)

# A SpecterError can be raised and will be shown to the user as a red banner
from cryptoadvance.specter.specter_error import SpecterError
from flask import current_app as app
from cryptoadvance.specter.wallet import Wallet
from flask_apscheduler import APScheduler

logger = logging.getLogger(__name__)


class ElectrumService(Service):
    id = "electrum"
    name = "Electrum"
    icon = "electrum/img/electrum_lightblue.svg"
    logo = "electrum/img/electrum_lightblue.svg"
    desc = "electrum specific stuff"
    has_blueprint = True
    blueprint_module = "cryptoadvance.specterext.electrum.controller"
    devices = ["cryptoadvance.specterext.electrum.devices.electrum"]
    devstatus = devstatus_prod
    sort_priority = 99
    isolated_client = False
