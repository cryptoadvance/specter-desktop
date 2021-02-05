import os
import json
import logging
from .helpers import alias, load_jsons
from .rpc import get_default_datadir

from .persistence import write_device, delete_file, delete_folder

logger = logging.getLogger(__name__)


class ServiceManager:
    """A ServiceManager which is quite dumb right now but it should decide which services to show"""

    def __init__(self, specter):
        self.specter = specter
        self._services = {
            "vaultoro": {
                "name": "vaultoro",
                "title": "Vaultoro",
                "logo": "img/Vaultoro-logo-white.svg",
                "desc": "A Bitcoin and precious metals exchange allows trading Bitcoin against Gold and Silver",
            },
            "dummyservice": {
                "name": "dummyservice",
                "title": "dummyservice",
                "logo": "",
                "desc": "Does nothing but can be switched on or off",
            },
        }

    def set_active_services(self, services):
        self.specter.update_services(services)

    @property
    def services(self):
        services = self._services
        for service_name in services:
            if service_name in self.specter.config.get("services", []):
                services[service_name]["active"] = True
            else:
                services[service_name]["active"] = False
        return services

    @property
    def active_services(self):
        services = self._services
        for service_name in services:
            if not service_name in self.specter.config.get("services", []):
                del services[service_name]
        return services
