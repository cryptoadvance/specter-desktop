## v0.6.0 August 4, 2020
- Build: Create `specterd` and `hwibridge` binaries (#258, #271) (@stepansnigirev)
- Devices: [Cobo Valut](https://cobo.com/hardware-wallet/cobo-vault) multisig support (#268) (@stepansnigirev)
- Bugfix: Fix issues and improve performance by removing local caching (#242) (@ben-kaufman)
- Bugfix: Fix installation issue on ARM machines by removing the BIP32 dependency (#259) (@stepansnigirev)
- Performance: RPC calls optimization (#251) (@stepansnigirev)
- Performance: Support multi RPC calls (#243) (@stepansnigirev)
- Feature: Allow sending transactions with multiple recipients (batch transactions) (#252) (@ben-kaufman)
- Feature: Add full backup and restore of all Specter data (#261) (@ben-kaufman)
- Feature: Dynamically start and manage Specter's Tor Hidden Service from the UI (#257) (@ben-kaufman)
- Feature: Allow user to customize the Bitcoin Core data-dir path (#260) (@ben-kaufman)
- Feature: Automatically derive key origin for depth 0 and 1 (#264) (@hodlwave)
- UI: Add Bitcoin Core node info dashboard (#267) (@ben-kaufman)
- UI: New landing page and multiple UI fixes. (#269) (@ben-kaufman)
- UI: Make sidebar wallets and devices lists foldable (#263) (@ben-kaufman)
- UI: New status bar at the top right corner with Setting, Tor, and Logout buttons (#263) (@ben-kaufman)
- UI: Reorganize the wallet Receive tab (#263) (@ben-kaufman)
- UI: Disable devices without keys compatible with chosen wallet type when creating a new wallet (#239) (@stepansnigirev)
- UI: Verify device fingerprint on signing to prevent using the wrong device (#240) (@ben-kaufman)
- UI: Redirect to unsigned PSBTs tab in the wallet Send tab if there are any (#245) (@stepansnigirev)
- UI: Remove upgrade warning when running from source (#241) (@stepansnigirev)
- UI: Remove addresses view and move UTXO view to wallet History page (#242) (@ben-kaufman)
- UI: Add auto-detect Bitcoin Core configurations to the Settings page (#249) (@ben-kaufman)
- UI: Various minor UI improvements (text colors, sizes, spaces, etc.) (#263) (@ben-kaufman)
- UI: Wallet transactions history pagination (#242) (@ben-kaufman)
- UI: Minor ColdCard related improvements (#265) (@ben-kaufman)
- UI: Show note on HWIBridge in HWI detect popup if no device is detected (#266) (@ben-kaufman)
- Refactoring: Create a `qr-scanner` HTML component (#248) (@stepansnigirev)
- Test: Fix test issues due to nondeterministic order of tests (#250) (@k9ert)

## v0.5.5 July 15, 2020
- Devices: Support Electrum wallet as a device (#222) (@stepansnigirev)
- Devices: Support Generic device (usable for any PSBT compatible device not directly supported in Specter) (#221) (@stepansnigirev)
- Bugfix: Fix crash when creating a transaction from wallet with a device with type "Other" (#221) (@stepansnigirev)
- Bugfix: Fix crash when adding keys to an existing device (#221) (@stepansnigirev)
- Bugfix: Show proper error messages when combining PSBTs fails due to server error (#221) (@stepansnigirev)
- Bugfix: Fix wallet behavior when passing a finalized transaction in signing page (#221) (@stepansnigirev)
- Bugfix: Fix signature counter displaying wrong number (#223) (@stepansnigirev)
- Bugfix: Fix PSBT xpubs derivation endian format (#232) (@stepansnigirev)
- Bugfix: Fix crash if Bitcoin Core connection fails (#231) (@stepansnigirev)
- HWI: Prepare support for [Trezor and KeepKey multisig change address verification](https://github.com/bitcoin-core/HWI/pull/355) by adding xpubs data to PSBT sent to HWI (#232) (@stepansnigirev)
- HWI: Add toggle passphrase support for Trezor and KeepKey devices (#234) (@ben-kaufman)
- Feature: Export wallet to allow importing it to Specter or other supported wallet softwares (#220) (@ben-kaufman)
- Feature: Import wallet from Specter or other supported wallet softwares (#225) (@ben-kaufman)
- UI: Improved amount validation in new transaction screen (#221) (@stepansnigirev)

## v0.5.4 July 13, 2020
- Devices: (⚠️ Experimental) Support Bitcoin Core hot wallets (#210) (@ben-kaufman)
- Bugfix: Fix issues with Bitcoin Core calls timing out (#214) (@stepansnigirev)
- Bugfix: Fix issues with non standard keys (#209) (@stepansnigirev)
- Refactoring: Refactor HWI Javascript code (#213) (@stepansnigirev)
- UI: Add new exception handler page to give information about errors (#211) (@stepansnigirev)
- UI: Improve keys table (#218) (@stepansnigirev)

## v0.5.3 July 10, 2020
- Bugfix: Fix potential crashes and issues due to multi-threading race conditions (#205) (@stepansnigirev)
- Bugfix: Fix crash if current Specter version could not be obtained (#202) (@stepansnigirev)
- Bugfix: Fix potential issue with wallets not being properly loaded (#197) (@ben-kaufman)
- Feature: User management panel for admin to manage the list of existing users (in multi-user mode) (#194) (@ben-kaufman)
- UI: Fix notification UI in coin-selection and login screens (#192, #195) (@stepansnigirev)
- UI: Fix some notification messages showing up as error messages (#193) (@ben-kaufman)
- UI: List the devices used in a wallet and the wallets using a certain device (#196) (@ben-kaufman)
- UI: Allow changing device type and warn if non was selected on device setup (#201) (@ben-kaufman)
- UI: Clarify why funds are not available when already used in an unsigned transaction and how to free them (#204) (@ben-kaufman)
- UI: Indicate selected device on the sidebar (#206) (@stepansnigirev)

## v0.5.2 July 5, 2020
- Devices: [Cobo Valut](https://cobo.com/hardware-wallet/cobo-vault) single-sig support (#189) (@stepansnigirev)
- Devices: Support Specter-DIY [v1.2.0](https://github.com/cryptoadvance/specter-diy/releases/tag/v1.2.0) (#188) (@stepansnigirev)
- Bugfix: Fix issue with wallets and devices not being loaded properly (#190) (@ben-kaufman)
- Bugfix: Return button to display address on device for Ledger single-sig wallets (#187) (@stepansnigirev)
- Bugfix: Allow same origin requests to HWI Bridge by default (#185) (@stepansnigirev)
- Bugfix: Fix authentication and styles issues (#181) (@stepansnigirev)
- UI: Improve sidebar UI when Bitcoin Core is not connected or not configured (#184) (@stepansnigirev)

## v0.5.1 (v0.5.0 Hotfix) June 30, 2020
- Bugfix: Fix issue with running Specter after installing from pip (@stepansnigirev)

## v0.5.0 June 30, 2020
- Bugfix: Fix compatibility issue with latest Ledger and Trezor firmwares (addresses new BIP143 vulnerability), use HWI 1.1.2 (#178) (@stepansnigirev)
- Bugfix: Don't update explorer if chain is unknown (#174) (@stepansnigirev)
- Bugfix: Fix labels issue with Bitcoin Core v0.20.0 (#160) (@ben-kaufman)
- Feature: Multi-user support (#172) (@ben-kaufman)
- Feature: Import-export PSBT transactions (#175) (@stepansnigirev)
- Feature: Support HWI display multisig address on device (ColdCard, KeepKey, Trezor) (#179) (@ben-kaufman)
- UI: Show installed Specter version and notify on upgrades on the Setting page. (#158) (@k9ert)
- UI: Redesign and improve notifications and error messages (#177, #163) (@stepansnigirev)
- UI: Separate the different areas in the Settings screen into tabs. (#176) (@ben-kaufman)
- UI: Add copy button for QR codes (#173) (@stepansnigirev)
- UI: Change confusing “Pending PSBTs” terminology to “Unsigned PSBTs” (#171) (@ben-kaufman)
- UI: Improve signing UI (#175, #160) (@stepansnigirev, @ben-kaufman)
- UI: Add reject reason to the error on broadcast (#160) (@stepansnigirev)
- UI: New Trezor and Ledger icons (#160) (@stepansnigirev, @ben-kaufman)
- UI: Allow selecting device type manually (#160) (@ben-kaufman)
- Refactoring: Separate `logic.py` into multiple files (#160) (@ben-kaufman)
- Refactoring: Refactor Device, DeviceManager, Wallet, WalletManager classes (#160) (@ben-kaufman)
- Refactoring: Modularize supported device types (#160) (@ben-kaufman)
- Refactoring: Make devices and wallets accessible to each other (#160) (@ben-kaufman)
- Test: Improve test coverage for: Device, DeviceManager, Wallet, WalletManager classes (#160, #170) (@ben-kaufman)
- Test: Support multiple Bitcoin Core versions (#161) (@k9ert)
- Docs: Create FAQ doc (#151) (@kkdao)
- Docs: FAQ table of contents auto-generation (#165) (@k9ert)
- Docs: README updates (#164) (@moritzwietersheim)

## v0.4.0 May 31, 2020
- #112 - Mobile friendly UI (@stepansnigirev)
- #130 - Showing transacation details while sending (@ben-kaufman)
- #232 - Being able to copy transaction instead of sending via own node (@ben-kaufman)
- #139 - User feedback for proper connection to Core in settings menu (@k9ert)
- #140 - Bugfix which blocked the use of Coldcard under certain circumstances  (@ben-kaufman)
- #128 - Bugfix how funds get represented  (@ben-kaufman)

- A lot of refactorings (especially for template-logic) and tidyups. We also removed some dependencies (@ben-kaufman, @stepansnigirev)

## v0.3.0 May 11, 2020
- #104 - QR-Code animations enable to pass more information in smaller chunks (@gorazdko)
- #108 - Renaming and Deleting wallets (@ben-kaufman)
- #95 - addresses and utxo-view for better overview of your funds (@ben-kaufman)
- #100 - Pending PSBTS for partially sign and sign with others devices much later (@ben-kaufman)
- #101 - Support Device passphrases for HWI-wallets (@ben-kaufman)
- #40 - coin selection to control which utxo you want to spend (@k9ert)
- #120 - Display Addresses on device (@ben-kaufman)
- #127 - Windows support (@stepansnigirev)

## v0.2.0 Mar 27, 2020
- #94 - label addresses to get remember where coins are coming from (@ben-kaufman)
- #81 - Optional Authentication with RPC Password (@k9ert)
- Support custom block explorer for all networks (@ben-kaufman)

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
