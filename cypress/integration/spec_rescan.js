describe('Test the UI related to a blockchain rescan', () => {
    before(() => {
        Cypress.config('includeShadowDom', true)
    })

    it('Go to the rescan section from a fresh wallet', () => {
        // Create a completely fresh wallet without any funds
        cy.addDevice('Trezor hold', 'Trezor', 'hold_accident')
        cy.addWallet('Fresh wallet', 'segwit', false, true, 'btc', 'singlesig', 'Trezor hold')
        cy.get('#btn_transactions').click()
        cy.get('#go-to-rescan-btn').click()
        cy.get('#blockchain-rescan').should('be.visible')
        // TODO: Do we keep this wallet and this device or teardown?
    })

    it('Check that there is no button for a used wallet', () => {
        // Only works if the ghost wallet was created with funded option
        cy.selectWallet('Ghost wallet')
        cy.get('[data-cy="no-tx-hint"]').should('not.be.visible')
    })
})