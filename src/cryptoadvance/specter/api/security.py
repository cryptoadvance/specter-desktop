""" Security Related things """
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

    logger.info(f"username: {username} ")
    logger.info(f"password: {password} ")
    g.user = app.specter.user_manager.get_user_by_username(username)
    logger.info(f"verify password for user: {g.user}")
    if user_verify_password(g.user.password, password):
        return username
    else:
        return False

    return g.user is not None and verify_password(g.user.password, password)


def require_admin(func):
    """ User needs Admin-rights method decorator """

    @wraps(func)
    def wrapper(*args, **kwargs):
        """ this needs to get implemented properly """
        # Verify if User is Admin
        app.logger.debug("User is :" + str(g.user))
        if g.user == None:
            return abort(401)
        if g.user.is_admin:
            return func(*args, **kwargs)
        else:
            return abort(401)

    return wrapper
