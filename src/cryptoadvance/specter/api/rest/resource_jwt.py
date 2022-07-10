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

def generate_token_id():
    return str(uuid.uuid4())

@rest_resource
class ResourceJWT(SecureResource):

    endpoints = ["/v1alpha/token/"]

    def get(self):
        user = auth.current_user()
        user_details = app.specter.user_manager.get_user(user)
        tokens = user_details.tokens
        return_dict = {
            "tokens": tokens,
        }
        return_dict["tokens"]=user_details.get_all_tokens()
        tokens = return_dict["tokens"]
        if len(tokens) == 0:
            return {"message": "Token does not exist"}, 404
        return {"message": "Tokens exists", "tokens": tokens}, 200

    def post(self):
        user = auth.current_user()
        user_details = app.specter.user_manager.get_user(user)
        jwt_token = user_details.jwt_token
        jwt_token_id = user_details.jwt_token_id
        return_dict = {
            "username": user_details.username,
            "id": user_details.id,
            "jwt_token_id": jwt_token_id,
            "jwt_token": jwt_token,
        }
        return_dict["jwt_token_id"] = generate_token_id()
        return_dict["jwt_token"] = generate_jwt(user_details)
        jwt_token_id = return_dict["jwt_token_id"]
        jwt_token = return_dict["jwt_token"]
        user_details.save_jwt_token(jwt_token_id, jwt_token)
        user_details.append_token(jwt_token_id, jwt_token)
        return {
                "message": "Token generated",
                "username": user_details.username,
                "created_jwt_token_id": jwt_token_id,
                "created_jwt_token": jwt_token,
            }, 201

@rest_resource
class ResourceJWTById(SecureResource):

    endpoints = ["/v1alpha/token/<jwt_token_id>/"]

    def get(self, jwt_token_id):
        user = auth.current_user()
        user_details = app.specter.user_manager.get_user(user)
        tokens = user_details.tokens
        return_dict = {
            "tokens": tokens,
        }
        return_dict["tokens"]=user_details.get_all_tokens()
        tokens = return_dict["tokens"]
        if tokens[jwt_token_id] is None:
            return {"message": "Token does not exist"}, 404
        return {"message": "Tokens exists", "jwt_token": tokens[jwt_token_id]}, 200

    def delete(self, jwt_token_id):
        user = auth.current_user()
        user_details = app.specter.user_manager.get_user(user)
        tokens = user_details.tokens
        if tokens[jwt_token_id] is None:
            return {"message": "Token does not exist"}, 404
        user_details.delete_jwt_token(jwt_token_id)
        return {"message": "Token deleted"}, 200
