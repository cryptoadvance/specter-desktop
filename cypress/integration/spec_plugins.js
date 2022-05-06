describe('plugins are working', () => {
    
    it('can create the associate button', () => {
        cy.viewport(1200,660)
        cy.visit('/')
        
        // choose address
        cy.get('#test_hot_wallet_1-sidebar-list-item').click()
        cy.get('[href="/wallets/wallet/test_hot_wallet_1/addresses/"]').click()
        cy.get('addresses-table').shadow().find('address-row').eq(0).shadow().find('.explorer-link').eq(0).click({position: 'top'})
        cy.get('address-data').shadow().find('#associate-btn').click()

        cy.contains("Service integration requires an authentication method that includes a password")
        // ok, let's set a password
        cy.get('select').select("passwordonly")
        cy.get('#specter_password_only').type("mySecretPassword")
        cy.get('#submit-btn').click()
        cy.contains("Admin password successfully updated")

        // choose address again
        cy.get('#test_hot_wallet_1-sidebar-list-item').click()
        cy.get('[href="/wallets/wallet/test_hot_wallet_1/addresses/"]').click()
        cy.get('addresses-table').shadow().find('address-row').eq(0).shadow().find('.explorer-link').eq(0).click()
        cy.get('address-data').shadow().find('#associate-btn').click()
        cy.contains("Associating an address with a service will")


    })

    it('deactivates the password protection again', () => {
        cy.viewport(1200,660)
        cy.visit('/')
        cy.get('#password').type("mySecretPassword")
        cy.get('#login-btn').click()
        cy.get('[href="/settings/"] > .svg-white').click()
        cy.get('[href="/settings/auth"]').click()
        cy.get('select').select("none")
        cy.get('#submit-btn').click()
    })

})