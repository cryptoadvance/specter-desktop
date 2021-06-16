"""
REST API Resource Routing

http://flask-restful.readthedocs.io/en/latest/
"""
import logging
import time
from flask import current_app as app
from cryptoadvance.specter.api.rest.base import BaseResource, rest_resource


logger = logging.getLogger(__name__)


@rest_resource
class ResourceLiveness(BaseResource):
    """/api/healthz/liveness"""

    endpoints = ["/healthz/liveness"]

    def get(self):
        return "i am alive"


@rest_resource
class ResourceReadyness(BaseResource):
    """/api/healthz/readyness"""

    endpoints = ["/healthz/readyness"]

    def get(self):
        try:
            app.specter.check()
        except Exception as e:
            logger.error(f"Readyness probe failed:{e}")
            # Would be cool to have a timeout check here to act more sophisticated e.g. warn in the logs
            # or something but looks complicated:
            # https://sqlalchemy.narkive.com/U4m4aqf9/set-a-query-timeout-on-a-per-query-basis
        return "i am ready"
