""" Security Related things for the REST-API """
import logging
from functools import wraps

from cryptoadvance.specter.user import User, verify_password as user_verify_password
from flask import current_app as app
from flask import g
from flask_restful import abort

# from flask_httpauth import HTTPBasicAuth

from . import auth

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
    if user_verify_password(g.user.password, password):
        logger.info(f"Rest-Request for user {username} PASSED password-test")
        return username
    else:
        logger.info(f"Rest-Request for user {username} FAILED password-test")
        return abort(401)

    return g.user is not None and verify_password(g.user.password, password)


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
