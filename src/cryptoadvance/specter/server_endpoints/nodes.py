import copy, random, json, time, os, shutil, logging

from flask import (
    Flask,
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
)
from flask_babel import lazy_gettext as _
from flask_login import login_required, current_user
from flask import current_app as app, session
from ..rpc import get_default_datadir, get_rpcconfig
from ..node import Node
from ..specter_error import (
    ExtProcTimeoutException,
    BrokenCoreConnectionException,
    SpecterError,
)
from ..util.shell import get_last_lines_from_file
from ..server_endpoints import flash

logger = logging.getLogger(__name__)

rand = random.randint(0, 1e32)  # to force style refresh

# Setup endpoint blueprint
nodes_endpoint = Blueprint("nodes_endpoint", __name__)


@nodes_endpoint.route("new_node/", methods=["GET"])
@login_required
def node_settings_new_node_get():
    if not current_user.is_admin:
        flash(_("Only an admin is allowed to access this page"), "error")
        return redirect("")
    bitcoin_conf_values = False
    # First check whether the Bitcoin Core data directory can be accessed at all
    datadir_accessable = False
    node_type = "BTC"
    default_datadir = get_default_datadir(node_type)
    if os.path.exists(default_datadir):
        datadir_accessable = True
    # If the data directory can be accessed, we can try reading config values from a bitcoin.conf file
    if datadir_accessable:
        config = get_rpcconfig(default_datadir)["bitcoin.conf"]
        bitcoin_conf_values = False
        for key, value in config.items():
            if value:
                bitcoin_conf_values = True
                break
        if bitcoin_conf_values:
            user = config["default"].get("rpcuser", "")
            password = config["default"].get("rpcpassword", "")
            port = 8332
            # Try-except only necessary for regtest or testnet
            try:
                if config["default"]["rpcport"]:
                    port = config["default"].get("rpcport", 8332)
            except KeyError:
                for key, value in config.items():
                    if "rpcport" in value:
                        port = value["rpcport"]
                        break

            node = Node.from_json(
                {
                    "name": "",
                    "autodetect": True,
                    "node_type": node_type,
                    "datadir": default_datadir,
                    "user": user,
                    "password": password,
                    "port": port,
                    "host": "localhost",
                    "protocol": "http",
                },
                app.specter.node_manager,
            )
            flash(
                f"Values from a {node_type} configuration file used. Double-check and click connect.",
                "warning",
            )
        else:
            node = Node.from_json(
                {
                    "name": "",
                    "autodetect": False,
                    "node_type": node_type,
                    "datadir": default_datadir,
                    "user": "",
                    "password": "",
                    "port": 8332,
                    "host": "localhost",
                    "protocol": "http",
                },
                app.specter.node_manager,
            )
    else:
        node = Node.from_json(
            {
                "name": "",
                "autodetect": False,
                "datadir": "",
                "user": "",
                "password": "",
                "port": 8332,
                "host": "",
                "protocol": "http",
            },
            app.specter.node_manager,
        )
    session["new_node"] = node.json
    return render_template(
        "node/node_settings.jinja",
        node=node,
        bitcoin_conf_values=bitcoin_conf_values,
        datadir_accessable=datadir_accessable,
        specter=app.specter,
        rand=rand,
    )


@nodes_endpoint.route("node/<node_alias>/", methods=["GET"])
@login_required
def node_settings_get(node_alias):
    if not current_user.is_admin:
        flash(_("Only an admin is allowed to access this page"), "error")
        return redirect("")
    try:
        node: Node = app.specter.node_manager.get_by_alias(node_alias)
        if not node.is_specter_core_object:
            return redirect(
                url_for(
                    # This is a convention which should be documented
                    # Maybe we should do that differently
                    f"{node.blueprint}.node_settings",
                    node_alias=node.alias,
                )
            )
        if not node.external_node:
            return redirect(
                url_for(
                    "nodes_endpoint.internal_node_settings",
                    node_alias=node.alias,
                )
            )
    except SpecterError as se:
        assert str(se).endswith("does not exist!")
        return render_template(
            "base.jinja",
            error=_("Node not found"),
            specter=app.specter,
            rand=rand,
        )
    return render_template(
        "node/node_settings.jinja",
        node=node,
        node_alias=node_alias,
        specter=app.specter,
        rand=rand,
    )


