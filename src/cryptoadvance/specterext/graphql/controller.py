import logging
from flask import redirect, render_template, request, url_for, flash
from flask import current_app as app
from flask_login import login_required, current_user
from strawberry.flask.views import GraphQLView

from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.services.controller import user_secret_decrypted_required
from cryptoadvance.specter.user import User
from cryptoadvance.specter.wallet import Wallet
from .service import GraphqlService


logger = logging.getLogger(__name__)

graphql_endpoint = GraphqlService.blueprint


def ext() -> GraphqlService:
    """convenience for getting the extension-object"""
    return app.specter.ext["graphql"]


def specter() -> Specter:
    """convenience for getting the specter-object"""
    return app.specter


# This endpoint is added dynamically in service.py
# @graphql_endpoint.route("/graphql", methods=["GET", "POST"])
# @app.csrf.exempt
# def index():
#     view_func = GraphQLView.as_view("graphql_view", schema=schema2)
#     return view_func()


@graphql_endpoint.route("/")
@login_required
def index():
    return render_template(
        "graphql/index.jinja",
    )


@graphql_endpoint.route("/transactions")
@login_required
def schema():
    # The wallet currently configured for ongoing autowithdrawals

    return render_template(
        "graphql/schema.jinja",
    )


@graphql_endpoint.route("/settings", methods=["GET"])
@login_required
def settings_get():

    return render_template(
        "graphql/settings.jinja",
    )


@graphql_endpoint.route("/settings", methods=["POST"])
@login_required
def settings_post():
    show_menu = request.form["show_menu"]
    user = app.specter.user_manager.get_user()
    if show_menu == "yes":
        user.add_service(GraphqlService.id)
    else:
        user.remove_service(GraphqlService.id)
    return redirect(url_for(f"{ GraphqlService.get_blueprint_name()}.settings_get"))
