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
  "data_folder": "/home/some_user/.specter_dev",
  "config": {
    "auth": {
      "method": "usernamepassword",
      "password_min_chars": 6,
      "rate_limit": "10",
      "registration_link_timeout": "1"
    },
    "explorers": {
      "main": "",
      "test": "",
      "regtest": "",
      "signet": ""
    },
    "explorer_id": {
      "main": "CUSTOM",
      "test": "CUSTOM",
      "regtest": "CUSTOM",
      "signet": "CUSTOM"
    },
    "active_node_alias": "default",
    "proxy_url": "socks5h://localhost:9050",
    "only_tor": false,
    "tor_control_port": "",
    "tor_status": false,
    "hwi_bridge_url": "/hwi/api/",
    "uid": "",
    "unit": "btc",
    "price_check": false,
    "alt_rate": 1,
    "alt_symbol": "BTC",
    "price_provider": "",
    "weight_unit": "oz",
    "validate_merkle_proofs": false,
    "fee_estimator": "mempool",
    "fee_estimator_custom_url": "",
    "hide_sensitive_info": false,
    "bitcoind": false,
    "torrc_password": "_-EEy7RlnCLcUurKd1lCEw"
  },
  "info": {
    "chain": "regtest",
    "blocks": 1421,
    "headers": 1421,
    "bestblockhash": "16ba8e83c41ad4b9e43091543c66482d2e54b68ef9fc407543443247c6722ef4",
    "difficulty": 4.656542373906925e-10,
    "mediantime": 1623851194,
    "verificationprogress": 1,
    "initialblockdownload": false,
    "chainwork": "0000000000000000000000000000000000000000000000000000000000000b1c",
    "size_on_disk": 431663,
    "pruned": false,
    "softforks": {
      "bip34": {
        "type": "buried",
        "active": true,
        "height": 500
      },
      "bip66": {
        "type": "buried",
        "active": true,
        "height": 1251
      },
      "bip65": {
        "type": "buried",
        "active": true,
        "height": 1351
      },
      "csv": {
        "type": "buried",
        "active": true,
        "height": 432
      },
      "segwit": {
        "type": "buried",
        "active": true,
        "height": 0
      },
      "testdummy": {
        "type": "bip9",
        "bip9": {
          "status": "active",
          "start_time": 0,
          "timeout": 9223372036854776000,
          "since": 432
        },
        "height": 432,
        "active": true
      }
    },
    "warnings": "",
    "mempool_info": {
      "loaded": true,
      "size": 0,
      "bytes": 0,
      "usage": 64,
      "maxmempool": 300000000,
      "mempoolminfee": 1e-05,
      "minrelaytxfee": 1e-05
    },
    "uptime": 13607,
    "blockfilterindex": false,
    "utxorescan": null
  },
  "network_info": {
    "version": 200100,
    "subversion": "/Satoshi:0.20.1/",
    "protocolversion": 70015,
    "localservices": "0000000000000409",
    "localservicesnames": [
      "NETWORK",
      "WITNESS",
      "NETWORK_LIMITED"
    ],
    "localrelay": true,
    "timeoffset": 0,
    "networkactive": true,
    "connections": 0,
    "networks": [
      {
        "name": "ipv4",
        "limited": false,
        "reachable": true,
        "proxy": "",
        "proxy_randomize_credentials": false
      },
      {
        "name": "ipv6",
        "limited": false,
        "reachable": true,
        "proxy": "",
        "proxy_randomize_credentials": false
      },
      {
        "name": "onion",
        "limited": true,
        "reachable": false,
        "proxy": "",
        "proxy_randomize_credentials": false
      }
    ],
    "relayfee": 1e-05,
    "incrementalfee": 1e-05,
    "localaddresses": [
      {
        "address": "2a02:810d:d00:7700:233e:a7e:ded8:f2da",
        "port": 18442,
        "score": 1
      },
      {
        "address": "2a02:810d:d00:7700:6534:73c3:85f0:d258",
        "port": 18442,
        "score": 1
      }
    ],
    "warnings": ""
  },
  "device_manager_datafolder": "/home/some_user/.specter_dev/devices",
  "devices_names": [
    "MyColdcard"
  ],
  "wallets_names": [
    "MyColdcard"
  ],
  "last_update": "06/16/2021, 15:48:04",
  "alias_name": {
    "mycoldcard": "MyColdcard"
  },
  "name_alias": {
    "MyColdcard": "mycoldcard"
  },
  "wallets_alias": [
    "mycoldcard"
  ]
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
