import copy, random, json

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
from ..rpc import get_default_datadir
from ..node import Node


rand = random.randint(0, 1e32)  # to force style refresh

# Setup endpoint blueprint
nodes_endpoint = Blueprint("nodes_endpoint", __name__)


@nodes_endpoint.route(
    "new_node/", defaults={"node_alias": None}, methods=["GET", "POST"]
)
@nodes_endpoint.route("node/<node_alias>/", methods=["GET", "POST"])
@login_required
def node_settings(node_alias):
    err = None
    if node_alias:
        try:
            node = app.specter.node_manager.get_by_alias(node_alias)
        except:
            return render_template(
                "base.jinja", error="Node not found", specter=app.specter, rand=rand
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
        flash("Only an admin is allowed to access this page.", "error")
        return redirect("")
    # The node might have been down but is now up again
    # (and the checker did not realized yet) and the user clicked "Configure Node"
    if node.rpc is None:
        node.update_rpc()

    err = None
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
            if not node_alias:
                node.name = request.form["name"]

        if action == "rename":
            node_name = request.form["newtitle"]
            if not node_name:
                flash("Node name must not be empty", "error")
            elif node_name == node.name:
                pass
            elif node_name in app.specter.device_manager.devices_names:
                flash("Node with this name already exists", "error")
            else:
                node.rename(node_name)
        elif action == "forget":
            if not node_alias:
                flash("Failed to deleted node. Node isn't saved", "error")
            elif len(app.specter.node_manager.nodes) > 1:
                app.specter.node_manager.delete_node(node, app.specter)
                flash("Node deleted successfully")
                return redirect(
                    url_for(
                        "nodes_endpoint.node_settings",
                        node_alias=app.specter.node.alias,
                    )
                )
            else:
                flash(
                    "Failed to deleted node. Specter must have at least one node configured",
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
                if False in list(test["tests"].values()):
                    flash(f"Test failed: {test['err']}", "error")
                else:
                    flash("Test passed", "info")
        elif action == "save":
            if not node_alias:
                if node.name in app.specter.node_manager.nodes:
                    flash(
                        "Node with this name already exits, please choose a different name.",
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
                flash("Failed connecting to the node", "error")
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


@nodes_endpoint.route("switch_node/", methods=["POST"])
@login_required
def switch_node():
    node_alias = request.form["node_alias"]
    app.specter.update_active_node(node_alias)
    return redirect(url_for("nodes_endpoint.node_settings", node_alias=node_alias))