@nodes_endpoint.route("new_node/", defaults={"node_alias": None}, methods=["POST"])
@nodes_endpoint.route("node/<node_alias>/", methods=["POST"])
@login_required
def node_settings(node_alias):
    if not current_user.is_admin:
        flash(_("Only an admin is allowed to access this page"), "error")
        return redirect("")
    node_manager = app.specter.node_manager
    if node_alias:
        node = node_manager.get_by_alias(node_alias)
    else:
        node_json = session.get("new_node", None)
        node = Node.from_json(node_json, node_manager)
    test = None
    failed_test = ""
    # The node might have been down but is up again and the checker did not realise it when the user clicked to configure the connection
    if node.rpc is None and node_alias:
        node.update_rpc()
    action = request.form["action"]
    if action == "delete":
        if not node_alias:
            flash(
                _("Failed to delete connection, connection had not been saved before."),
                "error",
            )
        else:
            node_manager.delete_node(node, app.specter)
            if len(node_manager.nodes) > 0:
                flash(
                    _(
                        "Connection deleted successfully, switched to the next available connection"
                    )
                )
                return redirect(
                    url_for(
                        "nodes_endpoint.node_settings_get",
                        node_alias=app.specter.node.alias,
                    )
                )
            else:
                flash(
                    _(
                        "Connection deleted successfully, you need to configure a new connection"
                    )
                )
                return redirect(
                    url_for(
                        "nodes_endpoint.node_settings_new_node_get",
                    )
                )
    elif action == "connect":
        user = request.form["username"]
        password = request.form["password"]
        port = request.form["port"]
        # Set the node type (BTC or ELM) - TODO: Remove if the Liquid node inherits from the abstract node as the Spectrum node does
        node_type = "BTC"
        liquid_ports = [7041, 18891, 18884]
        if port != "" and int(port) in liquid_ports:  # port is a string
            node_type = "ELM"
        host = request.form["host"].rstrip("/")
        protocol = ""
        if "://" in host:
            arr = host.split("://")
            protocol = arr[0]
            host = arr[1]
        else:
            protocol = "http"
        if not node_alias:
            # Name form field is only used when setting up new nodes
            node.name = request.form["name"]
            if node.name in node_manager.nodes_names:
                flash(
                    _(
                        "Connection with this name already exists, please choose a different name."
                    ),
                    "error",
                )
                return render_template(
                    "node/node_settings.jinja",
                    node=node,
                    node_alias=node_alias,
                    specter=app.specter,
                    rand=rand,
                )
            node_for_test = Node(
                node.name,
                node.alias,
                False,  # We set this to False for the test to avoid a re-establishment of the rpc connection by re-reading the bitcoin.conf
                node.datadir,
                user,
                password,
                port,
                host,
                protocol,
                node.fullpath,
                node_type,
                node_manager,
            )
            test = node_for_test.test_rpc()
            if not test["tests"] or False in list(test["tests"].values()):
                flash(
                    _(f"Connection attempt failed, configuration changes needed"),
                    "error",
                )
                # Determine the first failed test
                for test_name, value in test["tests"].items():
                    if value == False:
                        failed_test = test_name
                        break
                return render_template(
                    "node/node_settings.jinja",
                    node=node_for_test,
                    node_alias=node_alias,
                    test=test,
                    failed_test=failed_test,
                    specter=app.specter,
                    rand=rand,
                )
            else:
                # All good, we can save the node to the node manager, to disk and switch to it
                autodetect = node.autodetect
                # Set autodetect to False for Cypress tests
                if app.config["SPECTER_CONFIGURATION_CLASS_FULLNAME"].endswith(
                    "CypressTestConfig"
                ):
                    autodetect = False
                connectable_node = node_manager.add_external_node(
                    node_type,
                    node.name,
                    autodetect,
                    node.datadir,
                    user,
                    password,
                    port,
                    host,
                    protocol,
                )
                app.specter.update_active_node(connectable_node.alias)
                if len(node_manager.nodes_by_chain(app.specter.chain)) > 1:
                    flash(
                        f"You connected to more than one Bitcoin Core node on the same network ({app.specter.chain}). Your connection was saved. But be aware, this is a beta feature.",
                        "warning",
                    )
                else:
                    flash(_(f"New connection saved and selected"))
                return redirect(url_for("welcome_endpoint.index"))
        else:
            # Updating a node with autodetect with incorrect values doesn't lead to a failure since the get_rpc in the node class
            # is re-establishing the rpc connection by re-reading the bitcoin.conf. To avoid confusion we set autodetect here to False.
            success = node.update_rpc(
                user=user,
                password=password,
                port=port,
                host=host,
                protocol=protocol,
                autodetect=False,
            )
            if not success:
                node_for_test = Node(
                    node.name,
                    node.alias,
                    False,  # We set this to False for the test to avoid a re-establishment of the rpc connection by re-reading the bitcoin.conf
                    node.datadir,
                    user,
                    password,
                    port,
                    host,
                    protocol,
                    node.fullpath,
                    node_type,
                    node_manager,
                )
                test = node_for_test.test_rpc()
                if not test["tests"] or False in list(test["tests"].values()):
                    flash(
                        _(f"Update of configuration failed"),
                        "error",
                    )
                    # Determine the first failed test
                    for test_name, value in test["tests"].items():
                        if value == False:
                            failed_test = test_name
                            break
                    return render_template(
                        "node/node_settings.jinja",
                        node=node_for_test,
                        node_alias=node_alias,
                        test=test,
                        failed_test=failed_test,
                        specter=app.specter,
                        rand=rand,
                    )
            if success:
                flash(
                    _(
                        f"Configuration details updated successfully, switched to {node.name} connection"
                    )
                )
                app.specter.update_active_node(node.alias)
                return redirect(url_for("welcome_endpoint.index"))


