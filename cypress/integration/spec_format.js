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
        // Need to set the fiat symbol and the exchange rate, 
        // This is saved and derived from the user config in Specter which we don't have (yet?) in the Cypress environment
        cy.window().then((win) => {
            win.Specter.altSymbol = "$"
            win.Specter.altRate = "20000"
        })
        cy.window().its('Specter.unit').should('equal', 'btc')
        cy.window().its('Specter.isTestnet').should('equal', true)
        cy.window().its('Specter.isLiquid').should('equal', false)
        cy.window().its('Specter.priceCheck').should('equal', false)
        cy.window().its('Specter.hideSensitiveInfo').should('equal', false)
        cy.window().its('Specter.altRate').should('equal', "20000")
        cy.window().its('Specter.altSymbol').should('equal', "$")
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
        // Not completely sure why just expect(window.Specter.format.unitLabel(false)).to.equal('tBTC') is not working.
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

    it('Test btcAmountAndUnit', () => {
        cy.window()
            .then((win) => {
                expect(win.Specter.format.btcAmountAndUnit(1.34000935)).to.equal('1.34<span class="thousand-digits-in-btc-amount">000</span><span class="last-digits-in-btc-amount">935</span> <nobr>tBTC</nobr>')
                expect(win.Specter.format.btcAmountAndUnit(1.34000000)).to.equal('1.34<span class="thousand-digits-in-btc-amount"><span class="unselectable transparent-text hidden">0</span><span class="unselectable transparent-text hidden">0</span><span class="unselectable transparent-text hidden">0</span></span><span class="last-digits-in-btc-amount"><span class="unselectable transparent-text hidden">0</span><span class="unselectable transparent-text hidden">0</span><span class="unselectable transparent-text hidden">0</span></span> <nobr>tBTC</nobr>')
            })
    })

    it('Test btcAmount', () => {
        cy.window()
            .then((win) => {
                expect(win.Specter.format.btcAmount(1.34000935)).to.equal('1.34<span class="thousand-digits-in-btc-amount">000</span><span class="last-digits-in-btc-amount">935</span>')
                expect(win.Specter.format.btcAmount(1.34000000)).to.equal('1.34<span class="thousand-digits-in-btc-amount"><span class="unselectable transparent-text hidden">0</span><span class="unselectable transparent-text hidden">0</span><span class="unselectable transparent-text hidden">0</span></span><span class="last-digits-in-btc-amount"><span class="unselectable transparent-text hidden">0</span><span class="unselectable transparent-text hidden">0</span><span class="unselectable transparent-text hidden">0</span></span>')
            })
    })

    it('Test price', () => {
        cy.window()
            .then((win) => {
                // No price check enabled yet
                expect(win.Specter.format.price(5000)).to.equal('')
                win.Specter.priceCheck = true
                expect(win.Specter.format.price(5000, 'BTC', win.Specter.altSymbol, win.Specter.altRate, false)).to.equal('$100,000,000')
                win.Specter.hideSensitiveInfo = true
                expect(win.Specter.format.price(5000)).to.be.equal('#########') // Why is this ##### returned as an array?
                win.Specter.hideSensitiveInfo = false
                expect(win.Specter.format.price(1, 'BTC', "€", "100000", false)).to.equal('100,000€')
            })
    })

})
