describe('Node Configured', () => {
    it('Creates a wallet on specter', () => {
        cy.viewport(1200,660)
        cy.visit('http://localhost:25441')
        cy.addDevice("Testdevice Ghost")
        cy.get('body').then(($body) => {
            if ($body.text().includes('Testwallet Ghost')) {
                cy.get('#wallets_list > .item > svg').click()
                cy.get(':nth-child(6) > .right').click()
                cy.get('#advanced_settings_tab_btn').click()
                cy.get('.card > :nth-child(9) > .btn').click()
            }
        })
        cy.get('#btn_new_wallet').click()
        cy.get('[href="./simple/"]').click()
        cy.get('#testdevice_ghost').click()
        cy.get('#keysform > :nth-child(2) > .inline').type("Testwallet Ghost")
        cy.get('#keysform > .centered').click()
        cy.get('body').contains("New wallet was created successfully!")      
    })
})