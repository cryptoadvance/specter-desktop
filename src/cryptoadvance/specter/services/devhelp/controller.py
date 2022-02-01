import logging
from flask import Flask, Response, redirect, render_template, request, url_for, flash
from flask_login import login_required

from ..controller import user_secret_decrypted_required
from .service import DevhelpService


"""
    Empty placeholder just so the dummyservice/static folder can be wired up to retrieve its img
"""

logger = logging.getLogger(__name__)

devhelp_endpoint = DevhelpService.blueprint


@devhelp_endpoint.route("/")
@login_required
@user_secret_decrypted_required
def index():
    return render_template(
        "devhelp/index.jinja",
    )

@devhelp_endpoint.route("/html/<html_component>")
@login_required
@user_secret_decrypted_required
def html_component(html_component):
    return render_template(
        f"devhelp/html/{html_component}",
    )
