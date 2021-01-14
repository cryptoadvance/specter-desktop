## Specter API

## Basic Usage

Curl:

```bash
curl -u admin:password -i -X GET http://127.0.0.1:25441/api/v1alpha/specter
```

Python:

```python
response = requests.get('http://127.0.0.1:25441/api/v1alpha/specter', auth=('admin', 'password'))
json.loads(response.text)
```

## Specter Endpoint

This endpoint provides general information from Specter server and Node Status.

#### API Endpoint: [/api/v1alpha/specter](/api/v1alpha/specter)

#### Result

```yaml
{
  "data_folder": "/.specter",
  "file_config":
    {
      "rpc":
        {
          "autodetect": false,
          "datadir": "/Bitcoin/",
          "user": "xxx",
          "password": "xxx",
          "port": "8332",
          "host": "d.onion",
          "protocol": "http",
        },
      "auth": "usernamepassword",
      "explorers": { "main": "", "test": "", "regtest": "", "signet": "" },
      "hwi_bridge_url": "/hwi/api/",
      "uid": "xxxx",
      "unit": "btc",
      "price_check": true,
      "alt_rate": 1,
      "alt_symbol": "BTC",
      "price_provider": "",
      "validate_merkle_proofs": false,
      "new_user_otps": [{ "otp": 0000, "created_at": 0000 }],
    },
  "config":
    {
      "rpc":
        {
          "autodetect": false,
          "datadir": "/Bitcoin/",
          "user": "xxxx",
          "password": "xxx",
          "port": "8332",
          "host": "zx.onion",
          "protocol": "http",
        },
      "auth": "usernamepassword",
      "explorers": { "main": "", "test": "", "regtest": "", "signet": "" },
      "hwi_bridge_url": "/hwi/api/",
      "uid": "0",
      "unit": "btc",
      "price_check": true,
      "alt_rate": 1,
      "alt_symbol": "BTC",
      "price_provider": "",
      "validate_merkle_proofs": false,
      "new_user_otps": [{ "otp": 0, "created_at": 0 }],
    },
  "is_configured": true,
  "is_running": true,
  "info":
    {
      "chain": "main",
      "blocks": 662795,
      "headers": 662795,
      "bestblockhash": "0000000000000000000015b8683d762e12bf4bf4c5b2853d8852621dee259351",
      "difficulty": 18670168558399.59,
      "mediantime": 1608815424,
      "verificationprogress": 0.9999912844409599,
      "initialblockdownload": false,
      "chainwork": "0000000000000000000000000000000000000000173ec34c39fa6707d2741394",
      "size_on_disk": 360603550487,
      "pruned": false,
      "softforks":
        {
          "bip34": { "type": "buried", "active": true, "height": 227931 },
          "bip66": { "type": "buried", "active": true, "height": 363725 },
          "bip65": { "type": "buried", "active": true, "height": 388381 },
          "csv": { "type": "buried", "active": true, "height": 419328 },
          "segwit": { "type": "buried", "active": true, "height": 481824 },
        },
      "warnings": "",
      "mempool_info":
        {
          "loaded": true,
          "size": 25894,
          "bytes": 56391804,
          "usage": 215246768,
          "maxmempool": 300000000,
          "mempoolminfee": 1e-05,
          "minrelaytxfee": 1e-05,
        },
      "uptime": 2425625,
      "blockfilterindex": true,
      "utxorescan": null,
    },
  "network_info":
    {
      "version": 200100,
      "subversion": "/Satoshi:0.20.1/",
      "protocolversion": 70015,
      "localservices": "0000000000000409",
      "localservicesnames": ["NETWORK", "WITNESS", "NETWORK_LIMITED"],
      "localrelay": true,
      "timeoffset": -1,
      "networkactive": true,
      "connections": 10,
      "networks":
        [
          {
            "name": "ipv4",
            "limited": false,
            "reachable": true,
            "proxy": "10.11.5.1:29050",
            "proxy_randomize_credentials": true,
          },
          {
            "name": "ipv6",
            "limited": false,
            "reachable": true,
            "proxy": "10.11.5.1:29050",
            "proxy_randomize_credentials": true,
          },
          {
            "name": "onion",
            "limited": false,
            "reachable": true,
            "proxy": "10.11.5.1:29050",
            "proxy_randomize_credentials": true,
          },
        ],
      "relayfee": 1e-05,
      "incrementalfee": 1e-05,
      "localaddresses": [],
      "warnings": "",
    },
  "device_manager_datafolder": "/.specter/devices",
  "devices_names": ["A", "B", "C", "D"],
  "wallets_names": ["a", "b", "c", "d"],
  "last_update": "...",
  "alias_name": { ... },
  "name_alias": { ... },
  "wallets_alias": [...],
}
```

#### API Endpoint: [/api/v1alpha/full_txlist/](/api/v1alpha/full_txlist/)

#### Result

List of transactions. Each item of list in the format below.

```yaml
[
  {
    "involvesWatchonly": true,
    "address": "bc1...",
    "category": "receive",
    "amount": 0.01,
    "label": "",
    "vout": 0,
    "confirmations": 1,
    "blockhash": "...",
    "blockheight": 1111,
    "blockindex": 1111,
    "blocktime": 1222,
    "txid": "xxxx",
    "walletconflicts": [],
    "time": 16,
    "timereceived": 16,
    "bip125-replaceable": "no",
    "validated_blockhash": "",
    "wallet_alias": "A",
  },
]
```

#### API Endpoint: [/v1alpha/wallet_info/<wallet_alias>/](/v1alpha/wallet_info/<wallet_alias>/)

This API will return wallet balance details as well as transactions
