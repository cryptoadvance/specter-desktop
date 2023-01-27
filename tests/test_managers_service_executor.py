import pytest
from cryptoadvance.specter.managers.service_manager.callback_executor import (
    CallbackExecutor,
)

from cryptoadvance.specter.managers.service_manager.callback_executor import (
    topological_sort,
    set_dependency_level_recursive,
)
from cryptoadvance.specter.services.callbacks import *

# Testclasses
class A:
    id = "A"
    depends = []

    def callback_adjust_view_model(model):
        return "Hello"


class B:
    id = "B"
    pass


class C:
    id = "C"
    depends = [A]

    def callback_adjust_view_model(model):
        return model + " World"


class D:
    id = "D"
    depends = [C, B]


class E:
    id = "E"
    pass


class F:
    id = "F"
    depends = [A, D]


exts = [F, E, D, C, B, A]


def test_topological_sort():

    ext_sorted = topological_sort([F, E, D, C, B, A])
    assert ext_sorted == [A, C, B, D, F, E]


def test_set_dependency_level_recursive():
    for ext in exts:
        ext.dependency_level = 0

    set_dependency_level_recursive(C)
    assert A.dependency_level == 1
    set_dependency_level_recursive(D)
    assert C.dependency_level == 1
    assert B.dependency_level == 1
    assert A.dependency_level == 2
    set_dependency_level_recursive(F)
    assert C.dependency_level == 2
    assert B.dependency_level == 2
    assert A.dependency_level == 3
    assert D.dependency_level == 1
    # Doing it again does not change the numbers
    set_dependency_level_recursive(F)
    assert C.dependency_level == 2
    assert B.dependency_level == 2
    assert A.dependency_level == 3
    assert D.dependency_level == 1


def test_CallbackExecutor_services_sorted():
    A.sort_priority = 2
    B.sort_priority = 1
    E.sort_priority = 3

    service_dict = {ext.__name__: ext for ext in exts}
    print(service_dict)
    ce = CallbackExecutor(service_dict)
    assert len(ce.services_sorted) == 6
    for ext in ce.services_sorted:
        print(
            f"{ext.__name__}    {ext.dependency_level}    {getattr(ext, 'sort_priority',9999)}"
        )
    assert ce.services_sorted == [A, B, C, D, E, F]

    A.depends.append(F)  # cyclic dependency

    with pytest.raises(ValueError):
        ext_sorted = topological_sort([F, E, D, C, B, A])

    del A.depends


def test_CallbackExecutor_all_callbacks():
    service_dict = {ext.__name__: ext for ext in exts}
    print(service_dict)
    ce = CallbackExecutor(service_dict)
    assert len(ce.all_callbacks) == 8


def test_CallbackExecutor_execute():
    service_dict = {ext.__name__: ext for ext in exts}
    print(service_dict)
    ce = CallbackExecutor(service_dict)
    rv = ce.execute_ext_callbacks(flask_before_request, "bumm", ["diedel", "bummm"])
    assert rv == {}
    assert ce.execute_ext_callbacks(adjust_view_model, "") == ("Hello World",)
