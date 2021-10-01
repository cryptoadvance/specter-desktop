import logging
from ..specter_migrator import SpecterMigration

logger = logging.getLogger(__name__)


class SpecterMigration_0000(SpecterMigration):
    # the version that the stuff which is suppose to be migrated has been introduced
    # If this instance has been started AFTER this version, then this migration will never
    # get executed ( see the default-implementation of SpecterMigration.should_execute())
    version = "v1.5.0"

    def __init__(self, specter_migrator):
        self.specter_migrator = specter_migrator

    def execute(self):
        logger.debug(
            f"migration_0000 is an example method showing how to implement a migration"
        )
