from cryptoadvance.specterext.spectrum.controller_helpers import (
    evaluate_current_status,
    check_for_node_on_same_network,
)
from mock import Mock


def test_evaluate_current_status():
    # We changed the host and made the connection work again with it
    node_is_running_before_request, success, host_before_request, host_after_request = (
        False,
        True,
        "127.0.0.1",
        "electrum.emzy.de",
    )
    changed_host, check_port_and_ssl = evaluate_current_status(
        node_is_running_before_request, success, host_before_request, host_after_request
    )
    assert changed_host == True
    assert check_port_and_ssl == False

    # We didn't change anything
    node_is_running_before_request, success, host_before_request, host_after_request = (
        True,
        True,
        "127.0.0.1",
        "127.0.0.1",
    )
    changed_host, check_port_and_ssl = evaluate_current_status(
        node_is_running_before_request, success, host_before_request, host_after_request
    )
    assert changed_host == False
    assert check_port_and_ssl == False

    # We didn't change the host but the connection got lost, which indicates that the ssl / port config was changed
    node_is_running_before_request, success, host_before_request, host_after_request = (
        True,
        False,
        "127.0.0.1",
        "127.0.0.1",
    )
    changed_host, check_port_and_ssl = evaluate_current_status(
        node_is_running_before_request, success, host_before_request, host_after_request
    )
    assert changed_host == False
    assert check_port_and_ssl == True

    # We didn't change the host but the connection can still not be established
    node_is_running_before_request, success, host_before_request, host_after_request = (
        False,
        False,
        "127.0.0.1",
        "127.0.0.1",
    )
    changed_host, check_port_and_ssl = evaluate_current_status(
        node_is_running_before_request, success, host_before_request, host_after_request
    )
    assert changed_host == False
    assert check_port_and_ssl == True

    # We did change the host but the connection can still not be established
    node_is_running_before_request, success, host_before_request, host_after_request = (
        False,
        False,
        "127.0.0.1",
        "electrum.emzy.de",
    )
    changed_host, check_port_and_ssl = evaluate_current_status(
        node_is_running_before_request, success, host_before_request, host_after_request
    )
    assert changed_host == True
    assert check_port_and_ssl == True


def test_check_for_node_on_same_network():
    spectrum_node_mock = Mock()
    spectrum_node_mock.fqcn = (
        "cryptoadvance.specterext.spectrum.spectrum_node.SpectrumNode"
    )
    bitcoin_core_node_mock = Mock()
    bitcoin_core_node_mock.fqcn = "cryptoadvance.specter.node.Node"
    bitcoin_core_node_mock.is_liquid = False
    specter_mock = Mock()
    specter_mock.node_manager.nodes_by_chain.return_value = [
        spectrum_node_mock,
        bitcoin_core_node_mock,
    ]
    assert check_for_node_on_same_network(spectrum_node_mock, specter_mock) == True
