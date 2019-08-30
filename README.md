# Specter Desktop

## DISCLAIMER

This software is **WORK IN PROGRESS and NOT READY TO USE YET**. The master branch is empty **until the first release** of the software with core functionality implemented. At the moment all the code is in the 0.0.0-alpha branch.

## Why?

Bitcoin Core has a very powerful command line interface and a wonderful daemon. Using PSBT and HWI it can also work with hardware wallets, but at the moment it is too linux-way. The same applies to multisignature setups. 

The goal of this project is to make a convenient and user-friendly GUI around Bitcoin Core with a focus on multisignature setup with airgapped hardware wallets.

At the moment we are working on integration of our [Specter-DIY hardware wallet](https://github.com/cryptoadvance/specter-diy) that uses QR codes as a main communication channel, and ColdCard that uses SD cards. Later on we plan to integrate "hot" hardware wallets using HWI tool and [Junktion](https://github.com/justinmoon/junction).

## Current status

Most of the code is there, app should be ready for alpha testing by September 8th.

## A few screenshots

### Adding a new device

![](screenshots/devices.jpg)

![](screenshots/device_keys.jpg)

### Creating a new wallet

![](screenshots/wallets.jpg)

![](screenshots/new_multisig.jpg)

### Wallet interface

![](screenshots/transactions.jpg)

![](screenshots/receive.jpg)

![](screenshots/send.jpg)

### Configuration

![](screenshots/bitcoin-rpc.jpg)