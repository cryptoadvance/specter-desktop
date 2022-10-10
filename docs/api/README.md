# Specter API

Specter provides a Rest-API which is, by default, in production deactivated. In order to activate, you need to export a variable like that:
```
export SPECTER_API_ACTIVE=True
```

The Authentication is also necessary even if you don't activate any Authentication mechanism.
In order to make reasonable assumptions about how stable a specific endpoint is, we're versioning them via the URL. Currently, all endpoints are preset with `v1alpha` which pretty much don't give you any guarantee.

The Specter API is using JWT tokens for Authentication. In order to use the API, you need to obtain such a token. Currently, obtaining a token is not possible via the UI but only via a special endpoint, which accepts BasicAuth (as the only endpoint).

## Curl:

Create the token like this:
```bash
curl -u admin:password --location --request POST 'http://127.0.0.1:25441/api/v1alpha/token' \
--header 'Content-Type: application/json' \
-d '{
    "jwt_token_description": "A free description here to know for what the token is used",
    "jwt_token_life": "30 days"
}'
```
As a result, you get a json like this:
```json
{
    "message": "Token generated",
    "jwt_token_id": "4969e9fb-2097-41e7-af53-5e2082a3e4d3",
    "jwt_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VybmFtZSI6ImFkbWluIiwiand0X3Rva2VuX2lkIjoiNDk2OWU5ZmItMjA5Ny00MWU3LWFmNTMtNWUyMDgyYTNlNGQzIiwiand0X3Rva2VuX2Rlc2NyaXB0aW9uIjoiQSBmcmVlIGRlc2NyaXB0aW9uIGhlcmUgdG8ga25vdyBmb3Igd2hhdCB0aGUgdG9rZW4gaXMgdXNlZCIsImV4cCI6MTY5NjU4NDQ0MiwiaWF0IjoxNjY1MDQ4NDQyfQ.S2NIQknkNqoe-u0xA-W8ZxxkDM-I5B8eDCUwLrG-98E",
    "jwt_token_description": "A free description here to know for what the token is used",
    "jwt_token_life": 31536000
}
```

The token will only be shown once. However, apart from the token itself, you can still get the details of a specific token like this:

```bash
curl -s -u admin:secret --location --request GET 'http://127.0.0.1:25441/api/v1alpha/token/4969e9fb-2097-41e7-af53-5e2082a3e4d3' | jq .
```

```json
{
  "message": "Token exists",
  "jwt_token_description": "A free description here to know for what the token is used",
  "jwt_token_life": 2592000,
  "jwt_token_life_remaining": 2591960.19173622,
  "expiry_status": "Valid"
}
```

The `jwt_token_life` value and the other one are expressed in seconds.

In order to use that token, you can e.g. call the specter-endpoint like this:
```bash
curl -s --location --request GET 'http://127.0.0.1:25441/api/v1alpha/specter' \
--header 'Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VybmFtZSI6ImFkbWluIiwiand0X3Rva2VuX2lkIjoiNDk2OWU5ZmItMjA5Ny00MWU3LWFmNTMtNWUyMDgyYTNlNGQzIiwiand0X3Rva2VuX2Rlc2NyaXB0aW9uIjoiQSBmcmVlIGRlc2NyaXB0aW9uIGhlcmUgdG8ga25vdyBmb3Igd2hhdCB0aGUgdG9rZW4gaXMgdXNlZCIsImV4cCI6MTY5NjU4NDQ0MiwiaWF0IjoxNjY1MDQ4NDQyfQ.S2NIQknkNqoe-u0xA-W8ZxxkDM-I5B8eDCUwLrG-98E' | jq .
```
The result would be something like this:

```json
{
  "data_folder": "/home/someuser/.specter",
  "config": {
    "auth": {
      "method": "usernamepassword",
      "password_min_chars": 6,
      "rate_limit": "10",
      "registration_link_timeout": "1"
    },
    [...]
  "wallets_names": [],
  "last_update": "10/06/2022, 11:35:21",
  "alias_name": {},
  "name_alias": {},
  "wallets_alias": []
}
```
## Python

Here is an example of using the API with python. We don't assume that you use BasicAuth via python. Instead of an example of a real token, we use `<token>` and `<token_id>`.

```python
import requests
response = requests.get('http://127.0.0.1:25441/api/v1alpha/token/<token_id>', auth=('admin', 'secret'))
json.loads(response.text)
```


```python
### Pass the token to get authorized
import requests
response = requests.get('http://127.0.0.1:25441/api/v1alpha/specter', headers={'Authorization': 'Bearer <token>'})
json.loads(response.text)
```

## Endpoints

* [Liveness](./ep_liveness.md): Is specter up and running?
* [Readyness](./ep_readyness.md): Is specter ready to serve requests?
* [Specter](./ep_specter.md): Get details about the instance
* [Specter Full Tx List](./ep_specter_fulltxlist.md): Gives a full tx_list of all transactions.
* [Wallet](./ep_wallets_wallet.md): Details about a specific Wallet
* [Wallet PSBT](./ep_wallets_psbt.md): Listing and creating PSBTs
* [JWT Tokens](./ep_jwt_tokens.md): Listing, creating and managing JWT Tokens ]



