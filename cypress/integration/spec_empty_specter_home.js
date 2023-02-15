
describe('Completely empty specter-home', () => {
  before(() => {
    cy.task("clear:specter-home")
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

  it('Setup password protection', () => {
    cy.get('[data-cy="settings-btn"]').click()
    cy.contains('Authentication').click()
    cy.get('[data-cy="authentication-selection"]').select('Password Protection')
    cy.get('[data-cy="admin-password-input"]').type('satoshi')
    cy.get('[data-cy="save-auth-settings-btn"]').click()
    cy.contains('Admin password successfully updated')
  })

  it('Login with password and deactivate password protection again', () => {
    cy.get('[data-cy="admin-password"]').type('satoshi')
    cy.get('[data-cy="login-btn"]').click()
    cy.get('[data-cy="settings-btn"]').click()
    cy.contains('Authentication').click()
    cy.get('[data-cy="authentication-selection"]').select('None')
    cy.get('[data-cy="save-auth-settings-btn"]').click()
  })
})





