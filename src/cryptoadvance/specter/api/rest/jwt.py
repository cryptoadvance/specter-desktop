import jwt
from flask import current_app as app
from cryptoadvance.specter.api.rest.base import (
    BaseResource,
    rest_resource,
    AdminResource,
)
import uuid
import datetime
import logging
from ...user import *
from .base import *

from .. import auth

logger = logging.getLogger(__name__)


def generate_jwt(user):
    payload = {
        "user": user.username,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=1),
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")


@rest_resource
class TokenResource(AdminResource):
    endpoints = ["/v1alpha/token/"]

    def get(self):
        user = auth.current_user()
        user_details = app.specter.user_manager.get_user(user)
        jwt_token = user_details.jwt_token
        return_dict = {
            "username": user_details.username,
            "id": user_details.id,
            "jwt_token": jwt_token,
        }
        if jwt_token is None:
            return_dict["jwt_token"] = generate_jwt(user_details)
            jwt_token = return_dict["jwt_token"]
            user_details.save_jwt_token(jwt_token)
            return {
                "message": "Token generated",
                "username": user_details.username,
                "jwt_token": jwt_token,
            }
        return {"message": "Token already exists", "jwt_token": jwt_token}

    def delete(self):
        user = auth.current_user()
        user_details = app.specter.user_manager.get_user(user)
        jwt_token = user_details.jwt_token
        if jwt_token is None:
            return {"message": "Token does not exist"}
        user_details.delete_jwt_token()
        return {"message": "Token deleted"}
