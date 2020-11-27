describe('See the Welcome Page', () => {
    it('Visits specter', () => {
      cy.viewport(1200,660)
      cy.visit('http://localhost:25441')
      cy.contains('Welcome to Specter Desktop')
      cy.get('[href="/settings/"] > img').click()
      cy.contains('Bitcoin Core settings - Specter Desktop custom')
      cy.get('.mobile-right').click()
      cy.contains('General settings - Specter Desktop custom')
      cy.get('[href="/settings/auth"]').click()
      cy.contains('Authentication settings - Specter Desktop custom')
      cy.get('.right').click()
      cy.contains('HWI Bridge settings - Specter Desktop custom')
    })
  })


