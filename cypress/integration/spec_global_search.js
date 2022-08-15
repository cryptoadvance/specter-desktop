describe('Test sending transactions', () => {
    before(() => {
        Cypress.config('includeShadowDom', true)
    })

    // Keeps the session cookie alive, Cypress by default clears all cookies before each test
    beforeEach(() => {
        cy.viewport(1200,660)
        cy.visit('/')
        Cypress.Cookies.preserveOnce('session')
    })

    it('Search', () => {
        cy.addHotDevice("Hot Device 1","bitcoin")
        cy.addWallet('Test Hot Wallet 1', 'segwit', 'funded', 'btc', 'singlesig', 'Hot Device 1')
        cy.selectWallet("Test Hot Wallet 1")

        // check the #0 Receive address is found
        cy.get('#global-search-input').type("bcrt1", { force: true })
        cy.get('#global-search-dropdown-content').contains('Receive Address #0')

        // check varias names and alias'
        var searchTerms = ['Test Hot Wallet 1', 'Test_Hot_Wallet_1', "Hot Device 1", "Hot_Device_1"];
        for (var i in searchTerms){
            cy.get('#global-search-input').type(searchTerms[i], { force: true })
            cy.get('#global-search-dropdown-content').contains(searchTerms[i])    
        }

    })
})