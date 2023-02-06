describe('Ghost machine', () => {
    it('Create a DIY device with ghost machine keys and a wallet', () => {
        cy.addDevice('DIY ghost', 'Specter-DIY', 'ghost_machine')
        // addWallet assumes that we have a connection, so let's check for that and establish one if we don't have one
        cy.get('body')
            .then($body => {
                if ($body.find('[data-cy="no-core-connection"]').length) {
                    cy.connect()
                    cy.addWallet('Ghost wallet', 'segwit', false, false, 'btc', 'singlesig', 'DIY ghost')
                }
                else {
                    cy.addWallet('Ghost wallet', 'segwit', false, false, 'btc', 'singlesig', 'DIY ghost')
                }
                cy.get('#pdf-wallet-download').click()
                cy.readFile(`./cypress/downloads/ghost_wallet_backup.pdf`)
                cy.get('[data-cy="new-wallet-added-overlay-close-btn"]').click()
                cy.mine2wallet('btc')
            })
    })

    it('has downloadable artifacts', () => {
        cy.selectWallet('Ghost wallet')
        cy.get('#btn_settings').click()
        cy.contains("DIY ghost")

        cy.get('#btn_settings').click()
        cy.get('#advanced_settings_tab_btn').click()
        cy.contains("Import address labels")

        cy.get('#export_settings_tab_btn').click()
        cy.get('#export_specter_format').click()
        cy.readFile(`./cypress/downloads/Ghost wallet.json`)

        cy.get('#pdf-wallet-download').click()
        cy.readFile(`./cypress/downloads/ghost_wallet_backup.pdf`)

        cy.get('#pdf-paperxpub-download').click()
        cy.readFile(`./cypress/downloads/ghost_wallet_uj_backup.pdf`)

        cy.get('#electrum_export').click()
        cy.readFile(`./cypress/downloads/ghost_wallet_electrum.backup`)
    })
})
