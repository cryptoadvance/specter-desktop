
## Wallet Endpoint

This API will return wallet balance details as well as transactions.

**URL** : `/api/v1alpha/wallets/<wallet_alias>`

**Method** : `GET`

**Auth required** : Yes

**Permissions required** : Access to the wallet

### Success Response

**Code** : `200 OK`

**Content examples**

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
