// We are using the ghost machine wallet here, which at this point should be empty
describe('Test the UI related to a blockchain rescan', () => {
    before(() => {
        Cypress.config('includeShadowDom', true)
        cy.visit('/')
    })

    // Keeps the session cookie alive, Cypress by default clears all cookies before each test
    beforeEach(() => {
        cy.viewport(1200,660)
        Cypress.Cookies.preserveOnce('session')
    })

    it('Go to the rescan section from a fresh wallet', () => {
        cy.selectWallet("Wallet ghost")
        cy.get('#btn_transactions').click()
        cy.get('#rescan-hint > p').contains("Is this not a fresh wallet?")
        cy.get('#rescan-hint > .btn').click()
        cy.get('#blockchain-rescan').should('be.visible')
    })

    it('Check that there is no button for a used wallet', () => {
        cy.visit('/')
        cy.mine2wallet("btc")
        cy.get('#rescan-hint > p').should('not.be.visible')
        cy.get('#rescan-hint > .btn').should('not.be.visible')
    })
})