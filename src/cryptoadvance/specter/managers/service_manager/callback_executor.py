import logging
from typing import Dict, List

from cryptoadvance.specter.util.reflection import (
    get_template_static_folder,
    get_subclasses,
)
from flask import current_app as app
from flask import url_for
from flask.blueprints import Blueprint

from cryptoadvance.specter.util.specter_migrator import SpecterMigration

from ...services.service import Service
from ...services.callbacks import *
from ...services.callbacks import Callback
from ...specter_error import SpecterInternalException


logger = logging.getLogger(__name__)


class CallbackExecutor:
    """encapsulating the complexities of the extension callbacks"""

    def __init__(self, extensions):
        self._extensions = extensions

    def execute_ext_callbacks(self, callback, *args, **kwargs):
        """will execute the callback function for each extension which has defined that method
        the callback_id needs to be passed and specify why the callback has been called.
        It needs to be one of the constants defined in cryptoadvance.specter.services.callbacks
        """
        self.check_callback(callback)
        # No debug statement here possible as this is called for every request and would flood the logs
        # logger.debug(f"Executing callback {callback_id}")
        return_values = {}
        for ext in self.services_sorted:
            if hasattr(ext, f"callback_{callback.id}"):
                # logger.debug(f"About to execute on ext {ext.id} callback_{callback.id}")
                return_values[ext.id] = getattr(ext, f"callback_{callback.id}")(
                    *args, **kwargs
                )
                # logger.debug(f"returned {return_values[ext.id]}")

                if callback.return_style == "middleware":
                    if return_values[ext.id] == None:
                        logger.error(
                            f"Extension {ext.id} did not respect middleware contract for {callback.id}. Returned None! Skipping!"
                        )
                    else:
                        args = [return_values[ext.id]]

        # Filtering out all None return values
        return_values = {k: v for k, v in return_values.items() if v is not None}
        # logger.debug(f"return_values for callback {callback.id} {return_values}")
        if callback.return_style == "collect":
            return return_values
        elif callback.return_style == "middleware":
            return args[0]
        else:
            raise SpecterInternalException(
                f""" 
                Unknown callback return_style {callback.return_style} for callback {callback}
            """
            )

    @property
    def extensions(self) -> Dict[str, Service]:
        return self._extensions or {}

    @property
    def services_sorted(self) -> List[Service]:
        """A list of sorted extensions. First sort-criteria is the dependency. Second one the sort-priority"""
        if hasattr(self, "_services_sorted"):
            return self._services_sorted
        exts_sorted = topological_sort(self.extensions.values())
        for ext in exts_sorted:
            ext.__class__.dependency_level = 0
        for ext in exts_sorted:
            set_dependency_level_recursive(ext.__class__, 0)
        exts_sorted.sort(
            key=lambda x: (-x.dependency_level, -getattr(x, "sort_priority", 0))
        )
        self._services_sorted = exts_sorted
        return self._services_sorted

    @property
    def all_callbacks(self):
        return get_subclasses(Callback)

    def check_callback(self, callback, *args, **kwargs):
        """A callback argument needs to:
        * be a class which derives from callback
        * or a instance of such a class. This might simplify the the whole extensionframework in the future
        * If a callback has the return-type "middleware", it has to have exactly one argument (otherwise the whole thing gets to complicated)
        If one of the checks fails, it'll raise an SpecterInternalException. This behaviour should be improved over time but as long as
        the number of extensions are so small, that behaviour helps to catch issues in all extensions.
        ToDo in the future: Complaining and ignoring.
        """
        if type(callback) != type:
            callback: Callback = callback.__class__
        if callback not in self.all_callbacks:
            raise SpecterInternalException(
                f"""
                Non existing callback_id: {callback} or your class does not inherit from Callback
                """
            )
        if callback.return_style == "middleware":
            if len(args) > 1:
                raise SpecterInternalException(
                    f"""
                The callback {callback} is using middleware but it's passing more than one argument: {args}."
                """
                )

            if len(kwargs.values()) > 0:
                raise SpecterInternalException(
                    f"""
                The callback {callback} is using middleware but it's using named arguments: {kwargs}.
                """
                )


def topological_sort(instances):
    """Sorts a list of instances so that non dependent ones come first"""
    class_map = {instance.__class__: instance for instance in instances}
    in_degree = {cls: 0 for cls in class_map.keys()}
    graph = {cls: set() for cls in class_map.keys()}

    for cls, instance in class_map.items():
        for dep in getattr(cls, "depends", []):
            graph[dep].add(cls)
            in_degree[cls] += 1

    no_incoming_edges = [cls for cls in class_map.keys() if in_degree[cls] == 0]
    output = []

    while no_incoming_edges:
        node = no_incoming_edges.pop()
        output.append(class_map[node])

        for child in graph[node]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                no_incoming_edges.append(child)

    if len(output) != len(class_map):
        raise ValueError("Graph contains a cycle.")

    return output


def set_dependency_level_recursive(ext, level=0):
    for dep in getattr(ext, "depends", []):
        dep.dependency_level = max(getattr(dep, "dependency_level", 0), level + 1)
        set_dependency_level_recursive(dep, level + 1)
