
describe('Completely empty specter-home', () => {
  before(() => {
    cy.task("clear:specter-home")
    cy.viewport(1200,660)
    cy.visit('/welcome/about')
  })

  it('Click around on the welcome page', () => {
    cy.contains('Welcome to Specter')
    cy.get('[data-cy="settings-btn"]').click()
    cy.contains('Backup and Restore')
    cy.contains('Authentication').click()
    cy.contains('USB Devices').click()
    cy.contains('Hardware Devices Bridge')
    cy.get('main').scrollTo('top')
    cy.contains('Tor').click()
    cy.contains('Tor configurations')
    cy.get('#btn_plugins').click()
    cy.contains("Plugins in Production")
  })
})





