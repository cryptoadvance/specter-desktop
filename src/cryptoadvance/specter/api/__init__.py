""" API Blueprint Application """

import os
from flask import Flask, Blueprint, session
from flask_restful import Api
from flask_httpauth import HTTPBasicAuth

api_bp = Blueprint("api_bp", __name__, template_folder="templates", url_prefix="/api")

api_rest = Api(api_bp)

auth = HTTPBasicAuth()

from . import views
from .rest import livereadyprobes
from .rest import api
