""" Security Related things for the REST-API """
import logging, jwt
from functools import wraps

from cryptoadvance.specter.user import User, verify_password as user_verify_password
from flask import current_app as app
from flask import g
from flask_restful import abort

# from flask_httpauth import HTTPBasicAuth

from . import auth, token_auth

logger = logging.getLogger(__name__)

# auth = HTTPBasicAuth()


@auth.verify_password
def verify_password(username, password):
    """Validate user passwords and store user in the 'g' object"""
    if not username or not password:
        return abort(401)
    the_user = app.specter.user_manager.get_user_by_username(username)
    if not the_user:
        return abort(401)
    g.user = app.specter.user_manager.get_user_by_username(username)
    if user_verify_password(g.user.password_hash, password):
        logger.info(f"Rest-Request for user {username} PASSED password-test")
        return username
    else:
        logger.info(f"Rest-Request for user {username} FAILED password-test")
        return abort(401)

    return g.user is not None and verify_password(g.user.password_hash, password)


@token_auth.verify_token
def verify_token(jwt_token_id_and_jwt_token):
    """Validate JWT token and store user in the 'g' object"""
    seperated_value = jwt_token_id_and_jwt_token.split(":")
    jwt_token_id = seperated_value[0]
    jwt_token = seperated_value[1]
    if not jwt_token:
        return abort(401)
    try:
        payload = jwt.decode(jwt_token, app.config["SECRET_KEY"], algorithms=["HS256"])
        jwt_token_description = payload["description"]
        g.user = app.specter.user_manager.get_user_by_username(payload["user"])
        logger.info(
            {
                "jwt_token_id": jwt_token_id,
                "jwt_token_description": jwt_token_description,
                "user": g.user.username,
            }
        )
        if (
            jwt_token_id == g.user.get_jwt_token_id_by_jwt_token(jwt_token)
            and jwt_token_description
            == g.user.get_jwt_token_description_by_jwt_token(jwt_token)
            and g.user
        ):
            logger.info(f"Rest-Request for user {payload['user']} PASSED JWT-test")
            return True
    except jwt.ExpiredSignatureError:
        return "Signature expired. Please create a new one"
    except jwt.InvalidTokenError:
        return "Invalid token. Please create a new one"


@token_auth.verify_token
def verify_token(jwt_token_id_and_jwt_token):
    """Validate JWT token and store user in the 'g' object"""
    seperated_value = jwt_token_id_and_jwt_token.split(":")
    jwt_token_id = seperated_value[0]
    jwt_token = seperated_value[1]
    if not jwt_token:
        return abort(401)
    try:
        payload = jwt.decode(jwt_token, app.config["SECRET_KEY"], algorithms=["HS256"])
        jwt_token_description = payload["description"]
        g.user = app.specter.user_manager.get_user_by_username(payload["user"])
        logger.info(
            {
                "jwt_token_id": jwt_token_id,
                "jwt_token_description": jwt_token_description,
                "user": g.user.username,
            }
        )
        if (
            jwt_token_id == g.user.get_jwt_token_id_by_jwt_token(jwt_token)
            and jwt_token_description
            == g.user.get_jwt_token_description_by_jwt_token(jwt_token)
            and g.user
        ):
            logger.info(f"Rest-Request for user {payload['user']} PASSED JWT-test")
            return True
    except jwt.ExpiredSignatureError:
        return "Signature expired. Please create a new one"
    except jwt.InvalidTokenError:
        return "Invalid token. Please create a new one"


def require_admin(func):
    """User needs Admin-rights method decorator"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        """this needs to get implemented properly"""
        # Verify if User is Admin
        if g.user == None:
            return abort(401)
        if g.user.is_admin:
            return func(*args, **kwargs)
        else:
            return abort(401)

    return wrapper
