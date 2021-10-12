import logging
from ..specter_migrator import SpecterMigration

logger = logging.getLogger(__name__)


class SpecterMigration_0000(SpecterMigration):
    # the version that the stuff which is suppose to be migrated has been introduced
    # If this instance has been started AFTER this version, then this migration will never
    # get executed ( see the default-implementation of SpecterMigration.should_execute())
    version = "v1.5.0"  # Faking it here for the unit-tests

    def __init__(self, specter_migrator):
        self.specter_migrator = specter_migrator

    def execute(self):
        logger.debug(
            f"migration_0000 is an example method showing how to implement a migration"
        )

    @property
    def description(self) -> str:
        """Should return a (multiline) description of the migration which will get log.info() at execution-time"""
        return """A dummy migration:
            * It will do nothing
            * It's just here to explain how SpecterMigration works
            * It will be shown in the logs when it's executed (just like the other real migrations but doing nothing)
        """
