describe('Ghost machine', () => {
    it('Create a DIY device with ghost machine keys and a wallet', () => {
        cy.addDevice('DIY ghost', 'Specter-DIY', 'ghost_machine')
        // addWallet assumes that we have a connection, so let's check for that and establish one if we don't have one
        cy.get('body')
            .then($body => {
                if ($body.find('[data-cy="no-core-connection"]').length) {
                    cy.connect()
                    cy.addWallet('Ghost wallet', 'segwit', 'funded', 'btc', 'singlesig', 'DIY ghost')
                }
                else {
                    cy.addWallet('Ghost wallet', 'segwit', 'funded', 'btc', 'singlesig', 'DIY ghost')
                }
            })
    })
})
