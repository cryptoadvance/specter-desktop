from ...user import User
import jwt
from flask import current_app as app
import uuid
import datetime
import logging
from .base import *

logger = logging.getLogger(__name__)


def generate_jwt(user: User):
    token = jwt.encode(
        {
            "id": user.id,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(seconds=20),
        },
        app.config["SECRET_KEY"],
        algorithm="HS256",
    )
    user.save_info()
    return token


@rest_resource
class GetToken(BaseResource):
    """/api/v1alpha/token"""

    endpoints = ["/v1alpha/token"]

    def get(self):
        user = auth.current_user()
        jwt_secret = generate_jwt(user)
        return {"token": jwt_secret}
