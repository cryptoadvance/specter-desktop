"""
simple hello world rest which has a weird idea about auth
"""
import logging

import cryptoadvance.specter as specter
from cryptoadvance.specter.api.rest.base import (
    AdminResource,
    BaseResource,
    SecureResource,
    rest_resource,
)
from cryptoadvance.specter.api.security import require_admin, verify_password
from flask_restful import reqparse

from .. import auth

logger = logging.getLogger(__name__)


parser = reqparse.RequestParser()
parser.add_argument("greeting", help="This field cannot be blank", required=True)


@rest_resource
class ResourceHelloUser(SecureResource):
    """ /api/v1alpha/hello """

    endpoints = ["/v1alpha/hello"]

    def get(self):
        """ say hello to the User """
        return {"hello": auth.current_user()}

    def post(self):
        """ greet the user """
        args = parser.parse_args()
        return {"greeting": args["greeting"]}


@rest_resource
class ResourceHelloAdmin(SecureResource):
    """ /api/v1alpha/hello """

    endpoints = ["/v1alpha/helloadmin"]

    @require_admin
    def get(self):
        """ say hello to the User """
        return {"hello": auth.current_user()}
