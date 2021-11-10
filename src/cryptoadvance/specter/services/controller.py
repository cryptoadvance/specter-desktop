import random, traceback, socket
from datetime import datetime
from binascii import unhexlify
from flask import make_response

from flask import (
    render_template,
    Blueprint,
    request,
    redirect,
    url_for,
    flash,
)
from flask_login import login_required, current_user

from pathlib import Path

from dotenv import load_dotenv

from flask import current_app as app
from ..server_endpoints.filters import filters_bp

# app.register_blueprint(filters_bp)


# This endpoint is just there to share templates between services. No endpoints so far
services_endpoint = Blueprint(
    "services_endpoint", __name__, template_folder="templates"
)
app.register_blueprint(services_endpoint)

# All blueprint from Services are no longer loaded statically but dynamically when the service-class in initialized
# check cryptoadvance.specter.services.service_manager.Service for doing that and
# check cryptoadvance.specter.services/**/manifest for instances of Service-classes and
# check cryptoadvance.specter.services.service_manager.ServiceManager.services for initialisation of ServiceClasses
