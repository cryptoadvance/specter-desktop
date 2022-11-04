import logging
from flask import Flask, Response, redirect, render_template, request, url_for
from flask import current_app as app
from flask_login import login_required, current_user

from cryptoadvance.specter.services.controller import user_secret_decrypted_required
from .service import DevhelpService
from cryptoadvance.specter.wallet import Wallet
from cryptoadvance.specter.util.common import robust_json_dumps

logger = logging.getLogger(__name__)

devhelp_endpoint = DevhelpService.blueprint


@devhelp_endpoint.route("/")
@login_required
def index():
    return render_template(
        "devhelp/index.jinja",
    )


@devhelp_endpoint.route("/html/<html_component>")
@login_required
def html_component(html_component):
    associated_wallet: Wallet = DevhelpService.get_associated_wallet()
    return render_template(
        f"devhelp/html/{html_component}",
        wallet=associated_wallet,
        services=app.specter.service_manager.services,
        address=associated_wallet.get_address(3) if associated_wallet else None,
    )


@devhelp_endpoint.route("/console", methods=["GET"])
@login_required
def console():
    return render_template("devhelp/dev-console.jinja")


@devhelp_endpoint.route("/settings", methods=["GET"])
@login_required
def settings_get():
    associated_wallet: Wallet = DevhelpService.get_associated_wallet()

    # Get the user's Wallet objs, sorted by Wallet.name
    wallet_names = sorted(current_user.wallet_manager.wallets.keys())
    wallets = [current_user.wallet_manager.wallets[name] for name in wallet_names]

    return render_template(
        "devhelp/settings.jinja",
        associated_wallet=associated_wallet,
        wallets=wallets,
        cookies=request.cookies,
    )


@devhelp_endpoint.route("/settings", methods=["POST"])
@login_required
def settings_post():
    show_menu = request.form["show_menu"]
    user = app.specter.user_manager.get_user()
    if show_menu == "yes":
        user.add_service(DevhelpService.id)
    else:
        user.remove_service(DevhelpService.id)
    used_wallet_alias = request.form.get("used_wallet")
    if used_wallet_alias != None:
        wallet = current_user.wallet_manager.get_by_alias(used_wallet_alias)
        DevhelpService.set_associated_wallet(wallet)
    return redirect(url_for(f"{DevhelpService.get_blueprint_name()}.settings_get"))


NEVER_CALLED_PYTHON_COMMAND = True


@devhelp_endpoint.route("/python_command", methods=["POST"])
@login_required
def python_command():
    global NEVER_CALLED_PYTHON_COMMAND
    if NEVER_CALLED_PYTHON_COMMAND:
        NEVER_CALLED_PYTHON_COMMAND = False
        return robust_json_dumps(
            "!!!DANGER!!!\n"
            "This command allows arbitrary access to Specter.\n"
            "You can irreparabily damage your specter configuration and\n"
            "all funds on !!!HOT!!! wallets can be lost!\n"
            "Please use it with extreme care!!! Run your command again to execute it.\n\n"
            "--> Never copy&paste anything you do not FULLY understand. <--"
        )
    if current_user != "admin" or not app.specter.user_manager.user.is_admin:
        return robust_json_dumps(f"Access forbidden for user '{current_user}'!")
    if not app.config["DEVELOPER_JAVASCRIPT_PYTHON_CONSOLE"]:
        return robust_json_dumps(
            "DEVELOPER_JAVASCRIPT_PYTHON_CONSOLE disabled in Specter configuration.  "
            "This is an advanced option and should be used with great care!!!"
        )
    if request.method != "POST":
        return robust_json_dumps("Not a 'POST' command.")

    # The following commented lines are a further restriction of this endpoint, by limiting it only to regtest and testnet
    # uncomment these lines to enable the restriction
    # ----------------------------------------------
    # allowed_chains = ['regtest', 'testnet', 'liquidtestnet', 'liquidregtest']
    # if app.specter.chain not in allowed_chains:
    #     return robust_json_dumps(f"This command is only allowed for {allowed_chains}. "
    #                              "The current chain is {app.specter.chain}")
    # ----------------------------------------------

    command = request.form["command"]
    result = DevhelpService.console.exec_command(command)
    try:
        return robust_json_dumps(result)
    except:
        return robust_json_dumps(str(result))
