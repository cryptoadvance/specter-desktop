""" Security Related things for the REST-API """
import logging, jwt
from functools import wraps

from cryptoadvance.specter.user import User, verify_password as user_verify_password
from flask import current_app as app
from flask import g
from flask_restful import abort
from . import auth, token_auth
from ..user import *
from . import auth
from flask import current_app as app

logger = logging.getLogger(__name__)


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
def verify_token(jwt_token):
    """Validate JWT token and store user in the 'g' object"""
    if not jwt_token:
        return abort(401)
    try:
        payload = jwt.decode(jwt_token, app.config["SECRET_KEY"], algorithms=["HS256"])
        username = payload["username"]
        the_user = app.specter.user_manager.get_user_by_username(username)
        if not the_user:
            return abort(401)
        g.user = app.specter.user_manager.get_user_by_username(username)
        logger.info({"payload": payload})
        logger.info(f"Rest-Request for user {username} PASSED JWT-test")
        return username
    except jwt.ExpiredSignatureError:
        logger.info(f"Token expired. Please create a new one")
        return abort(401)
    except jwt.InvalidTokenError:
        logger.info(f"Invalid token. Please create a new one")
        return abort(401)


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
