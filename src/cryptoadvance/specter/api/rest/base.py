""" API Backend - Base Resource Models """

from functools import wraps
import logging
import re
from flask_restful import Resource, abort

from cryptoadvance.specter.api import api_rest
from cryptoadvance.specter.api.security import require_admin
from cryptoadvance.specter.api import auth
from cryptoadvance.specter.specter_error import SpecterError

logger = logging.getLogger(__name__)


def error_handling(func):
    """User needs Admin-rights method decorator"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        """wrapping the whole error-handling around methods"""
        try:
            return func(*args, **kwargs)
        except SpecterError as se:
            logger.error(se)
            # Not that elegant as this function is accumulating all the error-handling for different
            # endpoints. On the other hand, this is probabyl more tied to different SpecterErrors
            # rather than the implementation of a rest-endpoint.
            match = re.match("Wallet (.+) does not exist!", str(se))
            if match:
                return abort(403, message=f"Wallet {match.group(1)} does not exist")
            if str(se).endswith(
                "does not have sufficient funds to make the transaction."
            ):
                return abort(
                    412,
                    message=f"Wallet does not have sufficient funds to make the transaction.",
                )
            return abort(500)
        except Exception as e:
            logger.error("Unexpected Exception in Rest-Request:")
            logger.exception(e)
            return abort(
                500,
                message="Can't tell you the reason of the issue. Please check the logs",
            )

    return wrapper


class BaseResource(Resource):
    """A baseClass for rsources which returns Method not allowed by default"""

    method_decorators = [error_handling]

    def get(self, *args, **kwargs):
        abort(405)

    def post(self, *args, **kwargs):
        abort(405)

    def put(self, *args, **kwargs):
        abort(405)

    def patch(self, *args, **kwargs):
        abort(405)

    def delete(self, *args, **kwargs):
        abort(405)


class SecureResource(BaseResource):
    """A REST-resource which makes sure that the user is Authenticated"""

    method_decorators = [error_handling, auth.login_required]


class AdminResource(BaseResource):
    """A REST-resource which makes sure that the user is an admin"""

    method_decorators = [error_handling, require_admin, auth.login_required]


def rest_resource(resource_cls):
    """Decorator for adding resources to Api App"""
    api_rest.add_resource(resource_cls, *resource_cls.endpoints)
