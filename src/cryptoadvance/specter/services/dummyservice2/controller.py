import logging

from .service import DummyService2


"""
    Empty placeholder just so the dummyservice/static folder can be wired up to retrieve its icon.
"""

logger = logging.getLogger(__name__)

dummyservice2_endpoint = DummyService2.blueprint

