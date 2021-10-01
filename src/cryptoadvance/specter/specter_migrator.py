""" The migrationManager handles all things necessary migrating from one specter version to another.
    It uses patterns from DB-migration-frameworks like flask-migrate and the like.
    The idea is to keep adding migration scripts to the SpecterMigrator and they are executed exactly
    once. In order to keep track of that, the SpecterMigrator uses a MigDataManager which stores
    events and migration_executions in a file called migration_data.json.
    * Events are purely informational and only for troubleshooting purposes.
    * migration_executions simply keeps track of which scrips has been executed.

"""
import inspect
import logging
import os
from datetime import datetime
from importlib import import_module
from inspect import isclass
from pathlib import Path
from pkgutil import iter_modules

from cryptoadvance import specter

from .managers.genericdata_manager import GenericDataManager
from .specter_error import SpecterError
from .util.version import VersionChecker, compare

logger = logging.getLogger(__name__)


class SpecterMigration:
    """All Migrations should derive from this class. In order to create one, have a look at
    the example in the migrations directory.
    """

    version = "custom"  # the version this has been introduced

    def __init__(self, specter_migrator):
        self.specter_migrator = specter_migrator
        self.data_folder = specter_migrator.data_folder

    def should_execute(self):
        """You can override this to prevent execution for specific cases"""
        version_first_started = self.specter_migrator.mig.first_event["version"]
        # We need to compare the version we have been started first with the version this migration
        # is suppose to migrate.
        # If version_first_started > self.version we don't need to execute this migration and will return False
        # Should we import semver? Ok, let's minimize dependencies and do it ourself here
        try:
            compare_version = compare(version_first_started, self.version)
        except SpecterError:
            # if in doubt because versions are unparsable, execute!
            return True
        if compare_version == 1:
            return True
        elif compare_version == -1:
            return False
        elif compare_version == 0:
            return False

    def execute(self):
        logger.debug(
            f"migration_0000 is an example method showing how to implement a migration"
        )


class MigDataManager(GenericDataManager):
    """A class handling the data for the SpecterMigrator in migration_data.json with some convenience-methods"""

    initial_data = {
        "events": [],  # contains elements like {"timestamp": someTimestamp, "version": "v1.5.0"}
        "migration_executions": [],  # contains elements like {"timestamp": someTimestamp, "migration_no": 0}
    }
    name_of_json_file = "migration_data.json"

    def __init__(self, data_folder):
        # creating folders if they don't exist
        # Usually Specter is doing that but in the case of tests, we're instantiated before Specter
        if not os.path.isdir(data_folder):
            os.makedirs(data_folder)
        super().__init__(data_folder)

    @property
    def events(self):
        """A list of events where one event represents the initial use of a new specter-version which is a different
        version than the one used before. Looks like: {"timestamp": someTimestamp, "version": "v1.5.0"}
        """
        return self.data["events"]

    @property
    def latest_event(self):
        if self.events:
            return self.events[-1]
        return {"timestamp": None, "version": None}

    @property
    def first_event(self):
        """Effectively the binary version the data has been created with FIRST"""
        if self.events:
            return self.events[0]
        raise SpecterError("You should not check the first_event before you've set it!")

    def create_new_event(self, version):
        self.events.append({"timestamp": str(datetime.now()), "version": version})
        self._save()

    def create_new_execution_log(self, migration_no):
        self.migration_executions.append(
            {
                "timestamp": str(datetime.now()),
                "migration_no": migration_no,
                "status": "started",
            }
        )
        self._save()

    def set_execution_log_status(self, number, status):
        self._find_exec_log(number)["status"] = status
        self._save()

    def set_Execution_log_error_msg(self, number, msg):
        self._find_exec_log(number)["error_msg"] = msg
        self._save()

    def _find_exec_log(self, number):
        for migration in self.migration_executions:
            if migration["migration_no"] == number:
                return migration
        raise SpecterError(f"Can't find migration_execution with number {number}")

    @property
    def migration_executions(self):
        return self.data["migration_executions"]

    def has_migration_executed(self, migration_no):
        executed_list = [
            migration_execution["migration_no"]
            for migration_execution in self.migration_executions
        ]
        logger.debug(f"Executed migration_function numbers: {executed_list}")
        return migration_no in executed_list


class SpecterMigrator:
    """A Class managing Migrations. Not calling it managers, as this is reserved for Instances attached to the specter instance"""

    def __init__(self, data_folder):
        version = VersionChecker(specter=self)
        self.current_binary_version = version.current
        self.current_data_version = "unknown"
        self.data_folder = data_folder
        self.mig = MigDataManager(data_folder)
        if self.mig.latest_event["version"] != self.current_binary_version:
            logger.info(
                f"New version executing right now: {self.current_binary_version}"
            )
            self.mig.create_new_event(self.current_binary_version)
            self.mig._save()

    def plan_migration(self):
        """Returns a list of instances from all the migration_1234-classes which hasn't been
        executed yet (according to migration_data.json)
        """
        migration_function_list = []
        # The path where all the migrations are located:
        package_dir = str(Path(Path(__file__).resolve().parent, "migrations").resolve())
        for (_, module_name, _) in iter_modules(
            [package_dir]
        ):  # import the module and iterate through its attributes
            module = import_module(f"cryptoadvance.specter.migrations.{module_name}")
            for attribute_name in dir(module):
                attribute = getattr(module, attribute_name)
                if isclass(attribute):
                    if (
                        issubclass(attribute, SpecterMigration)
                        and not attribute.__name__ == "SpecterMigration"
                    ):
                        migration_obj = attribute(self)
                        if self.needs_execution(migration_obj):
                            logger.debug(
                                f"Adding class {attribute.__name__} to list of planned migrations"
                            )
                            migration_function_list.append(migration_obj)
        return migration_function_list

    def execute_migrations(self, migration_object_list=None):
        if migration_object_list == None:
            migration_object_list = self.plan_migration()
        for object in migration_object_list:
            exec_id = SpecterMigrator.calculate_number(object)
            try:
                logger.info(f"  --> Starting Migration {object.__class__.__name__}")
                self.mig.create_new_execution_log(exec_id)
                object.execute()
                logger.info(f"  --> Completed Migration {object.__class__.__name__}")
                self.mig.set_execution_log_status(exec_id, "completed")
            except Exception as e:
                logger.error(f"  --> Error in Migration {object.__class__.__name__}")
                logger.exception(e)
                self.mig.set_execution_log_status(exec_id, "error")
                self.mig.set_Execution_log_error_msg(exec_id, str(e))

    @classmethod
    def calculate_number(cls, migration_obj):
        """Extract the number from ojects derived from classes like SpecterMigration_0123"""
        prefix, number = migration_obj.__class__.__name__.split("_")
        assert prefix == "SpecterMigration"
        return int(number)

    def needs_execution(self, migration_obj: SpecterMigration):
        """returns true if the migrate_function hasn't been executed yet"""
        migration_no = SpecterMigrator.calculate_number(migration_obj)
        return (
            not self.mig.has_migration_executed(migration_no)
            and migration_obj.should_execute()
        )
