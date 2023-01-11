import logging
import json
from flask import redirect, render_template, request, url_for, Response
from flask import current_app as app
from flask_login import login_required, current_user

from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.services.controller import user_secret_decrypted_required
from cryptoadvance.specter.user import User
from cryptoadvance.specter.wallet import Wallet
from .service import NotificationsService

logger = logging.getLogger(__name__)

notifications_endpoint = NotificationsService.blueprint


def ext() -> NotificationsService:
    """convenience for getting the extension-object"""
    return app.specter.ext["notifications"]


def specter() -> Specter:
    """convenience for getting the specter-object"""
    return app.specter


@notifications_endpoint.route("/")
@login_required
def index():
    return render_template(
        "notifications/index.jinja",
    )


@notifications_endpoint.route("/settings", methods=["GET"])
@login_required
def settings_get():
    user = app.specter.user_manager.get_user()
    return render_template(
        "notifications/settings.jinja",
        cookies=request.cookies,
        show_menu=NotificationsService.id in user.services,
    )


@notifications_endpoint.route("/settings", methods=["POST"])
@login_required
def settings_post():
    show_menu = request.form["show_menu"]
    user = app.specter.user_manager.get_user()
    if show_menu == "yes":
        user.add_service(NotificationsService.id)
    else:
        user.remove_service(NotificationsService.id)
    return redirect(
        url_for(f"{ NotificationsService.get_blueprint_name()}.settings_get")
    )


@notifications_endpoint.route("/websocket", websocket=True)
def websocket():
    logger.debug("websocket route called. This will start a new websocket connection.")
    # this function will run forever. That is ok, because a stream is expected, similar to https://maxhalford.github.io/blog/flask-sse-no-deps/
    #  flask.Response(stream(), mimetype='text/event-stream')
    if app.specter.ext["notifications"].notification_manager.websockets_server:
        app.specter.ext["notifications"].notification_manager.websockets_server.serve(
            request.environ
        )
    else:
        logger.warning(
            "/websocket route accessed, but no websockets_server is initialized."
        )
    # returning something solved some error message when the function ends: https://stackoverflow.com/questions/25034123/flask-value-error-view-function-did-not-return-a-response
    # and this mimetype does not trigger slow_request_detection_stop
    # however when connected via ssl the following error still occurs
    # ssl.SSLEOFError: EOF occurred in violation of protocol (_ssl.c:2384)
    return Response(json.dumps({}), mimetype="application/json")


@notifications_endpoint.route("/get_websockets_info/", methods=["GET"])
@login_required
def get_websockets_info():
    return json.dumps(
        {
            "user_token": app.specter.ext[
                "notifications"
            ].notification_manager.get_websocket_token(current_user.username),
        }
    )