@nodes_endpoint.route("specter_node/<node_alias>/", methods=["GET", "POST"])
@login_required
def internal_node_settings(node_alias):
    err = None
    if node_alias:
        try:
            node = app.specter.node_manager.get_by_alias(node_alias)
            if node.external_node:
                return redirect(
                    url_for(
                        "nodes_endpoint.node_settings",
                        node_alias=node.alias,
                    )
                )
        except:
            return render_template(
                "base.jinja", error=_("Node not found"), specter=app.specter, rand=rand
            )
    else:
        # TODO: Allow internal node setup here?
        return redirect(
            url_for(
                "nodes_endpoint.internal_node_settings",
                node_alias=node.alias,
            )
        )

    if not current_user.is_admin:
        flash(_("Only an admin is allowed to access this page"), "error")
        return redirect("")
    # The node might have been down but is now up again
    # (and the checker did not realized yet) and the user clicked "Configure Node"
    if node.rpc is None or not node.is_bitcoind_running():
        node.update_rpc()

    if request.method == "POST":
        action = request.form["action"]

        if action == "rename":
            node_name = request.form["newtitle"]
            if not node_name:
                flash(_("Node name must not be empty"), "error")
            elif node_name == node.name:
                pass
            elif node_name in app.specter.device_manager.devices_names:
                flash("Node with this name already exists", "error")
            else:
                node.rename(node_name)
        elif action == "forget":
            if not node_alias:
                flash(_("Failed to delete node. Node isn't saved"), "error")
            elif len(app.specter.node_manager.nodes) > 1:
                node.stop()
                app.specter.node_manager.delete_node(node, app.specter)
                if bool(request.form.get("remove_datadir", False)):
                    shutil.rmtree(os.path.expanduser(node.datadir), ignore_errors=True)
                flash(_("Node deleted successfully"))
                return redirect(
                    url_for(
                        "nodes_endpoint.node_settings",
                        node_alias=app.specter.node.alias,
                    )
                )
            else:
                flash(
                    _(
                        "Failed to delete node. Specter must have at least one node configured"
                    ),
                    "error",
                )
        elif action == "stopbitcoind":
            try:
                node.stop()
                time.sleep(5)
                flash(_("Specter successfully stopped Bitcoin Core"))
            except Exception as e:
                try:
                    logger.exception(e)
                    flash(_("Stopping Bitcoin Core, this might take a few moments."))
                    node.rpc.stop()
                except Exception as ne:
                    logger.exception(ne)
                    flash(_("Failed to stop Bitcoin Core {}").format(ne), "error")
        elif action == "startbitcoind":
            if node.start(timeout=120):
                flash(_("Specter has started Bitcoin Core"))
            else:
                flash(_("Specter failed to start the node"), "error")
        elif action == "uninstall_bitcoind":
            try:
                node.stop()
                shutil.rmtree(
                    os.path.join(app.specter.data_folder, "bitcoin-binaries"),
                    ignore_errors=True,
                )
                if bool(request.form.get("remove_datadir", False)):
                    shutil.rmtree(os.path.expanduser(node.datadir), ignore_errors=True)
                flash(_("Bitcoin Core successfully uninstalled"))
                app.specter.node_manager.delete_node(node, app.specter)
                return redirect(
                    url_for(
                        "nodes_endpoint.node_settings",
                        node_alias=app.specter.node.alias,
                    )
                )
            except Exception as e:
                logger.exception(e)
                flash(_("Failed to remove Bitcoin Core, error: {}").format(e), "error")
        elif action == "upgrade_bitcoind":
            if node.version != app.config["INTERNAL_BITCOIND_VERSION"]:
                try:
                    app.specter.node_manager.update_bitcoind_version(
                        app.specter, app.config["INTERNAL_BITCOIND_VERSION"]
                    )
                except Exception as e:
                    logger.exception(e)
                    flash(
                        _("Failed to upgrade Bitcoin Core version, error: {}").format(
                            e
                        ),
                        "error",
                    )
            else:
                flash(_("Bitcoin Core version is already up to date"))
    return render_template(
        "node/internal_node_settings.jinja",
        node=node,
        latest_bitcoind=app.config["INTERNAL_BITCOIND_VERSION"],
        node_alias=node_alias,
        specter=app.specter,
        rand=rand,
    )


