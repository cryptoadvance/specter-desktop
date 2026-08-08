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
    jwt_token = data["jwt_token"]

    # API-created tokens remain registered after the user store is reloaded.
    client.application.specter.user_manager.update()

    # An active, registered token authenticates successfully. The missing wallet
    # is rejected by authorization after authentication has completed.
    token_headers = {"Authorization": "Bearer " + jwt_token}
    response = client.get(
        "/api/v1alpha/wallets/missing/psbt",
        follow_redirects=True,
        headers=token_headers,
    )
    assert response.status_code == 403

    # A signed token must still be registered in the user's active token store.
    unregistered_token = User.generate_jwt_token(
        "someuser", User.generate_token_id(), "unregistered", 360
    )
    response = client.get(
        "/api/v1alpha/wallets/missing/psbt",
        follow_redirects=True,
        headers={"Authorization": "Bearer " + unregistered_token},
    )
    assert response.status_code == 401

    # Missing and non-string token identifiers fail closed.
    expiry = datetime.datetime.utcnow() + datetime.timedelta(seconds=360)
    invalid_payloads = [
        {"username": "someuser", "exp": expiry},
        {"username": "someuser", "jwt_token_id": ["invalid"], "exp": expiry},
    ]
    for invalid_payload in invalid_payloads:
        invalid_token = jwt.encode(
            invalid_payload,
            client.application.config["SECRET_KEY"],
            algorithm="HS256",
        )
        response = client.get(
            "/api/v1alpha/wallets/missing/psbt",
            follow_redirects=True,
            headers={"Authorization": "Bearer " + invalid_token},
        )
        assert response.status_code == 401

    # A different signed token cannot borrow an active token's identifier.
    mismatched_token = User.generate_jwt_token(
        "someuser", jwt_token_id, "mismatched", 360
    )
    response = client.get(
        "/api/v1alpha/wallets/missing/psbt",
        follow_redirects=True,
        headers={"Authorization": "Bearer " + mismatched_token},
    )
    assert response.status_code == 401

    # Malformed persisted records fail closed instead of raising an error.
    user_details = client.application.specter.user_manager.get_user_by_username(
        "someuser"
    )
    stored_token_info = user_details.jwt_tokens[jwt_token_id]
    user_details.jwt_tokens[jwt_token_id] = {}
    user_details.save_info()
    client.application.specter.user_manager.update()
    response = client.get(
        "/api/v1alpha/wallets/missing/psbt",
        follow_redirects=True,
        headers=token_headers,
    )
    assert response.status_code == 401
    user_details = client.application.specter.user_manager.get_user_by_username(
        "someuser"
    )
    user_details.jwt_tokens[jwt_token_id] = stored_token_info
    user_details.save_info()

    # A malformed persisted token container also fails closed after reload.
    stored_tokens = user_details.jwt_tokens
    user_details.jwt_tokens = []
    user_details.save_info()
    client.application.specter.user_manager.update()
    response = client.get(
        "/api/v1alpha/wallets/missing/psbt",
        follow_redirects=True,
        headers=token_headers,
    )
    assert response.status_code == 401
    user_details = client.application.specter.user_manager.get_user_by_username(
        "someuser"
    )
    user_details.jwt_tokens = stored_tokens
    user_details.save_info()
    client.application.specter.user_manager.update()

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

    # Deletion immediately revokes the bearer token.
    response = client.get(
        "/api/v1alpha/wallets/missing/psbt",
        follow_redirects=True,
        headers=token_headers,
    )
    assert response.status_code == 401

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
