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
        cy.contains("Associating an address with a service will")
    })

    it('Deactivate password protection', () => {
        // This flow only works if we don't keep the session alive! So, no Cypress.Cookies.preserveOnce('session') in beforeEach().
        cy.get('#password').type("mySecretPassword")
        cy.get('#login-btn').click()
        cy.get('[data-cy="settings-btn"]').click()
        cy.get('[href="/settings/auth"]').click()
        cy.get('select').select("none")
        cy.get('#submit-btn').click()
    })

})