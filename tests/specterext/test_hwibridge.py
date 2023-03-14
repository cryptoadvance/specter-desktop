import json, requests
from cryptoadvance.specter.devices.ledger import Ledger
from cryptoadvance.specter.devices.trezor import Trezor


def test_malformed_parse_error(client):
    client.environ_base["HTTP_ORIGIN"] = "http://127.0.0.1:25441/"
    req = client.post("http://127.0.0.1:25441/hwi/api/", data=b"{'muh':'meh'}")
    assert {
        "jsonrpc": "2.0",
        "error": {
            "code": -32700,
            "message": "Parse error:Expecting property name enclosed in double quotes: line 1 column 2 (char 1)",
        },
        "id": None,
    } == json.loads(req.data)


def test_call_unauthorized_origin(client):
    client.environ_base["HTTP_ORIGIN"] = "http://unauthorized_domain.com/"
    req = client.post(
        "http://127.0.0.1:25441/hwi/api/",
        json={
            "jsonrpc": "2.0",
            "method": "enumerate",
            "id": 1,
            "params": {},
            "forwarded_request": True,
        },
    )
    assert {
        "jsonrpc": "2.0",
        "error": {
            "code": -32001,
            "message": "Unauthorized request origin.<br>You must first whitelist this website URL in HWIBridge settings to grant it access.",
        },
        "id": None,
    } == json.loads(req.data)


def test_call_without_method(client):
    client.environ_base["HTTP_ORIGIN"] = "http://127.0.0.1:25441/"
    req = client.post(
        "http://127.0.0.1:25441/hwi/api/",
        json={"jsonrpc": "2.0", "id": 1, "params": {}, "forwarded_request": True},
    )
    assert {
        "jsonrpc": "2.0",
        "error": {
            "code": -32600,
            "message": "Invalid Request. Request must specify a 'method'.",
        },
        "id": 1,
    } == json.loads(req.data)


def test_call_non_existing_method(client):
    client.environ_base["HTTP_ORIGIN"] = "http://127.0.0.1:25441/"
    req = client.post(
        "http://127.0.0.1:25441/hwi/api/",
        json={
            "jsonrpc": "2.0",
            "method": "enumerate_2",
            "id": 1,
            "params": {},
            "forwarded_request": True,
        },
    )
    assert {
        "jsonrpc": "2.0",
        "error": {"code": -32601, "message": "Method not found."},
        "id": 1,
    } == json.loads(req.data)


def test_enumerate_request_success(client):
    client.environ_base["HTTP_ORIGIN"] = "http://127.0.0.1:25441/"
    req = client.post(
        "http://127.0.0.1:25441/hwi/api/",
        json={
            "jsonrpc": "2.0",
            "method": "enumerate",
            "id": 1,
            "params": {},
            "forwarded_request": True,
        },
    )
    assert {"id": 1, "jsonrpc": "2.0", "result": []} == json.loads(req.data)


def test_request_success_localhost_origin(client):
    client.environ_base["HTTP_ORIGIN"] = "http://localhost:25441/"
    req = client.post(
        "http://127.0.0.1:25441/hwi/api/",
        json={
            "jsonrpc": "2.0",
            "method": "enumerate",
            "id": 1,
            "params": {},
            "forwarded_request": True,
        },
    )
    assert {"id": 1, "jsonrpc": "2.0", "result": []} == json.loads(req.data)


def test_calling_method_with_non_existing_parameters(client):
    client.environ_base["HTTP_ORIGIN"] = "http://127.0.0.1:25441/"
    req = client.post(
        "http://127.0.0.1:25441/hwi/api/",
        json={
            "jsonrpc": "2.0",
            "method": "enumerate",
            "id": 1,
            "params": {"non_existing_parameter": True},
            "forwarded_request": True,
        },
    )

    resp = json.loads(req.data)
    assert resp["error"]["code"] == -32000
    assert resp["error"]["message"].startswith("Internal error:")
    assert resp["error"]["message"].endswith(
        "got an unexpected keyword argument 'non_existing_parameter'."
    )
    assert resp["id"] == 1
    assert resp["jsonrpc"] == "2.0"


def test_call_not_connected_device(client):
    client.environ_base["HTTP_ORIGIN"] = "http://127.0.0.1:25441/"
    req = client.post(
        "http://127.0.0.1:25441/hwi/api/",
        json={
            "jsonrpc": "2.0",
            "method": "prompt_pin",
            "id": 1,
            "params": {
                "device_type": Trezor.device_type,
                "path": "",
                "passphrase": "",
                "chain": "test",
            },
            "forwarded_request": True,
        },
    )
    assert {
        "jsonrpc": "2.0",
        "error": {
            "code": -32000,
            "message": "Internal error: The device could not be found. Please check it is properly connected and try again.",
        },
        "id": 1,
    } == json.loads(req.data)


def test_call_prompt_pin_invalid_device(client):
    client.environ_base["HTTP_ORIGIN"] = "http://127.0.0.1:25441/"
    req = client.post(
        "http://127.0.0.1:25441/hwi/api/",
        json={
            "jsonrpc": "2.0",
            "method": "prompt_pin",
            "id": 1,
            "params": {
                "device_type": Ledger.device_type,
                "path": "",
                "passphrase": "",
                "chain": "test",
            },
            "forwarded_request": True,
        },
    )
    assert {
        "jsonrpc": "2.0",
        "error": {
            "code": -32000,
            "message": "Internal error: Invalid HWI device type ledger, prompt_pin is only supported for Trezor and Keepkey devices.",
        },
        "id": 1,
    } == json.loads(req.data)
