describe('Setup Tor and test connection', () => {
    // Tor testing is flaky on cirrus
    if (Cypress.env("CI")) {
        it('Setup Tor', () => {
            cy.viewport(1200,660)
            cy.visit('/settings/tor')

            cy.get('#setup-tor-button').click()

            cy.contains('Setup Tor daemon')
            cy.get('#setup-tor-button').click()

            cy.wait(60000)
            cy.get('#tor-status-text').contains('Status: Running')
            cy.get('[value="test_tor"]').click({ timeout: 60000 })
            cy.contains('Tor requests test completed successfully!')
            cy.get('[value="stoptor"]').click()
            cy.get('#tor-status-text').contains('Status: Down')
            cy.get('[value="starttor"]').click()
            cy.get('#tor-status-text').contains('Status: Running')
            cy.get('[value="uninstalltor"]').click()
            cy.get('#setup-tor-button').click()
        })
    }
})