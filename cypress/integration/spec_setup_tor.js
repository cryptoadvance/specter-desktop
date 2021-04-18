describe('Setup Tor and test connection', () => {
    it('Setup Tor', () => {
        cy.viewport(1200,660)
        cy.visit('/settings/tor')

        cy.get('#setup-tor-button').click()

        cy.contains('Setup Tor daemon')
        cy.get('#setup-tor-button').click()

        cy.wait(10000)
        cy.get('#tor-status-text').contains('Status: Running')
        cy.get('[value="test_tor"]').click()
        cy.contains('Tor requests test completed successfully!')
        cy.get('[value="stoptor"]').click()
        cy.get('#tor-status-text').contains('Status: Down')
        cy.get('[value="starttor"]').click()
        cy.get('#tor-status-text').contains('Status: Running')
        cy.get('[value="uninstalltor"]').click()
        cy.get('#setup-tor-button').click()
    })
})