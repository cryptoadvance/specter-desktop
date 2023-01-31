import pytest
import logging
from cryptoadvance.specter.managers.service_manager.callback_executor import (
    CallbackExecutor,
)

from cryptoadvance.specter.managers.service_manager.callback_executor import (
    topological_sort,
    set_dependency_level_recursive,
)
from cryptoadvance.specter.services.callbacks import (
    flask_before_request,
    adjust_view_model,
    Callback,
)
from cryptoadvance.specter.specter_error import SpecterInternalException

logger = logging.getLogger(__name__)

# Testclasses
class A:
    id = "A"
    depends = []

    def callback_adjust_view_model(self, model):
        logger.info(
            f"A.callback_adjust_view_model has been called with model='{model}'!"
        )
        return "Hello"


class B:
    id = "B"
    pass


class C:
    id = "C"
    depends = [A]

    def callback_adjust_view_model(self, model):
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


@pytest.fixture
def exts():
    return [F(), E(), D(), C(), B(), A()]


@pytest.fixture
def callback_executor(exts):
    service_dict = {ext.__class__.__name__: ext for ext in exts}
    print(service_dict)
    ce = CallbackExecutor(service_dict)
    return ce


def test_check_callback(callback_executor: CallbackExecutor):
    ce = callback_executor
    with pytest.raises(SpecterInternalException):
        ce.check_callback("muh")
    ce.check_callback(flask_before_request)
    ce.check_callback(adjust_view_model)


def test_topological_sort(exts):

    ext_sorted = topological_sort(exts)
    ext_classes = [ext.__class__ for ext in ext_sorted]
    assert ext_classes == [A, C, B, D, F, E]


def test_set_dependency_level_recursive(exts):
    for ext in exts:
        ext.__class__.dependency_level = 0

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


def test_CallbackExecutor_services_sorted(exts):
    A.sort_priority = 2
    B.sort_priority = 1
    E.sort_priority = 3

    service_dict = {ext.__class__.__name__: ext for ext in exts}
    print(service_dict)
    ce = CallbackExecutor(service_dict)
    assert len(ce.services_sorted) == 6
    for ext in ce.services_sorted:
        print(
            f"{ext.__class__.__name__}    {ext.__class__.dependency_level}    {getattr(ext, 'sort_priority',9999)}"
        )
    assert [ext.__class__ for ext in ce.services_sorted] == [A, B, C, D, E, F]


def test_CallbackExecutor_execute(caplog, callback_executor):
    caplog.set_level(logging.DEBUG)
    ce = callback_executor
    rv = ce.execute_ext_callbacks(flask_before_request, "bumm", ["diedel", "bummm"])
    assert rv == {}
    assert ce.execute_ext_callbacks(adjust_view_model, "") == "Hello World"


def test_topological_sort_cyclic_dependencies():

    A.depends.append(F)  # cyclic dependency

    with pytest.raises(ValueError):
        ext_sorted = topological_sort([F(), E(), D(), C(), B(), A()])

    del A.depends
