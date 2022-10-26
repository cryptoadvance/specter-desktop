describe('Tests of JS format functions', () => {
    before(() => {
        cy.visit('/')
    })
    
    it('Test capitalize function', () => {
        cy.window()
            .then((win) => {
                expect(win.Specter.format.capitalize('satoshi')).to.equal('Satoshi') // window is needed here to access Specter object
                expect(win.Specter.format.capitalize('satoshi nakamoto')).to.equal('Satoshi nakamoto')
            })
    })

    it('Test rstrip', () => {
        cy.window()
            .then((win) => {
                expect(win.Specter.format.rstrip('10000000', '0')).to.equal('1')
                expect(win.Specter.format.rstrip('liaaaaaaa', 'a')).to.equal('li')
                expect(win.Specter.format.rstrip('10,', ',')).to.equal('10')
            })
    })

    it('Check the global variables in the Specter window object', () => {
        cy.window().its('Specter.unit').should('equal', 'btc')
        cy.window().its('Specter.isTestnet').should('equal', true)
        cy.window().its('Specter.isLiquid').should('equal', false)
        cy.window().its('Specter.priceCheck').should('equal', false)
        cy.window().its('Specter.hideSensitiveInfo').should('equal', false)
        cy.window().its('Specter.altRate').should('equal', "1")
        cy.window().its('Specter.altSymbol').should('equal', "BTC")
        // Alternative approach
        let targetUnit
        cy.window()
            .then((win) => {
                targetUnit = win.Specter.unit;
            })
            .then(() => {
                expect(targetUnit).to.equal('btc')
            })
    }) 

    it('Test unitLabel', () => {
        // Not completely sure why just expect(window.Specter.format.unitLabel(false)).to.equal('tBTC') is not working
        // It probably has to do with this: https://docs.cypress.io/api/commands/window#Cypress-uses-2-different-windows
        cy.window()
            .then((win) => {
                expect(win.Specter.format.unitLabel(false)).to.equal('tBTC')
                win.Specter.isLiquid = true // This is setting the property across tests, so we need to reset it.
                expect(win.Specter.format.unitLabel(false)).to.equal('tLBTC')
                win.Specter.unit = "sat"
                expect(win.Specter.format.unitLabel(false)).to.equal('tLsat')
                win.Specter.isLiquid = false
                expect(win.Specter.format.unitLabel(false)).to.equal('tsat')
                win.Specter.isTestnet = false
                expect(win.Specter.format.unitLabel(false)).to.equal('sat')
                win.Specter.isLiquid = true
                expect(win.Specter.format.unitLabel(false)).to.equal('Lsat')
                win.Specter.unit = "btc"
                expect(win.Specter.format.unitLabel(false)).to.equal('LBTC')
                win.Specter.isLiquid = false
                expect(win.Specter.format.unitLabel(false)).to.equal('BTC')
                // Reset to testnet again
                win.Specter.isTestnet = true
            })
    })


})
