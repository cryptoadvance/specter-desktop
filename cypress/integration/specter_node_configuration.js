describe('Configuring the node in Specter', () => {
    it('Visits specter', () => {
        cy.viewport(1200,660)
        cy.visit('http://localhost:25441')
        cy.get('[href="/settings/"] > img').click()
        cy.get('#username').clear()
        cy.get('#username').type("bitcoin")
        cy.get('#password').clear()
        cy.get('#password').type("wrongPassword") // wrong Password
        cy.get('#host').clear()
        cy.get('#host').type("http://localhost")
        cy.get('#port').clear()
        cy.get('#port').type("18443")
        cy.get('[value="test"]').click()
        cy.get(':nth-child(2) > button > div').should('have.css', 'color', 'rgb(0, 128, 0)') // connectable: green
        cy.get(':nth-child(5) > button > div').should('have.css', 'color', 'rgb(255, 0, 0)') // Credentials: red
        cy.get('#password').clear()
        cy.get('#password').type("secret")
        cy.get('[value="test"]').click()
        cy.get(':nth-child(2) > button > div').should('have.css', 'color', 'rgb(0, 128, 0)') // connectable: green
        cy.get(':nth-child(5) > button > div').should('have.css', 'color', 'rgb(0, 128, 0)') // Credentials: red
        cy.get(':nth-child(8) > button > div').should('have.css', 'color', 'rgb(0, 128, 0)') // Version green
        cy.get(':nth-child(11) > button > div').should('have.css', 'color', 'rgb(0, 128, 0)') // Walletsenabled green
        cy.get('[value="save"]').click()
  })
})