# Specter API

Specter provides a Rest-API which is, by default, in production deactivated. In order to activate, you need to export a variable like that:
```
export SPECTER_API_ACTIVE=True
```

The Authentication is also necessary if you don't activate any Authentication mechanism.
In order to make reasonable assumptions about how stable a specific endpoint is, we're versioning them via the URL. Currently, all endpoints are preset with `v1alpha` which pretty much don't give you any guarantee.
# Basic Usage

Curl:

```bash
curl -u admin:secret -X GET http://127.0.0.1:25441/api/v1alpha/specter | jq .
```

Python:

```python
import requests
response = requests.get('http://127.0.0.1:25441/api/v1alpha/specter', auth=('admin', 'secret'))
json.loads(response.text)
```

# Endpoints

* [Liveness](./ep_liveness.md): Is specter up and running?
* [Readyness](./ep_readyness.md): Is specter ready to serve requests?
* [Specter](./ep_specter.md): Get details about the instance
* [Specter Full Tx List](./ep_specter_fulltxlist.md)
* [Wallet](./ep_wallets_wallet.md): Details about a specific Wallet
* [Wallet PSBT](./ep_wallets_psbt.md): Listing and creating PSBTs



