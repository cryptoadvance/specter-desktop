import copy, random, json, os, threading, shutil

from flask import (
    Flask,
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    flash,
)
from flask_login import login_required, current_user
from flask import current_app as app
from mnemonic import Mnemonic
from ..helpers import is_testnet, generate_mnemonic
from ..key import Key
from ..device_manager import get_device_class
from ..devices.bitcoin_core import BitcoinCore
from ..wallet_manager import purposes
from ..specter_error import handle_exception
from ..util.bitcoind_setup_tasks import (
    setup_bitcoind_thread,
    setup_bitcoind_directory_thread,
)
from ..util.tor_setup_tasks import (
    setup_tor_thread,
)

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
    return render_template("setup/node_type.jinja", specter=app.specter, rand=rand)


@setup_endpoint.route("/bitcoind/", methods=["GET"])
@login_required
def bitcoind():
    """wizard: Setup Bitcoin Core (Start the Setup!)"""
    app.specter.setup_status["stage"] = "bitcoind"
    return render_template("setup/bitcoind.jinja", specter=app.specter, rand=rand)


@setup_endpoint.route("/bitcoind_datadir/", methods=["GET"])
@login_required
def bitcoind_datadir():
    """wizard: Configure your node (Quicksync? , Start Syncing)"""
    app.specter.setup_status["stage"] = "bitcoind_datadir"
    return render_template(
        "setup/bitcoind_datadir.jinja", specter=app.specter, rand=rand
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
        t = threading.Thread(target=setup_tor_thread, args=(app.specter,))
        t.start()
    elif os.path.isfile(app.specter.torbrowser_path):
        return {"error": "Tor is already installed"}
    elif app.specter.setup_status["torbrowser"]["stage_progress"] != -1:
        return {"error": "Tor installation is still under progress"}
    return {"success": "Starting Tor setup!"}


@setup_endpoint.route("/setup_bitcoind", methods=["POST"])
@login_required
def setup_bitcoind():
    app.specter.config["internal_node"]["datadir"] = request.form.get(
        "bitcoin_core_datadir", app.specter.config["internal_node"]["datadir"]
    )
    app.specter._save()
    if os.path.exists(app.specter.config["internal_node"]["datadir"]):
        if request.form["override_data_folder"] != "true":
            return {"error": "data folder already exists"}
        shutil.rmtree(app.specter.config["internal_node"]["datadir"])
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
        return {"error": "Bitcoin Core is already installed"}
    elif app.specter.setup_status["bitcoind"]["stage_progress"] != -1:
        return {"error": "Bitcoin Core installation is still under progress"}
    return {"success": "Starting Bitcoin Core setup!"}


@setup_endpoint.route("/setup_bitcoind_datadir", methods=["POST"])
@login_required
def setup_bitcoind_datadir():
    if (
        os.path.isfile(app.specter.bitcoind_path)
        and app.specter.setup_status["bitcoind"]["stage_progress"] == -1
    ):
        app.specter.update_setup_status("bitcoind", "STARTING_SETUP")
        quicksync = request.form["quicksync"] == "true"
        pruned = request.form["nodetype"] == "pruned"
        t = threading.Thread(
            target=setup_bitcoind_directory_thread,
            args=(app.specter, quicksync, pruned),
        )
        t.start()
    elif not os.path.isfile(app.specter.bitcoind_path):
        return {"error": "Bitcoin Core in not installed but required for this step"}
    elif app.specter.setup_status["bitcoind"]["stage_progress"] != -1:
        return {"error": "Bitcoin Core installation is still under progress"}
    return {"success": "Starting Bitcoin Core setup!"}


######################### Setup status (open endpoint) #######################################
@setup_endpoint.route("/get_software_setup_status/<software>")
@login_required
@app.csrf.exempt
def get_software_setup_status(software):
    return app.specter.get_setup_status(software)
