import logging
from flask import redirect, render_template, request, url_for, flash
from flask import current_app as app
from flask_login import login_required, current_user

from cryptoadvance.specter.services.controller import user_secret_decrypted_required
from cryptoadvance.specter.user import User
from cryptoadvance.specter.wallet import Wallet
from cryptoadvance.specter.specter_error import SpecterError

from cryptoadvance.specterext.spectrum.spectrum_node import SpectrumNode
from .service import SpectrumService
from .controller_helpers import (
    ext,
    specter,
    evaluate_current_status,
    check_for_node_on_same_network,
)


logger = logging.getLogger(__name__)

spectrum_endpoint = SpectrumService.blueprint


@spectrum_endpoint.route("node/<node_alias>/", methods=["GET", "POST"])
@login_required
def node_settings(node_alias=None):
    if node_alias is not None and node_alias != "spectrum_node":
        raise SpecterError(f"Unknown Spectrum Node: {node_alias}")
    return redirect(url_for("spectrum_endpoint.index"))


@spectrum_endpoint.route("/", methods=["GET"])
@login_required
# index_get would be more consistent but in sidebar_services_list.jinja the url_for looks by default for all plugins for just an "index()" view function
def index():
    # Show current configuration
    if ext().id in specter().user.services:
        show_menu = "yes"
    else:
        show_menu = "no"
    electrum_options = app.config["ELECTRUM_OPTIONS"]
    elec_chosen_option = "manual"
    spectrum_node: SpectrumNode = ext().spectrum_node
    if spectrum_node is not None:
        host = spectrum_node.host
        port = spectrum_node.port
        ssl = spectrum_node.ssl
        for opt_key, elec in electrum_options.items():
            if elec["host"] == host and elec["port"] == port and elec["ssl"] == ssl:
                elec_chosen_option = opt_key
        return render_template(
            "spectrum/index.jinja",
            elec_options=electrum_options,
            elec_chosen_option=elec_chosen_option,
            host=host,
            port=port,
            ssl=ssl,
            node_is_available=ext().is_spectrum_node_available,
            show_menu=show_menu,
        )
    else:
        return render_template(
            "spectrum/index.jinja",
            elec_options=electrum_options,
            elec_chosen_option="list",
            node_is_available=ext().is_spectrum_node_available,
            show_menu=show_menu,
        )


@spectrum_endpoint.route("/", methods=["POST"])
@login_required
def index_post():
    # Node status before saving the settings
    node_is_running_before_request = ext().is_spectrum_node_running
    logger.debug(
        f"Node running before updating settings: {node_is_running_before_request}"
    )
    host_before_request = None
    if ext().is_spectrum_node_available:
        host_before_request = ext().spectrum_node.host
        logger.debug(f"The host before saving the new settings: {host_before_request}")

    action = request.form["action"]

    if action == "delete":
        ext().disable_spectrum()
        flash("Spectrum connection deleted")
        return redirect(url_for(f"{ SpectrumService.get_blueprint_name()}.index"))

    if action == "connect":
        # Gather the Electrum server settings from the form and update with them
        success = False
        host = request.form.get("host")
        try:
            port = int(request.form.get("port"))
        except ValueError:
            port = 0
        ssl = request.form.get("ssl") == "on"
        option_mode = request.form.get("option_mode")
        electrum_options = app.config["ELECTRUM_OPTIONS"]
        elec_option = request.form.get("elec_option")
        if option_mode == "list":
            host = electrum_options[elec_option]["host"]
            port = electrum_options[elec_option]["port"]
            ssl = electrum_options[elec_option]["ssl"]
        # If there is already a Spectrum node, just update with the new values (restarts Spectrum)
        if ext().is_spectrum_node_available:
            ext().update_electrum(host, port, ssl)
        # Otherwise, create the Spectrum node and then start Spectrum
        else:
            ext().enable_spectrum(host, port, ssl, activate_spectrum_node=False)
        # Make the Spectrum node the new active node and save it to disk, but only if the connection is working"""
        # BETA_VERSION: Additional check that there is no Bitcoin Core node for the same network alongside the Spectrum node
        spectrum_node = ext().spectrum_node

        if check_for_node_on_same_network(spectrum_node, specter()):
            # Delete Spectrum node again (it wasn't saved to disk yet)
            del specter().node_manager.nodes[spectrum_node.alias]
            return render_template(
                "spectrum/spectrum_setup_beta.jinja", core_node_exists=True
            )

        if ext().spectrum_node.is_running:
            logger.debug("Activating Spectrum node ...")
            ext().activate_spectrum_node()
            success = True

        # Set the menu item
        show_menu = request.form["show_menu"]
        user = specter().user_manager.get_user()
        if show_menu == "yes":
            user.add_service(ext().id)
        else:
            user.remove_service(ext().id)

        # Determine changes for better feedback message in the jinja template
        logger.debug(f"Node running after updating settings: {success}")
        host_after_request = ext().spectrum_node.host
        logger.debug(f"The host after saving the new settings: {host_after_request}")

        if (
            node_is_running_before_request == success
            and success == True
            and host_before_request == host_after_request
        ):
            # Case 1: We changed a setting that didn't impact the Spectrum node, currently only the menu item setting
            return redirect(url_for(f"{ SpectrumService.get_blueprint_name()}.index"))

        changed_host, check_port_and_ssl = evaluate_current_status(
            node_is_running_before_request,
            success,
            host_before_request,
            host_after_request,
        )

        return render_template(
            "spectrum/spectrum_setup.jinja",
            success=success,
            node_is_running_before_request=node_is_running_before_request,
            changed_host=changed_host,
            host_type=option_mode,
            check_port_and_ssl=check_port_and_ssl,
        )

    raise Exception(f"Unknown action: {action}")


@spectrum_endpoint.route("/wallets", methods=["GET"])
@login_required
def wallets_get():
    wallets = ext().spectrum_node.get_rpc().listwallets()
    wallets_dict = {}
    for wallet_name in wallets:
        rpc = ext().spectrum_node.get_rpc().wallet(wallet_name)
        wallets_dict[wallet_name] = rpc.getwalletinfo()
    return render_template(
        "spectrum/spectrum_wallets.jinja", wallets=wallets, wallets_dict=wallets_dict
    )


@spectrum_endpoint.route("/wallets", methods=["POST"])
@login_required
def wallets_post():
    wallet_name = request.form["wallet_name"]
    # Does not work yet
    # ext().spectrum_node.get_rpc().wallet()delete_wallet()
    logger.info("Would delete wallet if it would yet be possible!")
    flash("Deletion not yet implemented!")
    return redirect(url_for(f"{ SpectrumService.get_blueprint_name()}.wallets_get"))
