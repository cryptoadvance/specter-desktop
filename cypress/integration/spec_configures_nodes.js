
describe('Configuring nodes', () => {
  
    it('Configures the bitcoin-node in Specter', () => {
      cy.viewport(1200,660)
      cy.visit('/')
      cy.get('#node-switch-icon').click()
      cy.get('[href="/nodes/node/default/"]').first().click()
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
  
    it('Configures the elements-node in Specter', () => {
      cy.viewport(1200,660)
      cy.visit('/')
      cy.get('#node-switch-icon').click()
      cy.get('#btn_new_node').click()
      cy.get('[href="/nodes/new_node/"]').click()
      cy.get('#name').clear()
      cy.get('#name').type("Elements Node")
      cy.get('.slider').click()
      cy.readFile('elmd-conn.json').then((conn) => {
        cy.get('#username').clear()
        cy.get('#username').type("liquid")
        cy.get('#password').clear()
        cy.get('#password').type("wrongPassword") // wrong Password
        cy.get('#host').clear()
        cy.get('#host').type("http://"+conn["host"])
        cy.get('#port').clear()
        cy.get('#port').type(conn["port"])
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

  
    it('Choose Bitcoin Core Node', () => {
        // switch back to bitcoin-node
        cy.viewport(1200,660)
        cy.visit('/')
        cy.get('#node-switch-icon').click()
        cy.get('#default-select-node-form > .item > div').click()
    })   
  
  })