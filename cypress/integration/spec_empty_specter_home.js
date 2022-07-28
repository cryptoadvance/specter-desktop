
describe('Completely empty specter-home', () => {
  before(() => {
    cy.task("clear:specter-home")
  })

  it('Click around on the welcome page', () => {
    cy.viewport(1200,660)
    cy.visit('/welcome/about')
    cy.contains('Welcome to Specter Desktop')
    cy.get('#node-switch-icon').click()
    cy.get('[href="/nodes/node/default/"]').first().click()
    cy.contains('Bitcoin Core')
    cy.get('[href="/settings/"] > img').click()
    cy.contains('Backup and Restore')
    cy.get('[href="/settings/auth"]').click()
    cy.contains('Authentication:')
    cy.get('[href="/settings/hwi"]').click()
    cy.contains('Hardware Devices Bridge')
    cy.get('main').scrollTo('top')
    cy.contains('Tor').click({ scrollBehavior: false })
    cy.contains('Tor configurations')
    cy.contains("Choose plugins")
    cy.get('#btn_plugins').click()
    cy.contains("Plugins in Production")
  })
})





