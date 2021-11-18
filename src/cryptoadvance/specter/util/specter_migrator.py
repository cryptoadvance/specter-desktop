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

from ..managers.genericdata_manager import GenericDataManager
from ..specter_error import SpecterError
from .version import VersionChecker, compare

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
        """You can override this to prevent execution for specific cases
        The default is that the version where this migration has been implemented needs to be
        bigger than the version the user executed specter for the first time
        """
        return self.__class__.should_execute_cls(
            self.specter_migrator.mig.first_event["version"], self.__class__.version
        )

    @classmethod
    def should_execute_cls(cls, version_first_started, migration_version):
        """This is the default method and separated out for better testability"""
        # We need to compare the version we have been started first with the version this migration
        # is suppose to migrate.
        # If version_first_started > self.version we don't need to execute this migration and will return False
        try:
            compare_version = compare(version_first_started, migration_version)
        except SpecterError:
            # if in doubt because versions are unparsable, execute!
            return True
        if compare_version == 1:
            return True
        elif compare_version == -1:
            return False
        elif compare_version == 0:
            return False

    @property
    def description(self) -> str:
        """Should return a (multiline) description of the migration which will get log.info() at execution-time"""
        # return """A dummy migration:
        #     * "foo" changed from str to list[str] to support multiple foos (PR #1234)
        #     * "bar" renamed to "thing" (PR #1235)
        #     * "blah" removed; no longer needed because... (PR #1236)
        # """
        raise Exception(
            "Must write a description of the changes the migration implements."
        )

    def execute(self):
        logger.error(
            f"This migration seem to have forgotten orverriding the execute-method!"
        )


class SpecterMigrator:
    """A Class managing Migrations. Not calling it managers, as this is reserved for Instances attached to the specter instance"""

    def __init__(self, data_folder):
        version = VersionChecker(specter=self)
        self.current_binary_version = version._get_current_version()
        self.current_data_version = "unknown"
        self.data_folder = data_folder
        self.mig = MigDataManager(data_folder)
        if self.mig.latest_event["version"] != self.current_binary_version:
            logger.info(
                f"A new version has been started compared to last time: {self.current_binary_version}"
            )
            self.mig.create_new_event(self.current_binary_version)
        logger.debug(f"Initiated SpecterMigrator({self.mig})")

    def plan_migration(self):
        """Returns a list of instances from all the migration_1234-classes which hasn't been
        executed yet (according to migration_data.json)
        """
        migration_objects_list = []
        # The path where all the migrations are located:
        package_dir = str(Path(Path(__file__).resolve().parent, "migrations").resolve())
        for migration_class in self.get_migration_classes():
            migration_obj = migration_class(self)

            migration_id = SpecterMigrator.calculate_id(migration_obj)
            if not self.mig.has_migration_executed(migration_id):
                if migration_obj.should_execute():
                    logger.debug(
                        f"Adding class {migration_class.__name__} to list of planned migrations"
                    )
                    migration_objects_list.append(migration_obj)
                else:
                    logger.debug(
                        f"Skipping class {migration_class.__name__} because of 'should_execute' False"
                    )
        return migration_objects_list

    def execute_migrations(self, migration_object_list=None):
        if migration_object_list == None:
            migration_object_list = self.plan_migration()
        if not migration_object_list:
            logger.info("No Migrations to execute!")
        else:
            for object in migration_object_list:
                exec_id = SpecterMigrator.calculate_id(object)
                try:
                    logger.info(f"  --> Starting Migration {object.__class__.__name__}")
                    logger.info(object.description)
                    self.mig.create_new_exec_log(exec_id, self.current_binary_version)
                    object.execute()
                    logger.info(
                        f"  --> Completed Migration {object.__class__.__name__}"
                    )
                    self.mig.set_execution_log_status(exec_id, "completed")
                except Exception as e:
                    logger.error(
                        f"  --> Error in Migration {object.__class__.__name__}"
                    )
                    logger.exception(e)
                    self.mig.set_execution_log_status(exec_id, "error")
                    self.mig.set_Execution_log_error_msg(exec_id, str(e))

    @classmethod
    def calculate_id(cls, migration_obj):
        """Extract the id from ojects derived from classes like SpecterMigration_0123"""
        prefix, id = migration_obj.__class__.__name__.split("_")
        assert prefix == "SpecterMigration"
        return int(id)

    @classmethod
    def get_migration_classes(cls):
        """Returns all subclasses of class SpecterMigration"""
        class_list = []
        # The path where all the migrations are located:
        package_dir = str(Path(Path(__file__).resolve().parent, "migrations").resolve())
        for (_, module_name, _) in iter_modules(
            [package_dir]
        ):  # import the module and iterate through its attributes
            module = import_module(
                f"cryptoadvance.specter.util.migrations.{module_name}"
            )
            logger.info("Collecting possible migrations ...")
            for attribute_name in dir(module):
                attribute = getattr(module, attribute_name)
                if isclass(attribute):
                    if (
                        issubclass(attribute, SpecterMigration)
                        and not attribute.__name__ == "SpecterMigration"
                    ):
                        class_list.append(attribute)
        return class_list


class MigDataManager(GenericDataManager):
    """A class handling the data for the SpecterMigrator in migration_data.json with some convenience-methods"""

    @classmethod
    def initial_data(cls):
        return {
            "events": [],  # contains elements like {"timestamp": someTimestamp, "version": "v1.5.0"}
            "migration_executions": [],  # contains elements like {"timestamp": someTimestamp, "migration_id": 0}
        }

    name_of_json_file = "migration_data.json"

    def __init__(self, data_folder):
        # creating folders if they don't exist
        # Usually Specter is doing that but in the case of tests, we're instantiated before Specter
        if not os.path.isdir(data_folder):
            os.makedirs(data_folder)
        super().__init__(data_folder)
        logger.info(f"Initiated {self}")

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
        timestamp = datetime.now()
        logger.debug(f"Creating new event with version {version} at {timestamp}")
        self.events.append({"timestamp": str(timestamp), "version": version})
        self._save()

    def create_new_exec_log(self, migration_id, executing_version):
        timestamp = datetime.now()
        logger.debug(
            f"Creating new Execution log with id {migration_id} at {timestamp}"
        )
        self.migration_executions.append(
            {
                "timestamp": str(timestamp),
                "migration_id": migration_id,
                "status": "started",
                "executing_version": executing_version,
            }
        )
        self._save()

    def set_execution_log_status(self, id, status):
        logger.debug(f"Setting execution log status of {id} to {status}")
        self._find_exec_log(id)["status"] = status
        self._save()

    def set_Execution_log_error_msg(self, id, msg):
        logger.debug(f"Setting execution log error_message of {id} to {msg}")
        self._find_exec_log(id)["error_msg"] = msg
        self._save()

    def _find_exec_log(self, id):
        for migration in self.migration_executions:
            if migration.get("migration_id") == id:
                return migration
        raise SpecterError(f"Can't find migration_execution with id {id}")

    @property
    def migration_executions(self):
        return self.data["migration_executions"]

    def has_migration_executed(self, migration_id):
        executed_list = [
            migration_execution.get("migration_id")
            for migration_execution in self.migration_executions
        ]
        logger.debug(f"Executed migration_classes ids: {executed_list}")
        return migration_id in executed_list

    def __repr__(self):
        return f"MigDataManager({self.data_file} events:{len(self.events)} execs:{len(self.migration_executions)} )"
