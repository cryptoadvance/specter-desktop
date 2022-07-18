describe('Test adding different devices', () => {
    before(() => {
        cy.viewport(1200,660)
        cy.visit('/')
        Cypress.config('includeShadowDom', true)
    })

    // Keeps the session cookie alive, Cypress by default clears all cookies before each test
    beforeEach(() => {
        Cypress.Cookies.preserveOnce('session')
    })

    it('Electrum device', () => {
        cy.get('#toggle_devices_list').click()
        cy.get('#btn_new_device').click()
        cy.get('#electrum_device_card').click()
        cy.get('#device_name').type("Electron's Electrum Device")
        // Open and close the explainer
        cy.get('#toggle-explainer').find('#drop-icon').click()
        cy.get('#toggle-explainer').find('#drop-icon').click()
        cy.get('#master_pub_key').type("vpub5VGXXixD2pHLFtcKtCF57e8mx2JW6fie8VydXijC8sRKAL4RshgjEmzbmV915NeVB9pd23DVYem6zWM7HXFLNwaffNVHowdD9SJWwESyQhp")
        cy.get('.small-card > .btn').click()
        cy.contains('New device was added successfully!')
        cy.get('#page_overlay_popup_cancel_button').click()
        cy.get('#forget_device').click()
    })
})