# Wallet Creation Guide

## Introduction

Specter wallets are designed to provide a user-friendly interface around Bitcoin Core, focusing on multisignature setups with airgapped signing devices, though they also support single-signature wallets. It's developed to make the interaction with Bitcoin Core more convenient for the users.

## Types of Wallets

### Single-Sig Wallets
- These involve one signing device or hardware wallet generating one seed.
- They are simpler and require only one secure location for seed backup.
- However, they are less secure against phishing attacks as one compromised seed can lead to lost Bitcoin.

### Multi-Sig Wallets
- More secure than single-sig, multisig wallets require two or more signing devices to authorize transactions.
- They offer better security, as one compromised seed doesn't result in immediate loss of funds.
- However, they are more complex to set up and require multiple secure locations for seed backups.

## Step-by-Step Guide for Single-Sig Wallets

1. **Setup and Installation**
   - Download and install the Specter Desktop app from the official GitHub release page.
   - Ensure your system meets the necessary requirements (like Python version, Bitcoin Core version).

2. **Running the App**
   - Start the Specter Desktop app.
   - It should automatically detect Bitcoin Core if it's using a default data folder.
   - If not, set rpcuser and rpcpassword in the Bitcoin Core's bitcoin.conf file or directly in the Specter app settings.

3. **Creating a Wallet**
   - In Specter, navigate to the wallet creation section.
   - Choose the option for a single-signature wallet.
   - Follow the prompts to generate a new seed. This seed is crucial for accessing your funds and should be backed up securely.
   - Configure wallet settings as per your preference.

4. **Backing Up the Wallet**
   - After creating the wallet, make sure to back up the seed securely.
   - Specter recommends storing seeds on steel for long-term durability against elements like fire and water.

5. **Testing the Wallet**
   - It's advisable to test the wallet by sending a small amount of Bitcoin to it and then trying to access these funds using the wallet.

## Backup PDFs

- Specter provides backup PDFs that contain crucial information like (master) public keys and fingerprints.
- These backups do not include the seed itself.
- Keep a copy of the backup PDFs with every seed backup, but ensure they are kept private as they allow anyone to recreate the wallet and see the balance.

## Notes

- Always ensure the safety of your seed phrases and backup information.
- Regularly update the Specter software and your Bitcoin Core node for security and functionality improvements.
- For multisig wallet creation, a separate, more detailed guide is recommended due to its complexity.
