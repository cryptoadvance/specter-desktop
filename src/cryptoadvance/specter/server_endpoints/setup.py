import copy
import json
import logging
import os
import platform
import random
import shutil
import sys
import threading

from flask import Blueprint
from flask import current_app as app
from flask import render_template, request
from flask_babel import lazy_gettext as _
from flask_login import login_required

from ..helpers import alias
from ..util.bitcoind_setup_tasks import (
    setup_bitcoind_directory_thread,
    setup_bitcoind_thread,
)
from ..util.tor_setup_tasks import setup_tor_thread

logger = logging.getLogger(__name__)

rand = random.randint(0, 1e32)  # to force style refresh

# Setup endpoint blueprint
setup_endpoint = Blueprint("setup_endpoint", __name__)

######################### Setup pages #######################################
@setup_endpoint.route("/start/", methods=["GET"])
@login_required
def start():
    app.specter.setup_status["stage"] = "start"
    return render_template("setup/start.jinja", specter=app.specter, rand=rand)


@setup_endpoint.route("/tor/", methods=["GET"])
@login_required
def tor():
    """wizard: Setup Tor daemon (Skip / Setup Tor)"""
    app.specter.setup_status["stage"] = "tor"
    return render_template(
        "setup/tor.jinja",
        nextURL="setup_endpoint.node_type",
        specter=app.specter,
        rand=rand,
    )


@setup_endpoint.route("/node_type/", methods=["GET"])
@login_required
def node_type():
    """wizard: Would you like to setup a new Bitcoin node or connect to an existing one?
    (Connect existing node / Setup a new node )
    """
    app.specter.setup_status["stage"] = "node_type"
    return render_template(
        "setup/node_type.jinja",
        bitcoind_installed=os.path.isfile(app.specter.bitcoind_path),
        specter=app.specter,
        rand=rand,
    )


@setup_endpoint.route("/bitcoind/", methods=["GET"])
@login_required
def bitcoind():
    """wizard: Setup Bitcoin Core (Start the Setup!)"""
    app.specter.setup_status["stage"] = "bitcoind"
    return render_template("setup/bitcoind.jinja", specter=app.specter, rand=rand)


@setup_endpoint.route(
    "/bitcoind_datadir/", defaults={"network": "main"}, methods=["GET"]
)
@setup_endpoint.route("/bitcoind_datadir/<network>", methods=["GET"])
@login_required
def bitcoind_datadir(network):
    """wizard: Configure your node (Quicksync? , Start Syncing)"""
    app.specter.setup_status["stage"] = "bitcoind_datadir"
    return render_template(
        "setup/bitcoind_datadir.jinja", network=network, specter=app.specter, rand=rand
    )


@setup_endpoint.route("/end/", methods=["GET"])
@login_required
def end():
    """wizard: Setup competed Successfully (Done)"""
    app.specter.setup_status["stage"] = "start"
    return render_template("setup/end.jinja", specter=app.specter, rand=rand)


@setup_endpoint.route("/tor_setup/", methods=["GET"])
@login_required
def tor_from_settings():
    """wizard: Setup Tor daemon (Setup Tor)"""
    return render_template(
        "setup/tor.jinja",
        nextURL="settings_endpoint.tor",
        specter=app.specter,
        rand=rand,
    )


######################### Background tasks #######################################
@setup_endpoint.route("/setup_tor", methods=["POST"])
@login_required
def setup_tor():
    if (
        not os.path.isfile(app.specter.torbrowser_path)
        and app.specter.setup_status["torbrowser"]["stage_progress"] == -1
    ):
        # There is no Tor Browser binary for Raspberry Pi 4 (armv7l)
        if platform.system() == "Linux" and "armv" in platform.machine():
            return {
                "error": _(
                    "Linux ARM devices (e.g. Raspberry Pi) must manually install Tor"
                )
            }
        if not (getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")):
            return {
                "error": _(
                    "Sorry, Internal Tor Setup is not possible with Pip-installations."
                )
            }
        t = threading.Thread(target=setup_tor_thread, args=(app.specter,))
        t.start()
    elif os.path.isfile(app.specter.torbrowser_path):
        return {"error": _("Tor is already installed")}
    elif app.specter.setup_status["torbrowser"]["stage_progress"] != -1:
        return {"error": _("Tor installation is still in progress")}
    return {"success": _("Starting Tor setup!")}


@setup_endpoint.route("/setup_bitcoind", methods=["POST"])
@login_required
def setup_bitcoind():
    if (
        not os.path.isfile(app.specter.bitcoind_path)
        and app.specter.setup_status["bitcoind"]["stage_progress"] == -1
    ):
        app.specter.update_setup_status("bitcoind", "STARTING_SETUP")
        t = threading.Thread(
            target=setup_bitcoind_thread,
            args=(app.specter, app.config["INTERNAL_BITCOIND_VERSION"]),
        )
        t.start()
    elif os.path.isfile(app.specter.bitcoind_path):
        return {"error": _("Bitcoin Core is already installed")}
    elif app.specter.setup_status["bitcoind"]["stage_progress"] != -1:
        return {"error": _("Bitcoin Core installation is still in progress")}
    return {"success": _("Starting Bitcoin Core setup!")}


@setup_endpoint.route("/setup_bitcoind_datadir", methods=["POST"])
@login_required
def setup_bitcoind_datadir():
    network = request.form.get("network", "main")
    node_name = "Specter Bitcoin" if network == "main" else f"Specter {network.title()}"
    i = 1
    while node_name in app.specter.node_manager.nodes:
        i += 1
        node_name = (
            f"Specter Bitcoin {i}"
            if network == "main"
            else f"Specter {network.title()} {i}"
        )
    node_default_datadir = os.path.join(
        app.specter.node_manager.data_folder, f"{alias(node_name)}/.bitcoin-{network}"
    )
    user_selected_datadir = request.form.get(
        "bitcoin_core_datadir", node_default_datadir
    )
    if os.path.exists(user_selected_datadir):
        if request.form["override_data_folder"] != "true":
            logger.warning(
                f"Bitcoin Core data directory at {user_selected_datadir} already exists and no orride permission was explicitly given."
            )
            return {"error": "data folder already exists"}
        logger.info(f"Deleting Bitcoin Core data directory at: {user_selected_datadir}")
        shutil.rmtree(user_selected_datadir, ignore_errors=True)
    if (
        os.path.isfile(app.specter.bitcoind_path)
        and app.specter.setup_status["bitcoind"]["stage_progress"] == -1
    ):
        node = app.specter.node_manager.add_internal_node(
            node_name,
            network=network,
            datadir=user_selected_datadir,
        )
        app.specter.update_setup_status("bitcoind", "STARTING_SETUP")
        quicksync = request.form["quicksync"] == "true"
        pruned = request.form["nodetype"] == "pruned"
        t = threading.Thread(
            target=setup_bitcoind_directory_thread,
            args=(app.specter, quicksync, pruned, node.alias),
        )
        t.start()
    elif not os.path.isfile(app.specter.bitcoind_path):
        return {"error": _("Bitcoin Core in not installed but required for this step")}
    elif app.specter.setup_status["bitcoind"]["stage_progress"] != -1:
        return {"error": _("Bitcoin Core installation is still in progress")}
    return {"success": _("Starting Bitcoin Core setup!")}


######################### Setup status (open endpoint) #######################################
@setup_endpoint.route("/get_software_setup_status/<software>")
@login_required
@app.csrf.exempt
def get_software_setup_status(software):
    return app.specter.get_setup_status(software)
