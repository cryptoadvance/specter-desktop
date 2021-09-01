
describe('Completely empty specter-home', () => {
  beforeEach(() => {
    cy.task("clear:specter-home")
  })
  it('Visits specter and clicks around', () => {
    cy.viewport(1200,660)
    cy.visit('/')
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
    // Hidden in Cypress behind the price 
    // cy.get('[href="/settings/tor"]').click()
    // cy.contains('Tor configurations')
  })

  it('Creates a device in Specter', () => {
    cy.viewport(1200,660)
    cy.visit('/')
    cy.addDevice("Some Device")
  })

  it('Dummytest to enforce remove of device', () => {
    cy.viewport(1200,660)
    cy.visit('/')
  })
})




