// Note: Currently we only have address labels
describe('Test the labeling of addresses and transactions', () => {
    before(() => {
        Cypress.config('includeShadowDom', true)
        cy.visit('/')
    })

    // Keeps the session cookie alive, Cypress by default clears all cookies before each test
    beforeEach(() => {
        cy.viewport('macbook-13')
        Cypress.Cookies.preserveOnce('session')
    })

    it('Labeling an address on the address overview', () => {
        // Using the ghost wallet
        cy.selectWallet('Ghost wallet')
        cy.get('main').contains('Addresses').click()
        // Checking the correct titles since those are the only orientation for the user right now
        cy.get('[data-cy="edit-label-btn"]').last().should('have.attr', 'title', 'Edit label') // The last element in the array is the first one on the screen ...
        cy.get('[data-cy="label"]').last().should('have.attr', 'title', 'Edit label')
        // Edit the label of the first address
        cy.get('[data-cy="edit-label-btn"]').last().click().type('{selectall}{backspace}').type('Swan withdrawal address') // Not sure why backspace alone is not enough
        cy.get('[data-cy="update-label-btn"]').last().click()
        cy.contains('Swan withdrawal address')
        // Check that the canceling works as expected
        cy.get('[data-cy="edit-label-btn"]').last().click().type('{backspace}'.repeat(6))
        cy.get('[data-cy="cancel-edit-btn"]').last().click()
        cy.contains('Swan withdrawal address')
        // Clicking somewhere should cancel the editing
        cy.get('[data-cy="edit-label-btn"]').last().click().type('{backspace}'.repeat(6))
        cy.get('[data-cy="cancel-edit-btn"]').last().click()
        cy.get('main').click()
        cy.contains('Swan withdrawal address')
    })
})