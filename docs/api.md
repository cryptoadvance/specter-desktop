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
curl -u admin:password -X GET http://127.0.0.1:25441/api/v1alpha/specter
```

Python:

```python
response = requests.get('http://127.0.0.1:25441/api/v1alpha/specter', auth=('admin', 'secret'))
json.loads(response.text)
```

# Endpoints


## API Endpoint [/api/healthz/liveness](/api/healthz/liveness) (GET)
This endpoint works as heathz-check. See e.g. here:
https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/

## API Endpoint [/api/healthz/readyness](/api/healthz/readyness) (GET)
This endpoint works as heathz-check. See e.g. here:
https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/

Other than the liveness-endpoint, this also checks whether specter is functional from a user-point of view (not only up and listening for requests).

## API Endpoint [/api/v1alpha/specter](/api/v1alpha/specter) (GET)
This endpoint provides general information from Specter server and Node Status.


### Result

```json
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

## API Endpoint: [/api/v1alpha/specter/full_txlist/](/api/v1alpha/specter/full_txlist/) (GET)

Gives a full tx_list of all transactions. Transactions are cached within specter, so might not be 100% up-to-date.
### Result

List of transactions.

```yaml
[
  {
    "txid": "24defbc6161715abcfe56f89eb43bb49d29232b0117affde5483d49e79778f51",
    "blockhash": "11792c7d30adf202b9210999b79165f1613f46aa833eeefc5aeab827e02d715e",
    "blockheight": 305,
    "time": 1624977105,
    "conflicts": [],
    "bip125-replaceable": "no",
    "hex": "02000000000101bc574fc432597ef4f353178a85d3c03179e71a62ee1f5f63648d81097c4935510000000000feffffff020094357700000000160014c757cba1e8ffe37f0495c6e7488e52994df8012efc59cd1d00000000160014529002f66fae537c9320af29b7e0468c7f5bd1870247304402207a3cecbbe45082d85bdbf90d98459fcac376076d92637169ae9633b5e6c25df9022058c4a925a9e66cc11d161039d923593fd78a8cca663009b68fcbbe2de0d84b510121023c9190534406dd37c320d3a168e78e540c5de83fd179ec49e7a3bae13237b8fc10010000",
    "vsize": 141,
    "category": "receive",
    "address": "bcrt1qcatuhg0gll3h7py4cmn53rjjn9xlsqfwj3zcej",
    "amount": 20,
    "ismine": true,
    "confirmations": 272,
    "label": "Address #0",
    "validated_blockhash": "",
    "wallet_alias": "simple_3"
  },
  {
    ...
  }
]

```

## API Endpoint: [/v1alpha/wallets/<wallet_alias>/(/v1alpha/wallets/<wallet_alias>/) (GET)

This API will return wallet balance details as well as transactions.

### Result

