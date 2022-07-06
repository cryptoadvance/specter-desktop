describe('Ghost machine', () => {
    it('Create a DIY device with ghost machine keys and a wallet', () => {
        cy.viewport(1200,660)
        cy.visit('/')
        // addDevice is creating a DIY device with ghost machine keys
        cy.addDevice("DIY ghost")
        cy.get('body').then(($body) => {
            if ($body.text().includes('Wallet ghost')) {
                cy.contains('Wallet ghost').click()
                cy.get('#btn_settings').click({"force": true})
                cy.get('#advanced_settings_tab_btn').click()
                cy.get('#delete_wallet').click()
            }
        })
        cy.get('#btn_new_wallet').click()
        cy.get('[href="./simple/"]').click()
        cy.get('#diy_ghost').click()
        cy.get('#wallet_name').type("Wallet ghost")
        cy.get('#keysform > .centered').click()
        cy.get('body').contains("New wallet was created successfully!")
        // Download PDF
        // unfortunately this results in weird effects in cypress run
        //cy.get('#pdf-wallet-download > img').click()
        cy.get('#btn_continue').click()
    })
})
