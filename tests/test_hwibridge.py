import json, requests

def test_malformed_parse_error():
    requests_session = requests.Session()
    requests_session.headers.update({ 'origin': 'http://127.0.0.1:25441/' })
    req = requests_session.post('http://127.0.0.1:25441/hwi/api/', data=b'malformed')
    assert { 
        "jsonrpc": "2.0",
        "error": { "code": -32700, "message": "Parse error" },
        "id": None
    } == json.loads(req.content)

def test_call_unauthorized_origin():
    requests_session = requests.Session()
    requests_session.headers.update({ 'origin': 'http://unauthorized_domain.com/' })
    req = requests_session.post('http://127.0.0.1:25441/hwi/api/', data=json.dumps({
        'jsonrpc': '2.0',
        'method': 'enumerate',
        'id': 1,
        'params': {},
        'forwarded_request': True
    }))
    assert { 
        "jsonrpc": "2.0",
        "error": { "code": -32001, "message": "Unauthorized request origin.<br>You must first whitelist this website URL in HWIBridge settings to grant it access." },
        "id": None
    } == json.loads(req.content)

def test_call_without_method():
    requests_session = requests.Session()
    requests_session.headers.update({ 'origin': 'http://127.0.0.1:25441/' })
    req = requests_session.post('http://127.0.0.1:25441/hwi/api/', data=json.dumps({
        'jsonrpc': '2.0',
        'id': 1,
        'params': {},
        'forwarded_request': True
    }))
    assert { 
        "jsonrpc": "2.0",
        "error": { "code": -32600, "message": "Invalid Request. Request must specify a 'method'." },
        "id": 1
    } == json.loads(req.content)

def test_call_non_existing_method():
    requests_session = requests.Session()
    requests_session.headers.update({ 'origin': 'http://127.0.0.1:25441/' })
    req = requests_session.post('http://127.0.0.1:25441/hwi/api/', data=json.dumps({
        'jsonrpc': '2.0',
        'method': 'enumerate_2',
        'id': 1,
        'params': {},
        'forwarded_request': True
    }))
    assert { 
        "jsonrpc": "2.0",
        "error": { "code": -32601, "message": "Method not found" },
        "id": 1
    } == json.loads(req.content)

def test_enumerate_request_success():
    requests_session = requests.Session()
    requests_session.headers.update({ 'origin': 'http://127.0.0.1:25441/' })
    req = requests_session.post('http://127.0.0.1:25441/hwi/api/', data=json.dumps({
        'jsonrpc': '2.0',
        'method': 'enumerate',
        'id': 1,
        'params': {},
        'forwarded_request': True
    }))
    assert { "id": 1, "jsonrpc": "2.0", "result": []} == json.loads(req.content)

def test_calling_method_with_non_existing_parameters():
    requests_session = requests.Session()
    requests_session.headers.update({ 'origin': 'http://127.0.0.1:25441/' })
    req = requests_session.post('http://127.0.0.1:25441/hwi/api/', data=json.dumps({
        'jsonrpc': '2.0',
        'method': 'enumerate',
        'id': 1,
        'params': { 'non_existing_parameter': True },
        'forwarded_request': True
    }))
    assert { 
        "jsonrpc": "2.0",
        "error": { "code": -32000, "message": "Internal error: enumerate() got an unexpected keyword argument 'non_existing_parameter'" },
        "id": 1
    } == json.loads(req.content)

def test_call_not_connected_device():
    requests_session = requests.Session()
    requests_session.headers.update({ 'origin': 'http://127.0.0.1:25441/' })
    req = requests_session.post('http://127.0.0.1:25441/hwi/api/', data=json.dumps({
        'jsonrpc': '2.0',
        'method': 'prompt_pin',
        'id': 1,
        'params': { 'device_type': 'trezor', 'path': '', 'passphrase': '', 'chain': 'test' },
        'forwarded_request': True
    }))
    assert { 
        "jsonrpc": "2.0",
        "error": { "code": -32000, "message": "Internal error: The device could not be found. Please check it is properly connected and try again" },
        "id": 1
    } == json.loads(req.content)

def test_call_prompt_pin_invalid_device():
    requests_session = requests.Session()
    requests_session.headers.update({ 'origin': 'http://127.0.0.1:25441/' })
    req = requests_session.post('http://127.0.0.1:25441/hwi/api/', data=json.dumps({
        'jsonrpc': '2.0',
        'method': 'prompt_pin',
        'id': 1,
        'params': { 'device_type': 'ledger', 'path': '', 'passphrase': '', 'chain': 'test' },
        'forwarded_request': True
    }))
    assert { 
        "jsonrpc": "2.0",
        "error": { "code": -32000, "message": "Internal error: Invalid HWI device type ledger, prompt_pin is only supported for Trezor and Keepkey devices" },
        "id": 1
    } == json.loads(req.content)