```
{
  "simple_3": {
    "name": "Simple",
    "alias": "simple_3",
    "description": "Single (Segwit)",
    "address_type": "bech32",
    "address": "bcrt1qsqnuk9hulcfta7kj7687favjv66d5e9yy0lr7t",
    "address_index": 1,
    "change_address": "bcrt1qt28v03278lmmxllys89acddp2p5y4zds94944n",
    "change_index": 0,
    "keypool": 300,
    "change_keypool": 300,
    "recv_descriptor": "wpkh([1ef4e492/84h/1h/0h]tpubDC5EUwdy9WWpzqMWKNhVmXdMgMbi4ywxkdysRdNr1MdM4SCfVLbNtsFvzY6WKSuzsaVAitj6FmP6TugPuNT6yKZDLsHrSwMd816TnqX7kuc/0/*)#xp8lv5nr",
    "change_descriptor": "wpkh([1ef4e492/84h/1h/0h]tpubDC5EUwdy9WWpzqMWKNhVmXdMgMbi4ywxkdysRdNr1MdM4SCfVLbNtsFvzY6WKSuzsaVAitj6FmP6TugPuNT6yKZDLsHrSwMd816TnqX7kuc/1/*)#h4z73prm",
    "keys": [
      "Key"
    ],
    "devices": [
      "Trezor"
    ],
    "sigs_required": 1,
    "pending_psbts": {},
    "frozen_utxo": [],
    "fullpath": "/home/kim/.specter_dev/wallets/regtest/simple_3.json",
    "manager": "WalletManager",
    "rpc": "BitcoinRPC",
    "last_block": "338e9672c7f71140a3cb0c42fa9f064083b1b13a379242ba1180cff2355478a5",
    "_addresses": {
      "bcrt1qcatuhg0gll3h7py4cmn53rjjn9xlsqfwj3zcej": {
        "address": "bcrt1qcatuhg0gll3h7py4cmn53rjjn9xlsqfwj3zcej",
        "index": 0,
        "change": false,
        "label": null,
        "used": true
      },
      "bcrt1qsqnuk9hulcfta7kj7687favjv66d5e9yy0lr7t": {
        "address": "bcrt1qsqnuk9hulcfta7kj7687favjv66d5e9yy0lr7t",
        "index": 1,
        "change": false,
        "label": null,
        "used": null
      },
      ...
    },
    "_transactions": {
      "24defbc6161715abcfe56f89eb43bb49d29232b0117affde5483d49e79778f51": {
        "txid": "24defbc6161715abcfe56f89eb43bb49d29232b0117affde5483d49e79778f51",
        "blockheight": 305,
        "blockhash": "11792c7d30adf202b9210999b79165f1613f46aa833eeefc5aeab827e02d715e",
        "time": 1624977105,
        "conflicts": [],
        "bip125-replaceable": "no",
        "hex": "02000000000101bc574fc432597ef4f353178a85d3c03179e71a62ee1f5f63648d81097c4935510000000000feffffff020094357700000000160014c757cba1e8ffe37f0495c6e7488e52994df8012efc59cd1d00000000160014529002f66fae537c9320af29b7e0468c7f5bd1870247304402207a3cecbbe45082d85bdbf90d98459fcac376076d92637169ae9633b5e6c25df9022058c4a925a9e66cc11d161039d923593fd78a8cca663009b68fcbbe2de0d84b510121023c9190534406dd37c320d3a168e78e540c5de83fd179ec49e7a3bae13237b8fc10010000",
        "vsize": 141,
        "category": "receive",
        "address": "bcrt1qcatuhg0gll3h7py4cmn53rjjn9xlsqfwj3zcej",
        "amount": 20,
        "ismine": true
      }
    },
    "info": {
      "walletname": "specter/simple_3",
      "walletversion": 169900,
      "balance": 0,
      "unconfirmed_balance": 0,
      "immature_balance": 0,
      "txcount": 1,
      "keypoololdest": 1624977103,
      "keypoolsize": 300,
      "keypoolsize_hd_internal": 301,
      "paytxfee": 0,
      "private_keys_enabled": false,
      "avoid_reuse": false,
      "scanning": false
    },
    "full_utxo": [
      {
        "txid": "24defbc6161715abcfe56f89eb43bb49d29232b0117affde5483d49e79778f51",
        "vout": 0,
        "address": "bcrt1qcatuhg0gll3h7py4cmn53rjjn9xlsqfwj3zcej",
        "label": "",
        "scriptPubKey": "0014c757cba1e8ffe37f0495c6e7488e52994df8012e",
        "amount": 20,
        "confirmations": 286,
        "spendable": false,
        "solvable": true,
        "desc": "wpkh([1ef4e492/84'/1'/0'/0/0]02d02aeb0a1efc029fce0d61c2c5460fd6cac1ca4609bf4aa0d30d0aa462e7dae5)#3m9y9l9z",
        "safe": true,
        "time": 1624977105,
        "category": "receive",
        "locked": false
      }
    ],
    "balance": {
      "trusted": 20,
      "untrusted_pending": 0,
      "immature": 0,
      "available": {
        "trusted": 20,
        "untrusted_pending": 0,
        "immature": 0
      }
    }
  },
  "txlist": [
    {
      "txid": "24defbc6161715abcfe56f89eb43bb49d29232b0117affde5483d49e79778f51",
      "blockhash": "11792c7d30adf202b9210999b79165f1613f46aa833eeefc5aeab827e02d715e",
      "blockheight": 305,
      "time": 1624977105,
      "conflicts": [],
      "bip125-replaceable": "no",
      "hex": "02000000000101bc574fc432597ef4f353178a85d3c03179e71a62ee1f5f63648d81097c4935510000000000feffffff020094357700000000160014c757cba1e8ffe37f0495c6e7488e52994df8012efc59cd1d00000000160014529002f66fae537c9320af29b7e0468c7f5bd1870247304402207a3cecbbe45082d85bdbf90d98459fcac376076d92637169ae9633b5e6c25df9022058c4a925a9e66cc11d161039d923593fd78a8cca663009b68fcbbe2de0d84b510121023c9190534406dd37c320d3a168e78e540c5de83fd179ec49e7a3bae13237b8fc10010000",
      "vsize": 141,
      "category": "receive",
      "address": "bcrt1qcatuhg0gll3h7py4cmn53rjjn9xlsqfwj3zcej",
      "amount": 20,
      "ismine": true,
      "confirmations": 286,
      "label": "Address #0",
      "validated_blockhash": "",
      "wallet_alias": "simple_3"
    }
  ],
  "scan": null,
  "address_index": 1,
  "utxo": [
    {
      "txid": "24defbc6161715abcfe56f89eb43bb49d29232b0117affde5483d49e79778f51",
      "vout": 0,
      "address": "bcrt1qcatuhg0gll3h7py4cmn53rjjn9xlsqfwj3zcej",
      "label": "",
      "scriptPubKey": "0014c757cba1e8ffe37f0495c6e7488e52994df8012e",
      "amount": 20,
      "confirmations": 286,
      "spendable": false,
      "solvable": true,
      "desc": "wpkh([1ef4e492/84'/1'/0'/0/0]02d02aeb0a1efc029fce0d61c2c5460fd6cac1ca4609bf4aa0d30d0aa462e7dae5)#3m9y9l9z",
      "safe": true,
      "time": 1624977105,
      "category": "receive",
      "locked": false
    }
  ]
}

```

