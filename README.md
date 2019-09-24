# Specter Desktop

A flask web GUI for Bitcoin Core to use with airgapped hardware wallets

This is the working alpha branch. Random comments, weird pieces of code and comments, not documented, breaking changes etc.

Wait until we merge it to master, then you can use it.

## TODO

- Send transaction:
  - save psbt that is not finished
  - upload file and combine psbt
  - determine who else should sign (just look up pubkeys)
  - show as qr
  - work with coldcard to fix their multisig
- Display cosigners xpubs
- Migration between app versions?

### Later:

- Import wallet from coldcard
- Show addresses QR codes in the PSBT
- Delete wallets (requires access to the wallet folder - can only unload remotely)

### A bit later:

- proper error handling
- run flask server from distribution
- run bitcoind and bitcoin-cli from the distribution
- bitcoin configuration gui

### Nice to have

- control fee
- Tx batching (sendtomany)
- coin control
- rbf
- privacy mode - hide balances and/or menu bar (can be in settings)
- mobile version
- use vue js?
- specter-pi - airgapped bitcoin core for signing on pi

### Far in the future

- remote node over tor - camera requires https, how to solve? (let's encrypt doesn't work)
