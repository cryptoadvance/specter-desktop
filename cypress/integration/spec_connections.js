describe('Connecting nodes', () => {
    before(() => {
        Cypress.config('includeShadowDom', true)
    })

    it('Connect with Bitcoin Core node', () => {
      // Starting from the welcome page
      cy.get('[data-cy="core-connection-btn"]').click()
      // Using a wrong RPC password
      cy.get('#name').type('Bitcoin Core')
      cy.get('#username').clear()
      cy.get('#username').type('bitcoin')
      cy.get('#password').clear()
      cy.get('#password').type("wrong")
      cy.get('#host').clear()
      cy.get('#host').type('http://localhost')
      cy.get('#port').clear()
      cy.get('#port').type(15443)
      cy.get('[data-cy="connect-btn"]').click()
      cy.contains('Connection attempt failed')
      cy.contains('Credentials')
      cy.get('#cancel-icon').click()
      // Now connect with the correct password
      cy.get('#password').clear()
      cy.get('#password').type("secret")
      cy.get('[data-cy="connect-btn"]').click()
      cy.contains('New connection saved')
    })
  
    it('Connect with Liquid node', () => {
      cy.isElementsRunning().then((isRunning) => {
        if (isRunning) {
          cy.get('#node-switch-icon').click()
          cy.get('[data-cy="new-connection-btn"]').click()
          cy.get('#name').clear()
          cy.get('#name').type("Liquid")
          cy.get('#username').clear()
          cy.get('#username').type('liquid')
          cy.get('#password').clear()
          cy.get('#password').type('secret')
          cy.get('#host').clear()
          cy.get('#host').type('http://localhost')
          cy.get('#port').clear()
          cy.get('#port').type(8040)
          cy.get('[data-cy="connect-btn"]').click()
        } 
        else {
          cy.log('Test was skipped: Elementsd was not started by the test script.')
        }
      })
    })

    it('Select Bitcoin Core connection', () => {
      cy.get('#node-switch-icon').click()
      cy.contains('Bitcoin Core').click()
      cy.contains('Switched to use Bitcoin Core as connection')
    })
    
    it('Check sync status of Bitcoin Core node', () => {
      cy.intercept("GET", "/nodes/sync_status/", {'fullySynced': false});
      cy.visit('/')
      cy.get('[data-cy="unfinished-sync-indicator"]').should('be.visible')
    })   
  
  })
