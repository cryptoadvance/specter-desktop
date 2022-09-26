import logging
import os
import shutil

from urllib3.exceptions import NewConnectionError
from requests.exceptions import ConnectionError

from cryptoadvance.specter.specter_error import SpecterError
from ...config import BaseConfig
from ..specter_migrator import SpecterMigration
from ...helpers import load_jsons
from ...managers.service_manager import ServiceManager
from ...specter import Specter

logger = logging.getLogger(__name__)


class SpecterMigration_0002(SpecterMigration):
    version = "v1.13.1"  # the version this migration has been rolled out
    # irrelevant though because we'll execute this script in any case
    # as we can't have yet a say on when specter has been started first

    def should_execute(self):
        # This Migration cannot rely on the default-mechanism as the migration_framework was not
        # in place when the functionality has been implemented
        return True

    @property
    def description(self) -> str:
        return """Add the notification service for all users"""

    def execute(self):
        specter = Specter(data_folder=self.data_folder)
        specter.service_manager.add_required_services_to_users(
            specter.user_manager.users, force_opt_out=True
        )
        specter.user_manager.save()
        specter.cleanup_on_exit()
