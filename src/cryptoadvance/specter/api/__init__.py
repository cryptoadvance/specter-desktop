""" API Blueprint Application """

import os
from flask import Flask, Blueprint, session
from flask_restful import Api
from flask_httpauth import HTTPBasicAuth
from flask import current_app as app

api_bp = Blueprint("api_bp", __name__, template_folder="templates", url_prefix="/api")

api_rest = Api(api_bp, decorators=[app.csrf.exempt])

auth = HTTPBasicAuth()

from . import views
from .rest import api
