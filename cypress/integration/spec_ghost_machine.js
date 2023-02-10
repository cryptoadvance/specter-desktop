describe('Ghost machine', () => {
    it('Create a DIY device with ghost machine keys and a wallet', () => {
        cy.addDevice('DIY ghost', 'Specter-DIY', 'ghost_machine')
        // addWallet assumes that we have a connection, so let's check for that and establish one if we don't have one
        cy.get('body')
            .then($body => {
                if ($body.find('[data-cy="no-core-connection"]').length) {
                    cy.connect()
                    cy.addWallet('Ghost wallet', 'segwit', 'funded', true, 'btc', 'singlesig', 'DIY ghost')
                }
                else {
                    cy.addWallet('Ghost wallet', 'segwit', 'funded', true, 'btc', 'singlesig', 'DIY ghost')
                }
            })
    })

    it('Check wallet settings', () => {
        // Wallet info
        cy.selectWallet('Ghost wallet')
        cy.get('#btn_settings').click()
        cy.contains("DIY ghost")
        // Advanced
        cy.get('#btn_settings').click()
        cy.get('#advanced_settings_tab_btn').click()
        cy.contains("Import address labels")
        // Export options
        cy.get('#export_settings_tab_btn').click()
        // Specter JSON
        cy.get('#export_specter_format').click()
        cy.readFile(`./cypress/downloads/Ghost wallet.json`)
        // Backup PDF
        cy.get('#pdf-wallet-download').click()
        cy.readFile(`./cypress/downloads/ghost_wallet_backup.pdf`)
        // Uncle Jim PDF
        cy.get('#pdf-paperxpub-download').click()
        cy.readFile(`./cypress/downloads/ghost_wallet_uj_backup.pdf`)
        // Export to Electrum
        cy.get('[data-cy="show-export-details-overlay-btn"]').click()
        cy.get('#electrum_export').click()
        cy.readFile(`./cypress/downloads/ghost_wallet_electrum.backup`)
    })
})
