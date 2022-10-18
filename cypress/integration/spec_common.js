import { Specter } from '../../src/cryptoadvance/specter/static/helpers.js'

describe('Tests of JS common functions', () => {
    before(() => {
        cy.visit('/')
    })

    it('Unit test of showNotification function', () => {
        // Approach from: https://dzone.com/articles/how-to-execute-javascript-commands-in-cypress
        cy.window().then((win) => {
            win.eval('Specter.common.showNotification("New wallet created", timeout=2000)');
        });
        cy.get('message-box').should('have.text', 'New wallet created')
    })

    it('Integration test of showError function', () => {
        cy.selectWallet('Ghost wallet')
        cy.get('#btn_send').click()
        cy.get('#create_psbt_btn').click()
        cy.get('message-box').contains('You provided no address.')
    })
    
})