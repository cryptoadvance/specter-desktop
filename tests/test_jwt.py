import base64
from importlib.abc import ResourceLoader
import jwt, logging
import uuid
import datetime

# test for jwt enpoints
from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.user import *


def test_token_endpoints(client, empty_data_folder, caplog):
    specter = Specter(data_folder=empty_data_folder, checker_threads=False)
    user = User.from_json(
        user_dict={
            "id": "someuser",
            "username": "someuser",
            "password": hash_password("somepassword"),
            "config": {},
            "is_admin": False,
            "services": None,
            "jwt_tokens": {},
        },
        specter=specter,
    )
    caplog.set_level(logging.DEBUG)

    # unauthorized
    # username and password not entered
    headers = {
        "Authorization": "Basic " + "",
        "Content-type": "application/json",
    }

    # user shouldn't be able to acces the endpoints
    response = client.get("/api/v1alpha/token", follow_redirects=True, headers=headers)
    assert response.status_code == 401
    assert json.loads(response.data)["message"].startswith(
        "The server could not verify that you are authorized to access the URL requested."
    )

    response = client.post(
        "/api/v1alpha/token",
        data="""{"jwt_token_description": "somedescription", "jwt_token_life": "6 minutes"}""",
        follow_redirects=True,
        headers=headers,
    )
    assert response.status_code == 401
    assert json.loads(response.data)["message"].startswith(
        "The server could not verify that you are authorized to access the URL requested."
    )

    # authorized
    headers = {
        "Authorization": "Basic "
        + base64.b64encode(bytes("someuser" + ":" + "somepassword", "ascii")).decode(
            "ascii"
        ),
        "Content-type": "application/json",
    }

    # if token is not created throw an error
    response = client.get("/api/v1alpha/token", follow_redirects=True, headers=headers)
    assert response.status_code == 404
    data = json.loads(response.data)
    assert json.loads(response.data)["message"] == "Tokens does not exist"

    # user creates a token first
    response = client.post(
        "/api/v1alpha/token",
        data="""{"jwt_token_description": "somedescription", "jwt_token_life": "6 minutes"}""",
        follow_redirects=True,
        headers=headers,
    )
    assert response.status_code == 201
    data = json.loads(response.data)
    print(data)
    assert data["message"] == "Token generated"
    assert data["jwt_token_id"]
    assert data["jwt_token"]
    assert data["jwt_token_description"] == "somedescription"
    assert data["jwt_token_life"] == 360

    jwt_token_id = data["jwt_token_id"]

    # testing GET request
    response = client.get("/api/v1alpha/token", follow_redirects=True, headers=headers)
    assert response.status_code == 200
    data = json.loads(response.data)
    assert json.loads(response.data)["message"] == "Tokens exist"
    assert data

    # unauthorized
    # username and password not entered
    headers = {
        "Authorization": "Basic " + "",
        "Content-type": "application/json",
    }

    # user shouldn't be able to acces the endpoints
    response = client.get(
        "/api/v1alpha/token/some_token_id", follow_redirects=True, headers=headers
    )
    assert response.status_code == 401
    assert json.loads(response.data)["message"].startswith(
        "The server could not verify that you are authorized to access the URL requested."
    )

    # authorized
    headers = {
        "Authorization": "Basic "
        + base64.b64encode(bytes("someuser" + ":" + "somepassword", "ascii")).decode(
            "ascii"
        ),
        "Content-type": "application/json",
    }

    # testing GET request to fetch a token by token_id
    response = client.get(
        "/api/v1alpha/token/" + jwt_token_id, follow_redirects=True, headers=headers
    )
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["message"] == "Token exists"
    assert data["jwt_token_description"] == "somedescription"
    assert data["jwt_token_life"] == 360

    # testing DELETE request to delete a token by token_id
    response = client.delete(
        "/api/v1alpha/token/" + jwt_token_id, follow_redirects=True, headers=headers
    )
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["message"] == "Token deleted"

    # retry accessing a deleted token
    response = client.get(
        "/api/v1alpha/token/" + jwt_token_id, follow_redirects=True, headers=headers
    )
    assert response.status_code == 500
    data = json.loads(response.data)
    assert (
        data["message"]
        == "Can't tell you the reason of the issue. Please check the logs"
    )
