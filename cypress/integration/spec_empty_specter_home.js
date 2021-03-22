
describe('Completely empty specter-home', () => {
  beforeEach(() => {
    cy.task("clear:specter-home")
  })
  it('Visits specter and clicks around', () => {
    cy.viewport(1200,660)
    cy.visit('/')
    cy.contains('Welcome to Specter Desktop')
    cy.get('[href="/settings/"] > img').click()
    cy.contains('Bitcoin JSON-RPC')
    cy.get('[href="/settings/general"]').click()
    cy.contains('Backup and Restore')
    cy.get('[href="/settings/auth"]').click()
    cy.contains('Authentication:')
    cy.get('[href="/settings/hwi"]').click()
    cy.contains('Hardware Devices Bridge')
    cy.get('[href="/settings/tor"]').click()
    cy.contains('Tor configurations')
  })

  it('Creates a device in Specter', () => {
    cy.viewport(1200,660)
    cy.visit('/')
    cy.addDevice("Some Device")
  })

  it('Configures the node in Specter', () => {
    cy.viewport(1200,660)
    cy.visit('/')
    cy.get('[href="/settings/"] > img').click()
    cy.get('#datadir-container').then(($datadir) => {
      cy.log($datadir)
      if (!Cypress.dom.isVisible($datadir)) {
        cy.get('.slider').click()
      }
    })
    cy.get('.slider').click()
    cy.get('#username').clear()
    cy.get('#username').type("bitcoin")
    cy.get('#password').clear()
    cy.get('#password').type("wrongPassword") // wrong Password
    cy.get('#host').clear()
    // This is hopefully correct for some longer time. If the connection fails, check the 
    // output of python3 -m cryptoadvance.specter bitcoind (in the CI-output !!) for a better ip-address.
    // AUtomating that is probably simply not worth it.
    cy.readFile('btcd-conn.json').then((conn) => {
      cy.get('#host').type("http://"+conn["host"])
    })
    cy.get('#port').clear()
    cy.get('#port').type("18443")
    cy.get('[value="test"]').click()
    cy.get(':nth-child(2) > button > div').should('have.css', 'color', 'rgb(0, 128, 0)') // connectable: green
    cy.get(':nth-child(5) > button > div').should('have.css', 'color', 'rgb(255, 0, 0)') // Credentials: red
    cy.get('message-box').shadow().find('div.error > a').click()
    cy.get('#password').clear()
    cy.get('#password').type("secret")
    cy.get('[value="test"]').click()
    cy.get(':nth-child(2) > button > div').should('have.css', 'color', 'rgb(0, 128, 0)') // connectable: green
    cy.get(':nth-child(5) > button > div').should('have.css', 'color', 'rgb(0, 128, 0)') // Credentials: green
    cy.get(':nth-child(8) > button > div').should('have.css', 'color', 'rgb(0, 128, 0)') // Version green
    cy.get(':nth-child(11) > button > div').should('have.css', 'color', 'rgb(0, 128, 0)') // Walletsenabled green
    cy.get('message-box').shadow().find('div.main > a').click()
    cy.get('[value="save"]').click()

  })

})


