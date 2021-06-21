""" API Backend - Base Resource Models """

from flask_restful import Resource, abort

from cryptoadvance.specter.api import api_rest
from cryptoadvance.specter.api.security import require_admin
from cryptoadvance.specter.api import auth


class BaseResource(Resource):
    """A baseClass for rsources which returns Method not allowed by default"""

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

    method_decorators = [auth.login_required]


class AdminResource(BaseResource):
    """A REST-resource which makes sure that the user is an admin"""

    method_decorators = [require_admin]


def rest_resource(resource_cls):
    """Decorator for adding resources to Api App"""
    api_rest.add_resource(resource_cls, *resource_cls.endpoints)