@nodes_endpoint.route("/internal_node_logs/<node_alias>/", methods=["GET"])
@login_required
def internal_node_logs(node_alias):
    node = app.specter.node_manager.get_by_alias(node_alias)
    logfile_location = os.path.join(node.datadir, "debug.log")
    return render_template(
        "node/internal_node_logs.jinja",
        node_alias=node_alias,
        specter=app.specter,
        loglines="".join(get_last_lines_from_file(logfile_location)),
    )


@nodes_endpoint.route("switch_node/", methods=["POST"])
@login_required
def switch_node():
    node_alias = request.form["node_alias"]
    node = app.specter.node_manager.get_by_alias(node_alias)
    if node.is_running:
        app.specter.update_active_node(node_alias)
        flash(_(f"Switched to use {node.name} as connection"))
        return redirect(url_for("index"))
    else:
        flash(
            _(
                f"Can't select {node.name} (no connection). Try a different configuration."
            ),
            "error",
        )
        return redirect(url_for("nodes_endpoint.node_settings", node_alias=node.alias))


@nodes_endpoint.route("rename/", methods=["POST"])
@login_required
def rename_node():
    new_name = request.form["newName"]
    node_alias = request.form["nodeAlias"]
    node_manager = app.specter.node_manager
    node = node_manager.get_by_alias(node_alias)
    if not new_name:
        # Should not be possible because of the required, but still ...
        response = {"nameChanged": False, "error": "Name cannot be empty"}
    elif node.name == new_name:
        response = {"nameChanged": False, "error": "You didn't change the name."}
    elif new_name in node_manager.nodes_names:
        response = {
            "nameChanged": False,
            "error": "A connection with this name already exists, please choose a different name.",
        }
    else:
        node.rename(new_name)
        response = {"nameChanged": True, "error": None}
    return jsonify(response)


@nodes_endpoint.route("sync_status/", methods=["GET"])
@login_required
def check_sync_status():
    if app.specter.node.rpc.getblockchaininfo()["initialblockdownload"] == True:
        response = {"fullySynced": False}
    else:
        response = {"fullySynced": True}
    return jsonify(response)


# Currently only used for Spectrum
@nodes_endpoint.route("sync_progress/", methods=["GET"])
@login_required
def get_sync_progress():
    sync_progress = (
        app.specter.node.rpc.getblockchaininfo()["verificationprogress"] * 100
    )
    response = {"syncProgress": sync_progress}
    return jsonify(response)
