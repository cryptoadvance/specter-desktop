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
        self._services = [
            {
                "name": "vaultoro",
                "desc": "A Bitcoin Exchange to trade precious metals agains bitcoin",
            },
            {
                "name": "dummyservice",
                "desc": "Does nothing but can be switched on or off",
            },
        ]
        self._services = {
            "vaultoro": {
                "name": "vaultoro",
                "desc": "A Bitcoin Exchange to trade precious metals agains bitcoin",
            },
            "dummyservice": {
                "name": "dummyservice",
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
