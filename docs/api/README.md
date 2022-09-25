# Specter API

Specter provides a Rest-API which is, by default, in production deactivated. In order to activate, you need to export a variable like that:
```
export SPECTER_API_ACTIVE=True
```

The Authentication is also necessary if you don't activate any Authentication mechanism.
In order to make reasonable assumptions about how stable a specific endpoint is, we're versioning them via the URL. Currently, all endpoints are preset with `v1alpha` which pretty much don't give you any guarantee.
## Basic Usage
>Works for the endpoints with `BasicAuthResource`

Curl:

```bash
### Create a token
curl -u admin:password --location --request POST 'http://127.0.0.1:25441/api/v1alpha/token' \
--header 'Content-Type: application/json' \
-d '{
    "jwt_token_description": "Token specter",
    "jwt_token_life": "6 hours"
}'

### Get a token by its id
curl -u admin:secret --location --request GET 'http://127.0.0.1:25441/api/v1alpha/token/<jwt_token_id>' | jq .
```

Python:

```python
### Get a token by its id
import requests
response = requests.get('http://127.0.0.1:25441/api/v1alpha/token/<token_id>', auth=('admin', 'secret'))
json.loads(response.text)
```

## Token Based Usage
>Works for the endpoints with `SecureResource` and `AdminResource`

Curl:

```bash
### Pass the token to get authorized
curl --location --request GET 'http://127.0.0.1:25441/api/v1alpha/specter' \
--header 'Authorization: Bearer <token>' | jq .
```

Python:

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



