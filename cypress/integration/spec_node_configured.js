describe('Node Configured', () => {
    it('Creates a wallet on specter', () => {
        cy.viewport(1200,660)
        cy.visit('/')
        cy.addDevice("Testdevice Ghost")
        cy.get('body').then(($body) => {
            if ($body.text().includes('Testwallet Ghost')) {
                cy.contains('Testwallet Ghost').click()
                cy.get('#btn_settings').click({"force": true})
                cy.get('#advanced_settings_tab_btn').click()
                cy.get('#delete_wallet').click()
            }
        })
        cy.get('#btn_new_wallet').click()
        cy.get('[href="./simple/"]').click()
        cy.get('#testdevice_ghost').click()
        cy.get('#wallet_name').type("Testwallet Ghost")
        cy.get('#keysform > .centered').click()
        cy.get('body').contains("New wallet was created successfully!")
        // Download PDF
        // unfortunately this results in weird effects in cypress run
        //cy.get('#pdf-wallet-download > img').click()
        cy.get('#btn_continue').click()
        
        cy.mine2wallet("btc")


    })
})
