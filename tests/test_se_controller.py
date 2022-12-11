from cryptoadvance.specter.rpc import RpcError
from cryptoadvance.specter.specter_error import (
    BrokenCoreConnectionException,
    ExtProcTimeoutException,
    SpecterError,
)
from mock import patch
from werkzeug.exceptions import MethodNotAllowed, NotFound
from flask_wtf.csrf import CSRFError


def test_controller_error_handling_RpcError(app):
    from cryptoadvance.specter.server_endpoints.controller import server_rpc_error

    with app.test_request_context(environ_base={"HTTP_ACCEPT": "application/json"}):
        assert server_rpc_error(RpcError("Muh!")) == {"error": "Muh!"}
    with app.test_request_context(environ_base={"HTTP_ACCEPT": "*/*"}):
        with patch(
            "cryptoadvance.specter.server_endpoints.controller.flash"
        ) as mock_flash:
            response = server_rpc_error(RpcError("Muh!"))
            assert response.status_code == 302  # redirect
            assert mock_flash.called


def test_controller_error_handling_SpecterError(app):
    from cryptoadvance.specter.server_endpoints.controller import server_specter_error

    with app.test_request_context(environ_base={"HTTP_ACCEPT": "application/json"}):
        assert server_specter_error(SpecterError("Muh!")) == {"error": "Muh!"}
    with app.test_request_context(environ_base={"HTTP_ACCEPT": "*/*"}):
        with patch(
            "cryptoadvance.specter.server_endpoints.controller.flash"
        ) as mock_flash:
            response = server_specter_error(SpecterError("Muh!"))
            assert response.status_code == 302  # redirect
            assert mock_flash.called


def test_controller_error_handling_NotFound(app):
    from cryptoadvance.specter.server_endpoints.controller import server_notFound_error

    with app.test_request_context(environ_base={"HTTP_ACCEPT": "application/json"}):
        assert server_notFound_error(NotFound("Muh!"))["error"].startswith(
            "Could not find Resource (404)"
        )
    with app.test_request_context(environ_base={"HTTP_ACCEPT": "*/*"}):
        with patch(
            "cryptoadvance.specter.server_endpoints.controller.flash"
        ) as mock_flash:
            response, status_code = server_notFound_error(NotFound("Muh!"))
            assert status_code == 404
            assert not mock_flash.called


def test_controller_error_handling_Exception(app):
    from cryptoadvance.specter.server_endpoints.controller import server_error

    with app.test_request_context(environ_base={"HTTP_ACCEPT": "application/json"}):
        assert server_error(Exception("Muh!"))["error"].startswith("Uncaught exception")
    with app.test_request_context(environ_base={"HTTP_ACCEPT": "*/*"}):
        with patch(
            "cryptoadvance.specter.server_endpoints.controller.flash"
        ) as mock_flash:
            response, status_code = server_error(Exception("Muh!"))
            assert status_code == 500
            assert not mock_flash.called


def test_controller_error_handling_BrokenCoreConnectionException(app):
    from cryptoadvance.specter.server_endpoints.controller import (
        server_broken_core_connection,
    )

    with app.test_request_context(environ_base={"HTTP_ACCEPT": "application/json"}):
        assert server_broken_core_connection(BrokenCoreConnectionException("Muh!"))[
            "error"
        ].startswith("You got disconnected from your node (no RPC connection)")
    with app.test_request_context(environ_base={"HTTP_ACCEPT": "*/*"}):
        with patch(
            "cryptoadvance.specter.server_endpoints.controller.flash"
        ) as mock_flash:
            response = server_broken_core_connection(
                BrokenCoreConnectionException("Muh!")
            )
            assert response.status_code == 302
            assert mock_flash.called


def test_controller_error_handling_ExtProcTimeoutException(app):
    from cryptoadvance.specter.server_endpoints.controller import server_error_timeout

    with app.test_request_context(environ_base={"HTTP_ACCEPT": "application/json"}):
        assert server_error_timeout(ExtProcTimeoutException("Muh!"))[
            "error"
        ].startswith("Bitcoin Core is not coming up in time. ")
    with app.test_request_context(environ_base={"HTTP_ACCEPT": "*/*"}):
        with patch(
            "cryptoadvance.specter.server_endpoints.controller.flash"
        ) as mock_flash:
            response = server_error_timeout(ExtProcTimeoutException("Muh!"))
            assert response.status_code == 302
            assert mock_flash.called


def test_controller_error_handling_CSRFError(app):
    from cryptoadvance.specter.server_endpoints.controller import server_error_csrf

    with app.test_request_context(environ_base={"HTTP_ACCEPT": "application/json"}):
        assert server_error_csrf(CSRFError("Muh!"))["error"].startswith(
            "Session expired (CSRF)."
        )
    with app.test_request_context(environ_base={"HTTP_ACCEPT": "*/*"}):
        with patch(
            "cryptoadvance.specter.server_endpoints.controller.flash"
        ) as mock_flash:
            response = server_error_csrf(CSRFError("Muh!"))
            assert response.status_code == 302
            assert mock_flash.called


def test_controller_error_handling_MethodNotAllowed(app):
    from cryptoadvance.specter.server_endpoints.controller import server_error_405

    with app.test_request_context(environ_base={"HTTP_ACCEPT": "application/json"}):
        assert server_error_405(MethodNotAllowed("Muh!"))["error"].startswith(
            "405 method not allowed. Token might have expired."
        )
    with app.test_request_context(environ_base={"HTTP_ACCEPT": "*/*"}):
        with patch(
            "cryptoadvance.specter.server_endpoints.controller.flash"
        ) as mock_flash:
            response = server_error_405(MethodNotAllowed("Muh!"))
            assert response.status_code == 302
            assert mock_flash.called
