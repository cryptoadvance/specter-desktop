# Full Transaction List Endpoint

Gives a full tx_list of all transactions. Transactions are cached within specter, so might not be 100% up-to-date.
The result here is highly dependent on the user executing calling this resource as this is not specific to a specific wallet but returns ALL of the TXs of all the wallets.

**URL** : `/api/v1alpha/specter/full_txlist`

**Method** : `GET`

**Auth required** : YES

**Permissions required** : None

### Success Response

**Code** : `200 OK`

**Content examples**


```json
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