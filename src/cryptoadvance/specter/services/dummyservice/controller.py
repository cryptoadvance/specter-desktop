import logging

from .service import DummyService


"""
    Empty placeholder just so the dummyservice/static folder can be wired up to retrieve its icon.
"""

logger = logging.getLogger(__name__)

dummyservice_endpoint = DummyService.blueprint

