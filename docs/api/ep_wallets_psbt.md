# PSBT Endpoint

**URL** : `/v1alpha/wallets/<wallet_alias>/psbt`

## GET

**Method** : `GET`

**Auth required** : Yes

**Permissions required** : Access to the wallet

### Success Response

**Code** : `200 OK`

**Content examples**

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

## POST

**Method** : `POST`

**Auth required** : YES

**Permissions required** : Access to the wallet

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