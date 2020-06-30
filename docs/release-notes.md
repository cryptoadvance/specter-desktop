## v0.5.0 June 30, 2020
- Bugfix: Fix compatibility issue with latest Ledger and Trezor firmwares (addresses new BIP143 vulnerability), use HWI 1.1.2 (#178) (@stepansnigirev)
- Bugfix: Don't update explorer if chain is unknown (#174) (@stepansnigirev)
- Bugfix: Fix labels issue with Bitcoin Core v0.20.0 (#160) (@benk10)
- Feature: Multi-user support (#172) (@benk10)
- Feature: Import-export PSBT transactions (#175) (@stepansnigirev)
- Feature: Support HWI display multisig address on device (ColdCard, KeepKey, Trezor) (#179) (@benk10)
- UI: Show installed Specter version and notify on upgrades on the Setting page. (#158) (@k9ert)
- UI: Redesign and improve notifications and error messages (#177, #163) (@stepansnigirev)
- UI: Separate the different areas in the Settings screen into tabs. (#176) (@benk10)
- UI: Add copy button for QR codes (#173) (@stepansnigirev)
- UI: Change confusing “Pending PSBTs” terminology to “Unsigned PSBTs” (#171) (@benk10)
- UI: Improve signing UI (#175, #160) (@stepansnigirev, @benk10)
- UI: Add reject reason to the error on broadcast (#160) (@stepansnigirev)
- UI: New Trezor and Ledger icons (#160) (@stepansnigirev, @benk10)
- UI: Allow selecting device type manually (#160) (@benk10)
- Refactoring: Separate `logic.py` into multiple files (#160) (@benk10)
- Refactoring: Refactor Device, DeviceManager, Wallet, WalletManager classes (#160) (@benk10)
- Refactoring: Modularize supported device types (#160) (@benk10)
- Refactoring: Make devices and wallets accessible to each other (#160) (@benk10)
- Test: Improve test coverage for: Device, DeviceManager, Wallet, WalletManager classes (#160, #170) (@benk10)
- Test: Support multiple Bitcoin Core versions (#161) (@k9ert)
- Docs: Create FAQ doc (#151) (@kkdao)
- Docs: FAQ table of contents auto-generation (#165) (@k9ert)
- Docs: README updates (#164) (@moritzwietersheim)

## v0.4.0 May 31, 2020
- #112 - Mobile friendly UI (@stepansnigirev)
- #130 - Showing transacation details while sending (@benk10)
- #232 - Being able to copy transaction instead of sending via own node (@benk10)
- #139 - User feedback for proper connection to Core in settings menu (@k9ert)
- #140 - Bugfix which blocked the use of Coldcard under certain circumstances  (@benk10)
- #128 - Bugfix how funds get represented  (@benk10)

- A lot of refactorings (especially for template-logic) and tidyups. We also removed some dependencies (@benk10, @stepansnigirev)

## v0.3.0 May 11, 2020
- #104 - QR-Code animations enable to pass more information in smaller chunks (@gorazdko)
- #108 - Renaming and Deleting wallets (@benk10)
- #95 - addresses and utxo-view for better overview of your funds (@benk10)
- #100 - Pending PSBTS for partially sign and sign with others devices much later (@benk10)
- #101 - Support Device passphrases for HWI-wallets (@benk10)
- #40 - coin selection to control which utxo you want to spend (@k9ert)
- #120 - Display Addresses on device (@benk10)
- #127 - Windows support (@stepansnigirev)

## v0.2.0 Mar 27, 2020
- #94 - label addresses to get remember where coins are coming from (@benk10)
- #81 - Optional Authentication with RPC Password (@k9ert)
- Support custom block explorer for all networks (@benk10)

## v0.1.2 Mar 6, 2020
- bugfix-release (#84)

## v0.1.1 Feb 29, 2020
- #80 - Support for compressed PSBT in QR-codes (@stepansnigirev)
- #77 - Use specter-diy to sign via USB (@stepansnigirev)

## v0.1.0 Feb 27, 2020
- #73 - Rescan Blockchain to import older wallets easily (@stepansnigirev)
- Command-line options for server: daemon, ssl-certs and tor

## v0.0.2 Feb 20, 2020
- #69 - First PIP-Release available on [PyPi](https://pypi.org/project/cryptoadvance.specter/#history) (@k9ert)
- #23 - HWI support enables a whole bunch of hardwarewallets to work with specter (@kdmukai)
- #19 - Tor integration (@kdmukai)
- #56 - Support for coldcard (@kdmukai)
- #64 - https support (@stepansnigirev)

## v0.0.1-alpha Sep 28, 2019
Specter Desktop has been started by @stepansnigirev since Aug 30, 2019.
Thank you Stepan :-).
