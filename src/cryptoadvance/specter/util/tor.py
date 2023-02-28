import os, platform
from stem.control import Controller
import logging

logger = logging.getLogger(__name__)


def get_tor_daemon_suffix():
    if platform.system() == "Windows":
        return ".exe"
    return ""


def start_hidden_service(app):
    app.specter.tor_controller.authenticate(
        password=app.specter.config.get("torrc_password", "")
    )
    key_path = os.path.abspath(
        os.path.join(app.specter.data_folder, ".tor_service_key")
    )
    app.tor_service_id = None

    if not os.path.exists(key_path):
        service = app.specter.tor_controller.create_ephemeral_hidden_service(
            {app.tor_port: app.port}, await_publication=True
        )
        app.tor_service_id = service.service_id
        print(
            "* Started a new hidden service with the address of %s.onion"
            % app.tor_service_id
        )

        with open(key_path, "w") as key_file:
            key_file.write("%s:%s" % (service.private_key_type, service.private_key))
    else:
        with open(key_path) as key_file:
            key_type, key_content = key_file.read().split(":", 1)

        service = app.specter.tor_controller.create_ephemeral_hidden_service(
            {app.tor_port: app.port},
            key_type=key_type,
            key_content=key_content,
            await_publication=True,
        )
        app.tor_service_id = service.service_id
        print("* Resumed %s.onion" % app.tor_service_id)

    # save address to file
    if app.save_tor_address_to is not None:
        with open(app.save_tor_address_to, "w") as f:
            f.write("%s.onion" % app.tor_service_id)
    app.tor_service_id = app.tor_service_id
    app.tor_enabled = True
    if app.specter.config["auth"].get("method", "none") == "none":
        logger.warning(
            " * ############################# Warning! #############################"
        )
        logger.warning(
            " * Your are running Specter over Tor with no authentication settings configured."
        )
        logger.warning(
            " * This means your Specter instance is accessible to anyone with the .onion URL."
        )
        logger.warning(
            " * This .onion URL is publicly exposed and indexed on the Tor network - it is not secret!"
        )
        logger.warning(
            " * It is stronly adviced that you configure proper authentication while running Specter behind a Tor hidden service."
        )
        logger.warning(
            " * Please go to Settings -> Authentication and set up an authentication method."
        )
        logger.warning(
            " * ####################################################################"
        )


def stop_hidden_services(app):
    try:
        app.specter.tor_controller.authenticate(
            password=app.specter.config.get("torrc_password", "")
        )
        hidden_services = app.specter.tor_controller.list_ephemeral_hidden_services()
        logger.info(" * Shutting down our hidden service")
        for tor_service_id in hidden_services:
            app.specter.tor_controller.remove_ephemeral_hidden_service(tor_service_id)
        # Sanity
        if len(app.specter.tor_controller.list_ephemeral_hidden_services()) != 0:
            logger.error(" * Failed to shut down our hidden services...")
        else:
            logger.info(" * Hidden services were shut down successfully")
            app.tor_service_id = None
    except Exception as e:
        logger.exception(e)
        pass  # we tried...
