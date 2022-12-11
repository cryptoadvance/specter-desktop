import logging

from cryptoadvance.specter.specter import Specter
from flask import current_app as app

from .service import SpectrumService

logger = logging.getLogger(__name__)


def ext() -> SpectrumService:
    """convenience for getting the extension-object"""
    return app.specter.ext["spectrum"]


def specter() -> Specter:
    """convenience for getting the specter-object"""
    return app.specter


def check_for_node_on_same_network(spectrum_node, specter: Specter):
    if spectrum_node is not None:
        current_spectrum_chain = spectrum_node.chain
        nodes_current_chain = specter.node_manager.nodes_by_chain(
            current_spectrum_chain
        )
        # Check whether there is a Bitcoin Core node for the same network:
        core_node_exists = False
        for node in nodes_current_chain:
            logger.debug(node)
            if (
                node.fqcn
                != "cryptoadvance.specterext.spectrum.spectrum_node.SpectrumNode"
                and not node.is_liquid
            ):
                return True
    return False


def evaluate_current_status(
    node_is_running_before_request, success, host_before_request, host_after_request
):
    """Figures out whether the:
    * the user changed the host and/or
    * the user changed the port/ssl
    and returns two booleans: changed_host, check_port_and_ssl
    useful for user-feedback.
    """
    changed_host = False
    check_port_and_ssl = False
    if (
        node_is_running_before_request == success
        and success == True
        and host_before_request != host_after_request
    ):
        # Case 2: We changed the host but switched from one working connection to another one
        changed_host = True
    if node_is_running_before_request and not success:
        # Case 3: We changed the host from a working to a broken connection
        if host_before_request != host_after_request:
            changed_host = True
        # Case 4: We didn't change the host but probably other configs such as port and / or ssl which are likely the reason for the broken connection
        # TODO: Worth it to also check for changes in the port / ssl configs?
        else:
            check_port_and_ssl = True
    if not node_is_running_before_request and success:
        # Case 5: We changed the host from a broken to a working connection
        if host_before_request != host_after_request and host_before_request != None:
            changed_host = True
        # Case 6: We didn't change the host but only the port and / or ssl config which did the trick
        else:
            # Not necessary since this is set to False by default, just to improve readability
            check_port_and_ssl = False
    if not node_is_running_before_request and not success:
        # Case 7: We don't get a connection running for the current host, perhaps it is due to the port / ssl
        if host_before_request == host_after_request and host_before_request != None:
            check_port_and_ssl = True
        # Case 7: Unclear what the issue is, best to check everything
        if host_before_request != host_after_request:
            changed_host = True
            check_port_and_ssl = True

    return changed_host, check_port_and_ssl
