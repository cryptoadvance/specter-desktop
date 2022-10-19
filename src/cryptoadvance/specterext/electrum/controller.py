import logging
from flask import redirect, render_template, request, url_for, flash
from flask import current_app as app
from flask_login import login_required, current_user

from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.services.controller import user_secret_decrypted_required
from cryptoadvance.specter.user import User
from cryptoadvance.specter.wallet import Wallet
from .service import ElectrumService


logger = logging.getLogger(__name__)

electrum_endpoint = ElectrumService.blueprint


def ext() -> ElectrumService:
    """convenience for getting the extension-object"""
    return app.specter.ext["electrum"]


def specter() -> Specter:
    """convenience for getting the specter-object"""
    return app.specter


@electrum_endpoint.route("/")
@login_required
def index():
    return render_template(
        "electrum/index.jinja",
    )
