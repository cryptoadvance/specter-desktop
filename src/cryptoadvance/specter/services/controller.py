import logging
from functools import wraps

from flask import Blueprint
from flask import current_app as app
from flask import flash, redirect, render_template, request, url_for
from flask_babel import lazy_gettext as _
from flask_login import current_user, login_required

from ..services import ExtensionException

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
        if app.config["LOGIN_DISABLED"]:
            # No logins means no password so no user_secret is possible
            flash(
                _(
                    "Service integration requires an authentication method that includes a password"
                )
            )
            return redirect(url_for(f"settings_endpoint.auth"))
        elif not current_user.is_user_secret_decrypted:
            flash(_("Must login again to enable protected Services-related data"))
            # Force re-login; automatically redirects back to calling page
            return app.login_manager.unauthorized()
        else:
            return func(*args, **kwargs)

    return wrapper


@services_endpoint.route("/choose", methods=["GET"])
def choose():
    return render_template(
        "services/choose.jinja",
        is_login_disabled=app.config["LOGIN_DISABLED"],
        specter=app.specter,
        services=app.specter.service_manager.services_sorted,
    )


@services_endpoint.route(
    "/associate_addr/<wallet_alias>/<address>", methods=["GET", "POST"]
)
@login_required
@user_secret_decrypted_required
def associate_addr(wallet_alias, address):
    wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)

    if request.method == "POST":
        service_id = request.form["service_id"]
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
        service_cls = app.specter.service_manager.get_service(service_id)
        service_cls.reserve_address(wallet=wallet, address=address)
        return redirect(
            url_for("wallets_endpoint.addresses", wallet_alias=wallet_alias)
        )

    addr_obj = wallet.get_address_obj(address=address)

    # Inject the User's active Services
    services = []
    for service_id in current_user.services:
        try:
            services.append(app.specter.service_manager.get_service(service_id))
        except ExtensionException:
            pass

    return render_template(
        "services/associate_addr.jinja",
        specter=app.specter,
        services=services,
        wallet=wallet,
        addr_obj=addr_obj,
    )
