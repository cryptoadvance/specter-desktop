describe('Test the UI related to a blockchain rescan', () => {
    before(() => {
        Cypress.config('includeShadowDom', true)
    })

    // Keeps the session cookie alive, Cypress by default clears all cookies before each test
    beforeEach(() => {
        cy.visit('/')
        cy.viewport(1200,660)
        Cypress.Cookies.preserveOnce('session')
    })

    it('Go to the rescan section from a fresh wallet', () => {
        // Create a completely fresh wallet which is not receiving funds from the continous mining
        cy.addDevice('Trezor hold', 'Trezor', 'hold_accident')
        cy.addWallet('Fresh wallet', 'Trezor hold', 'segwit', false)
        cy.get('#btn_transactions').click()
        cy.get('#rescan-hint > .btn', { timeout: 6000 }).click()
        cy.get('#blockchain-rescan').should('be.visible')
        // TODO: Do we keep this wallet and this device or teardown?
    })

    it('Check that there is no button for a used wallet', () => {
        // Only works if the ghost wallet was created with funded option
        cy.selectWallet('Ghost wallet')
        cy.get('#rescan-hint > p').should('not.be.visible')
        cy.get('#rescan-hint > .btn').should('not.be.visible')
    })
})