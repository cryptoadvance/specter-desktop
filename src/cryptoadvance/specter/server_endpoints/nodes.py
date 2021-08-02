import copy, random, json, time, os, shutil, logging

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
from flask_babel import lazy_gettext as _
from flask_login import login_required, current_user
from flask import current_app as app
from ..rpc import get_default_datadir
from ..node import Node
from ..specter_error import ExtProcTimeoutException
from ..util.shell import get_last_lines_from_file

logger = logging.getLogger(__name__)

rand = random.randint(0, 1e32)  # to force style refresh

# Setup endpoint blueprint
nodes_endpoint = Blueprint("nodes_endpoint", __name__)


@nodes_endpoint.route(
    "new_node/", defaults={"node_alias": None}, methods=["GET", "POST"]
)
@nodes_endpoint.route("node/<node_alias>/", methods=["GET", "POST"])
@login_required
def node_settings(node_alias):
    if node_alias:
        try:
            node = app.specter.node_manager.get_by_alias(node_alias)
            if not node.external_node:
                return redirect(
                    url_for(
                        "nodes_endpoint.internal_node_settings",
                        node_alias=node.alias,
                    )
                )
        except:
            return render_template(
                "base.jinja", error=_("Node not found"), specter=app.specter, rand=rand
            )
    else:
        node = Node.from_json(
            {
                "name": "New Node",
                "autodetect": True,
                "datadir": get_default_datadir(),
                "user": "",
                "password": "",
                "port": 8332,
                "host": "localhost",
                "protocol": "http",
                "external_node": True,
            },
            app.specter.node_manager,
        )

    if not current_user.is_admin:
        flash(_("Only an admin is allowed to access this page"), "error")
        return redirect("")
    # The node might have been down but is now up again
    # (and the checker did not realized yet) and the user clicked "Configure Node"
    if node.rpc is None and node_alias:
        node.update_rpc()

    test = None
    if request.method == "POST":
        action = request.form["action"]

        if action != "rename":
            autodetect = "autodetect" in request.form
            if autodetect:
                datadir = request.form["datadir"]
            else:
                datadir = ""
            user = request.form["username"]
            password = request.form["password"]
            port = request.form["port"]
            host = request.form["host"].rstrip("/")
            # protocol://host
            if "://" in host:
                arr = host.split("://")
                protocol = arr[0]
                host = arr[1]
            else:
                protocol = "http"

            if not node_alias:
                node.name = request.form["name"]

        if action == "rename":
            node_name = request.form["newtitle"]
            if not node_name:
                flash(_("Node name cannot be empty"), "error")
            elif node_name == node.name:
                pass
            elif node_name in app.specter.device_manager.devices_names:
                flash(_("Node with this name already exists"), "error")
            else:
                node.rename(node_name)
        elif action == "forget":
            if not node_alias:
                flash(_("Failed to deleted node. Node isn't saved"), "error")
            elif len(app.specter.node_manager.nodes) > 1:
                app.specter.node_manager.delete_node(node, app.specter)
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
        elif action == "test":
            # If this is failing, the test_rpc-method needs improvement
            # Don't wrap this into a try/except otherwise the feedback
            # of what's wrong to the user gets broken
            node = Node(
                node.name,
                node.alias,
                autodetect,
                datadir,
                user,
                password,
                port,
                host,
                protocol,
                node.external_node,
                node.fullpath,
                node.manager,
            )
            test = node.test_rpc()

            if "tests" in test:
                # If any test has failed, we notify the user that the test has not passed
                if not test["tests"] or False in list(test["tests"].values()):
                    flash(_("Test failed: {}").format(test["err"]), "error")
                else:
                    flash(_("Test passed"), "info")
            elif "err" in test:
                flash(_("Test failed: {}").format(test["err"]), "error")
        elif action == "save":
            if not node_alias:
                if node.name in app.specter.node_manager.nodes:
                    flash(
                        _(
                            "Node with this name already exists, please choose a different name."
                        ),
                        "error",
                    )
                    return render_template(
                        "node/node_settings.jinja",
                        node=node,
                        node_alias=node_alias,
                        test=test,
                        specter=app.specter,
                        rand=rand,
                    )
                node = app.specter.node_manager.add_node(
                    node.name,
                    autodetect,
                    datadir,
                    user,
                    password,
                    port,
                    host,
                    protocol,
                    node.external_node,
                )
                app.specter.update_active_node(node.alias)
                return redirect(
                    url_for("nodes_endpoint.node_settings", node_alias=node.alias)
                )

            success = node.update_rpc(
                autodetect=autodetect,
                datadir=datadir,
                user=user,
                password=password,
                port=port,
                host=host,
                protocol=protocol,
            )
            if not success:
                flash(_("Failed connecting to the node"), "error")
            if app.specter.active_node_alias == node.alias:
                app.specter.check()

    return render_template(
        "node/node_settings.jinja",
        node=node,
        node_alias=node_alias,
        test=test,
        specter=app.specter,
        rand=rand,
    )


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
                flash(_("Failed to deleted node. Node isn't saved"), "error")
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
                flash(_("Failed to remove Bitcoin Core, error: {}").format(e), "error")
        elif action == "upgrade_bitcoind":
            if node.version != app.config["INTERNAL_BITCOIND_VERSION"]:
                try:
                    app.specter.node_manager.update_bitcoind_version(
                        app.specter, app.config["INTERNAL_BITCOIND_VERSION"]
                    )
                except Exception as e:
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
    app.specter.update_active_node(node_alias)
    return redirect(url_for("nodes_endpoint.node_settings", node_alias=node_alias))
