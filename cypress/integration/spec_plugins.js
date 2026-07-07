describe('Test plugins', () => {
    before(() => {
        Cypress.config('includeShadowDom', true)
    })

    it('Associate an address with a service', () => {
        // choose address
        cy.selectWallet("Ghost wallet")
        cy.get('main').contains('Addresses').click()
         // Click on the first address
        cy.contains('td', '#0').siblings().contains('bcrt').click()
        cy.get('[data-cy="associate-address-with-service-btn"]').click()
        cy.contains("Service integration requires an authentication method that includes a password")
        // OK, let's set a password
        cy.get('select').select("passwordonly")
        cy.get('#specter_password_only').type("mySecretPassword")
        cy.get('#submit-btn').click()
        cy.contains("Admin password successfully updated")

        // Choose address again
        cy.selectWallet("Ghost wallet")
        cy.get('main').contains('Addresses').click()
        cy.contains('td', '#0').siblings().contains('bcrt').click()
        cy.get('#associate-btn').click()
        cy.contains("Associate Address with Service")
    })

    it('Deactivate password protection', () => {
        cy.get('body').then(($body) => {
            // Cypress 13 keeps browser context when testIsolation is disabled for
            // this stateful suite. If the session cookie survived from the
            // previous test, we are already logged in and can go straight to
            // settings; otherwise log in first.
            if ($body.find('#password').length) {
                cy.get('#password').type("mySecretPassword")
                cy.get('#login-btn').click()
            }
        })
        cy.get('[data-cy="settings-btn"]').click()
        cy.get('[href="/settings/auth"]').click()
        cy.get('select').select("none")
        cy.get('#submit-btn').click()
    })

})