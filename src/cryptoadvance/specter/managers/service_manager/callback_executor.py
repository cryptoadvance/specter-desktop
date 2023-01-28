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


logger = logging.getLogger(__name__)


class CallbackExecutor:
    """encapsulating the complexities of the extension callbacks"""

    def __init__(self, services):
        self._services = services

    def execute_ext_callbacks(self, callback: Callback, *args, **kwargs):
        """will execute the callback function for each extension which has defined that method
        the callback_id needs to be passed and specify why the callback has been called.
        It needs to be one of the constants defined in cryptoadvance.specter.services.callbacks
        """
        if callback not in self.all_callbacks:
            raise Exception(f"Non existing callback_id: {callback}")
        # No debug statement here possible as this is called for every request and would flood the logs
        # logger.debug(f"Executing callback {callback_id}")
        return_values = {}
        for ext in self.services_sorted:
            if hasattr(ext, f"callback_{callback.id}"):
                return_values[ext.id] = getattr(ext, f"callback_{callback.id}")(
                    *args, **kwargs
                )
                if callback.return_style == "middleware":
                    args = (return_values[ext.id],)
        # Filtering out all None return values
        return_values = {k: v for k, v in return_values.items() if v is not None}
        # logger.debug(f"return_values for callback {callback.id} {return_values}")
        if callback.return_style == "dict":
            return return_values
        else:
            return args

    @property
    def services(self) -> Dict[str, Service]:
        return self._services or {}

    @property
    def services_sorted(self) -> List[Service]:
        """A list of sorted extensions. First sort-criteria is the dependency. Second one the sort-priority"""
        if hasattr(self, "_services_sorted"):
            return self._services_sorted
        exts_sorted = topological_sort(self.services.values())
        for ext in exts_sorted:
            ext.dependency_level = 0
        for ext in exts_sorted:
            set_dependency_level_recursive(ext, 0)
        exts_sorted.sort(
            key=lambda x: (-x.dependency_level, -getattr(x, "sort_priority", 0))
        )
        self._services_sorted = exts_sorted
        return self._services_sorted

    @property
    def all_callbacks(self):
        return get_subclasses(Callback)


def topological_sort(exts):
    """Sorts a list of extensions so that non dependent ones come first"""
    in_degree = {cls: 0 for cls in exts}
    graph = {cls: set() for cls in exts}

    for cls in exts:
        for dep in getattr(cls, "depends", []):
            graph[dep].add(cls)
            in_degree[cls] += 1

    no_incoming_edges = [cls for cls in exts if in_degree[cls] == 0]
    output = []

    while no_incoming_edges:
        node = no_incoming_edges.pop()
        output.append(node)

        for child in graph[node]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                no_incoming_edges.append(child)

    if len(output) != len(exts):
        raise ValueError("Graph contains a cycle.")

    return output


def set_dependency_level_recursive(ext, level=0):
    for dep in getattr(ext, "depends", []):
        dep.dependency_level = max(getattr(dep, "dependency_level", 0), level + 1)
        set_dependency_level_recursive(dep, level + 1)
