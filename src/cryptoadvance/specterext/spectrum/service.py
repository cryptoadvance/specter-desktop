import logging
import os

from cryptoadvance.specter.managers.node_manager import NodeManager
from cryptoadvance.specter.services.service import (
    Service,
    devstatus_prod,
)

# A SpecterError can be raised and will be shown to the user as a red banner
from cryptoadvance.specter.specter_error import SpecterError
from flask import current_app as app
from flask import url_for
from flask_apscheduler import APScheduler
from cryptoadvance.specterext.spectrum.spectrum_node import SpectrumNode
from cryptoadvance.spectrum.server import init_app, Spectrum
from cryptoadvance.spectrum.db import db
from cryptoadvance.specter.specter_error import BrokenCoreConnectionException
from cryptoadvance.specter.server_endpoints.welcome.welcome_vm import WelcomeVm

logger = logging.getLogger(__name__)

spectrum_node_alias = "spectrum_node"


class SpectrumService(Service):
    id = "spectrum"
    name = "Spectrum"
    icon = "spectrum/img/logo.svg"
    logo = "spectrum/img/logo.svg"
    desc = "An electrum hidden behind a core API"
    has_blueprint = True
    blueprint_module = "cryptoadvance.specterext.spectrum.controller"
    devstatus = devstatus_prod
    isolated_client = False

    # TODO: As more Services are integrated, we'll want more robust categorization and sorting logic
    sort_priority = 2

    @property
    def spectrum_node(self):
        """Iterates all nodes and returns the spectrum Node or None if it doesn't exist"""
        for node in app.specter.node_manager.nodes.values():

            if (
                hasattr(node, "fqcn")
                and node.fqcn
                == "cryptoadvance.specterext.spectrum.spectrum_node.SpectrumNode"
            ):
                return node
        return None

    @property
    def is_spectrum_node_available(self):
        """Whether there is a spectrum Node available (activated or not)"""
        return not self.spectrum_node is None

    @property
    def is_spectrum_node_running(self):
        if self.is_spectrum_node_available:
            return self.spectrum_node.is_running
        return False

    def callback_specter_added_to_flask_app(self):
        logger.debug("Setting up Spectrum ...")
        # See comments in config.py which would be the natural place to define SPECTRUM_DATADIR
        # but we want to avoid RuntimeError: Working outside of application context.
        app.config["SPECTRUM_DATADIR"] = os.path.join(
            app.config["SPECTER_DATA_FOLDER"], "sqlite"
        )
        app.config["DATABASE"] = os.path.abspath(
            os.path.join(app.config["SPECTRUM_DATADIR"], "db.sqlite")
        )
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + app.config["DATABASE"]

        if not os.path.exists(app.config["SPECTRUM_DATADIR"]):
            os.makedirs(app.config["SPECTRUM_DATADIR"])
        logger.info(
            f"Intitializing Database in {app.config['SQLALCHEMY_DATABASE_URI']}"
        )
        db.init_app(app)
        db.create_all()
        # Check whether there is a Spectrum node in the node manager of Specter
        if self.is_spectrum_node_available:
            try:
                self.spectrum_node.start_spectrum(app, self.data_folder)
            except BrokenCoreConnectionException as e:
                logger.error(e)
        self.specter.checker.run_now()

    # TODO: Refactor this or the next function to only have one
    def enable_default_spectrum(self):
        """* Creates and saves a Spectrum node if there is none with the default config values ("ELECTRUM_DEFAULT_OPTION")
        * Starts Spectrum
        * Switches to the Spectrum node
        """
        if not self.is_spectrum_node_available:
            # No SpectrumNode yet created. Let's do that.
            default_electrum = app.config["ELECTRUM_DEFAULT_OPTION"]
            spectrum_node = SpectrumNode(
                host=app.config["ELECTRUM_OPTIONS"][default_electrum]["host"],
                port=app.config["ELECTRUM_OPTIONS"][default_electrum]["port"],
                ssl=app.config["ELECTRUM_OPTIONS"][default_electrum]["ssl"],
            )
            app.specter.node_manager.nodes[spectrum_node_alias] = spectrum_node
            app.specter.node_manager.save_node(spectrum_node)
        self.spectrum_node.start_spectrum(app, self.data_folder)
        self.activate_spectrum_node()

    def enable_spectrum(self, host, port, ssl, activate_spectrum_node=False):
        """* Creates a Spectrum node if there is none
        * Starts Spectrum
        * Does by default NOT yet switch to the Spectrum node nor yet save the node to disk
        """
        if not self.is_spectrum_node_available:
            # No SpectrumNode yet created. Let's do that.
            logger.debug("Creating a Spectrum node ...")
            spectrum_node = SpectrumNode(host=host, port=port, ssl=ssl)
            app.specter.node_manager.nodes[spectrum_node_alias] = spectrum_node
        self.spectrum_node.start_spectrum(app, self.data_folder)
        if activate_spectrum_node:
            self.activate_spectrum_node()

    def disable_spectrum(self):
        """Stops Spectrum and deletes the Spectrum node"""
        self.spectrum_node.stop_spectrum()
        spectrum_node = None
        if self.is_spectrum_node_available:
            app.specter.node_manager.delete_node(self.spectrum_node, app.specter)
        logger.info("Spectrum disabled")

    def update_electrum(self, host, port, ssl):
        if not self.is_spectrum_node_available:
            raise Exception("No Spectrum node available. Cannot start Spectrum.")
        logger.info(f"Updating Spectrum node with {host}:{port} (ssl: {ssl})")
        self.spectrum_node.update_electrum(host, port, ssl, app, self.data_folder)

    def activate_spectrum_node(self):
        """Makes the Spectrum node the new active node and saves it to disk"""
        logger.info("Activating Spectrum node.")
        if not self.is_spectrum_node_available:
            raise Exception("Spectrum is not enabled. Cannot start Electrum")
        nm: NodeManager = app.specter.node_manager
        if self.spectrum_node.is_running:
            app.specter.update_active_node(spectrum_node_alias)
            app.specter.node_manager.save_node(self.spectrum_node)
            logger.info(
                f"Activated node {self.spectrum_node} with rpc {self.spectrum_node.rpc}"
            )
        else:
            raise SpecterError(
                "Trying to switch Spectrum node but there seems to be a connection problem."
            )

    def callback_adjust_view_model(self, view_model: WelcomeVm):
        if view_model.__class__.__name__ == "WelcomeVm":
            # potentially, we could make a reidrect here:
            # view_model.about_redirect=url_for("spectrum_endpoint.some_enpoint_here")
            # but we do it small here and only replace a specific component:
            view_model.get_started_include = (
                "spectrum/welcome/components/get_started.jinja"
            )
            if self.is_spectrum_node_available:
                view_model.tick_checkboxes_include = (
                    "spectrum/welcome/components/tick_checkboxes.jinja"
                )
        return view_model
