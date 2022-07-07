describe('Ghost machine', () => {
    it('Create a DIY device with ghost machine keys and a wallet', () => {
        cy.viewport(1200,660)
        cy.visit('/')
        cy.addDevice('DIY ghost', 'Specter-DIY', 'ghost_machine')
        cy.addWallet('Ghost wallet', null, 'segwit', 'funded', 'btc')
    })
})
