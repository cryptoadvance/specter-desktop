import { showNotification } from '../../src/cryptoadvance/specter/static/helper-modules/common.js'

describe('Unit tests of common JS functions', () => {
    before(() => {
        cy.visit('/')
    })

    it('Test showNotification function', () => {
        // Approach from: https://dzone.com/articles/how-to-execute-javascript-commands-in-cypress
        cy.window().then((win) => {
            win.eval('showNotification("New wallet created", timeout=2000)');
        });
        cy.get('message-box').should('have.text', 'New wallet created')
    })
    
})