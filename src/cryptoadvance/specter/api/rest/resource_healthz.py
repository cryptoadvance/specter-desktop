"""
liveness and readiness probes are a semi-standard way of health-checking.
See e.g. here:
https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
"""
import json
import logging
from os import abort

from cryptoadvance.specter.api.rest.base import BaseResource, rest_resource
from flask import current_app as app

logger = logging.getLogger(__name__)


@rest_resource
class ResourceLiveness(BaseResource):
    """/api/healthz/liveness
    Whether the app is up and running although it might not have connection to DB/nodes etc.
    """

    endpoints = ["/healthz/liveness"]

    def get(self):
        return {"message": "i am alive"}


@rest_resource
class ResourceReadyness(BaseResource):
    """/api/healthz/readyness
    Whether the app is up and running AND ALL its dependent services (in our case nodes) are properly functioning as well.
    """

    endpoints = ["/healthz/readyness"]

    def get(self):
        try:
            # Not sure whether that's enough. Probably improvable:
            app.specter.check()
        except Exception as e:
            abort(500, message="Readyness probe failed")
        return {"message": "i am ready"}
