# Multisig Security Trade-offs

## Receive addresses

When using a standard non-multisig wallet we normally trust that the wallet will verify that a receiving address belongs to our wallet.

This assumption does not always hold true when using a multisig wallet with hardware wallets. With a multisig wallet the wallet must verify not only that an address was generated from its own XPUB but also valid cosigner device XPUBs, not all hardware wallets are able to validate cosigner XPUBs.

Below is a table ([initial source](https://shiftcrypto.ch/blog/how-nearly-all-personal-hardware-wallet-multisig-setups-are-insecure/)) that shows hardware wallet support for validating cosigner XPUBs:

|                                      | BitBox02 | Ledger | Trezor | Coldcard | Specter DIY | Cobo Vault |
|--------------------------------------|----------|--------|--------|----------|-------------|------------|
| Display own xpub on demand           | ✅       | ❌     | ❌     | ✅       | ✅          | ✅         |
| Display cosigner xpubs               | ✅       | ❌     | ✅     | ✅       | ✅          | ✅         |
| Show SLIP-132 formats (`Ypub, Zpub`) | ✅       | ❌     | ❌     | ✅       | ✅          | ✅         |
| Register xpubs inside the device     | ✅       | ❌     | ❌     | ✅       | ✅          | ✅         |

## Backups

To spend from a multisig wallet (for example 2 of 3) you need *all 3* of the XPUBs, not just 2-of-3, in order to construct a valid transaction.

This means that when using a Specter Desktop multisig wallet you should keep a copy of the exported PDF backup file with each of your signing devices.


## See also:

 - https://shiftcrypto.ch/blog/how-nearly-all-personal-hardware-wallet-multisig-setups-are-insecure/