## API Endpoint: [/v1alpha/wallets/<wallet_alias>/psbt](/v1alpha/wallets/<wallet_alias>/psbt) (GET/POST)

### Get Result 

```json
{
  "result": {
    "a49d234652fc811650bfb3e9a29dcc8a902a2155dbbda8ca8cd1af250f547e41": {
      "tx": {
        "txid": "a49d234652fc811650bfb3e9a29dcc8a902a2155dbbda8ca8cd1af250f547e41",
        "hash": "a49d234652fc811650bfb3e9a29dcc8a902a2155dbbda8ca8cd1af250f547e41",
        "version": 2,
        "size": 113,
        "vsize": 113,
        "weight": 452,
        "locktime": 0,
        "vin": [
          {
            "txid": "24defbc6161715abcfe56f89eb43bb49d29232b0117affde5483d49e79778f51",
            "vout": 0,
            "scriptSig": {
              "asm": "",
              "hex": ""
            },
            "sequence": 4294967293
          }
        ],
        "vout": [
          {
            "value": 19.98991399,
            "n": 0,
            "scriptPubKey": {
              "asm": "0 5a8ec7c55e3ff7b37fe481cbdc35a150684a89b0",
              "hex": "00145a8ec7c55e3ff7b37fe481cbdc35a150684a89b0",
              "reqSigs": 1,
              "type": "witness_v0_keyhash",
              "addresses": [
                "bcrt1qt28v03278lmmxllys89acddp2p5y4zds94944n"
              ]
            }
          },
          {
            "value": 0.01,
            "n": 1,
            "scriptPubKey": {
              "asm": "0 c757cba1e8ffe37f0495c6e7488e52994df8012e",
              "hex": "0014c757cba1e8ffe37f0495c6e7488e52994df8012e",
              "reqSigs": 1,
              "type": "witness_v0_keyhash",
              "addresses": [
                "bcrt1qcatuhg0gll3h7py4cmn53rjjn9xlsqfwj3zcej"
              ]
            }
          }
        ]
      },
      "unknown": {},
      "inputs": [
        {
          "witness_utxo": {
            "amount": 20,
            "scriptPubKey": {
              "asm": "0 c757cba1e8ffe37f0495c6e7488e52994df8012e",
              "hex": "0014c757cba1e8ffe37f0495c6e7488e52994df8012e",
              "type": "witness_v0_keyhash",
              "address": "bcrt1qcatuhg0gll3h7py4cmn53rjjn9xlsqfwj3zcej"
            }
          },
          "non_witness_utxo": {
            "txid": "24defbc6161715abcfe56f89eb43bb49d29232b0117affde5483d49e79778f51",
            "hash": "24defbc6161715abcfe56f89eb43bb49d29232b0117affde5483d49e79778f51",
            "version": 2,
            "size": 113,
            "vsize": 113,
            "weight": 452,
            "locktime": 272,
            "vin": [
              {
                "txid": "5135497c09818d64635f1fee621ae77931c0d3858a1753f3f47e5932c44f57bc",
                "vout": 0,
                "scriptSig": {
                  "asm": "",
                  "hex": ""
                },
                "sequence": 4294967294
              }
            ],
            "vout": [
              {
                "value": 20,
                "n": 0,
                "scriptPubKey": {
                  "asm": "0 c757cba1e8ffe37f0495c6e7488e52994df8012e",
                  "hex": "0014c757cba1e8ffe37f0495c6e7488e52994df8012e",
                  "reqSigs": 1,
                  "type": "witness_v0_keyhash",
                  "addresses": [
                    "bcrt1qcatuhg0gll3h7py4cmn53rjjn9xlsqfwj3zcej"
                  ]
                }
              },
              {
                "value": 4.9999718,
                "n": 1,
                "scriptPubKey": {
                  "asm": "0 529002f66fae537c9320af29b7e0468c7f5bd187",
                  "hex": "0014529002f66fae537c9320af29b7e0468c7f5bd187",
                  "reqSigs": 1,
                  "type": "witness_v0_keyhash",
                  "addresses": [
                    "bcrt1q22gq9an04efheyeq4u5m0czx33l4h5v8yfk2m3"
                  ]
                }
              }
            ]
          },
          "bip32_derivs": [
            {
              "pubkey": "02d02aeb0a1efc029fce0d61c2c5460fd6cac1ca4609bf4aa0d30d0aa462e7dae5",
              "master_fingerprint": "1ef4e492",
              "path": "m/84'/1'/0'/0/0"
            }
          ]
        }
      ],
      "outputs": [
        {
          "bip32_derivs": [
            {
              "pubkey": "0270537e123805be08ed48ddcc5961c01607643f42cc11fdcf18f709c40588984a",
              "master_fingerprint": "1ef4e492",
              "path": "m/84'/1'/0'/1/0"
            }
          ]
        },
        {
          "bip32_derivs": [
            {
              "pubkey": "02d02aeb0a1efc029fce0d61c2c5460fd6cac1ca4609bf4aa0d30d0aa462e7dae5",
              "master_fingerprint": "1ef4e492",
              "path": "m/84'/1'/0'/0/0"
            }
          ]
        }
      ],
      "fee": 8.601e-05,
      "fee_rate": "0.00061000",
      "tx_full_size": 141,
      "base64": "cHNidP8BAHECAAAAAVGPd3me1INU3v96EbAyktJJu0PriW/lz6sVFxbG+94kAAAAAAD9////AicwJncAAAAAFgAUWo7HxV4/97N/5IHL3DWhUGhKibBAQg8AAAAAABYAFMdXy6Ho/+N/BJXG50iOUplN+AEuAAAAAAABAHECAAAAAbxXT8QyWX7081MXioXTwDF55xpi7h9fY2SNgQl8STVRAAAAAAD+////AgCUNXcAAAAAFgAUx1fLoej/438ElcbnSI5SmU34AS78Wc0dAAAAABYAFFKQAvZvrlN8kyCvKbfgRox/W9GHEAEAAAEBHwCUNXcAAAAAFgAUx1fLoej/438ElcbnSI5SmU34AS4iBgLQKusKHvwCn84NYcLFRg/WysHKRgm/SqDTDQqkYufa5Rge9OSSVAAAgAEAAIAAAACAAAAAAAAAAAAAIgICcFN+EjgFvgjtSN3MWWHAFgdkP0LMEf3PGPcJxAWImEoYHvTkklQAAIABAACAAAAAgAEAAAAAAAAAACICAtAq6woe/AKfzg1hwsVGD9bKwcpGCb9KoNMNCqRi59rlGB705JJUAACAAQAAgAAAAIAAAAAAAAAAAAA=",
      "amount": [
        0.01
      ],
      "address": [
        "bcrt1qcatuhg0gll3h7py4cmn53rjjn9xlsqfwj3zcej"
      ],
      "time": 1624978624.173007,
      "sigs_count": 0
    }
  }
}

```

### POST


```
curl -u admin:password -X POST http://127.0.0.1:25441/api/v1alpha/wallets/simple_3/psbt \
-H 'Content-Type: application/json' \
-d \
'
        {
            "recipients" : [
                { 
                    "address": "BCRT1qgc6h85z43g3ss2dl5zdrzrp3ef6av4neqcqhh8",
                    "amount": 0.1,
                    "unit": "btc",
                    "label": "someLabel"
                },
                {
                    "address": "bcrt1q3kfetuxpxvujasww6xas94nawklvpz0e52uw8a",
                    "amount": 111211,
                    "unit": "sat",
                    "label": "someOtherLabel"
                }
            ],
            "rbf_tx_id": "",
            "subtract_from": "1",
            "fee_rate": "64",
            "rbf": true
        }'
```

As a result, you get the created PSBT as in the GET-Request.