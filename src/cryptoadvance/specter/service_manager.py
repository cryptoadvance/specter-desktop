import os
import json
import logging
from .helpers import alias, load_jsons
from .rpc import get_default_datadir

from .persistence import write_device, delete_file, delete_folder

logger = logging.getLogger(__name__)


class ServiceManager:
    """A ServiceManager which is quite dumb right now but it should decide which services to show"""

    def __init__(self):
        self.services = {"vaultoro": None}

    @property
    def services_names(self):
        return sorted(self.services.keys())
