import logging

from flask import Blueprint, render_template, redirect, url_for, flash
from flask import current_app as app
from flask_login import current_user, login_required
from functools import wraps


logger = logging.getLogger(__name__)


# This endpoint is just there to share templates between services.
services_endpoint = Blueprint(
    "services_endpoint", __name__, template_folder="templates"
)

# All blueprint from Services are no longer loaded statically but dynamically when the service-class in initialized
# check cryptoadvance.specter.services.service_manager.Service for doing that and
# check cryptoadvance.specter.services/**/manifest for instances of Service-classes and
# check cryptoadvance.specter.services.service_manager.ServiceManager.services for initialisation of ServiceClasses


def user_secret_decrypted_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_user_secret_decrypted:
            flash(
                "Must login again to enable protected Services-related data"
            )
            return redirect(url_for(f"auth_endpoint.logout"))
        else:
            return func(*args, **kwargs)

    return wrapper



@services_endpoint.route("/choose", methods=["GET"])
@login_required
@user_secret_decrypted_required
def choose():
    return render_template(
        "services/choose.jinja",
        specter=app.specter,
        services=app.specter.service_manager.services_sorted,
    )

