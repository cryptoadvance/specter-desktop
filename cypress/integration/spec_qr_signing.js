// This spec file assumes that the DIY ghost machine device and wallet from spec_ghost_machine are available
describe('Test QR code signing flow', () => {
    before(() => {
        Cypress.config('includeShadowDom', true)
        cy.visit('/')
    })

    // Keeps the session cookie alive, Cypress by default clears all cookies before each test
    beforeEach(() => {
        cy.viewport(1200,660)
        Cypress.Cookies.preserveOnce('session')
    })

    it('Message signing with Specter DIY', () => {
        cy.get('.side').contains('Wallet ghost').click()
        cy.get('main').contains('Addresses').click()
        // Click on the first address
        cy.contains('td', '#0').siblings().contains('bcrt').click()
        cy.get('#msg-signing-btn').click()
        cy.get('#signing-address').should('have.value', 'bcrt1qvtdx75y4554ngrq6aff3xdqnvjhmct5wck95qs')
        cy.get('#messageDerivationPath').should('have.value', 'm/84h/1h/0h/0/0')
        cy.get('#message').type('The DIY is the best signing device.')
        cy.get('#diy_ghost_qr_sign_msg_btn').click()
        cy.get('#diy_ghost_sign_msg_qr > h2').contains('Scan this QR code')
        cy.get('#page_overlay_popup_cancel_button').click()
    })

    it('QR code signing (currently) only available for DIYs', () => {
        // Changing the device type to simulate a different device
        cy.changeDeviceType("DIY ghost", "Trezor")
        cy.contains("Sign message").click()
        // Only USB signing available for a Trezor device
        cy.get('#diy_ghost_qr_sign_msg_btn').should('not.exist')
        cy.get('#diy_ghost_usb_sign_msg_btn').should('exist')
        cy.get('#page_overlay_popup_cancel_button').click()
        cy.contains("Wallet ghost").click()
        cy.get('main').contains('Addresses').click()
        cy.contains('td', '#0').siblings().contains('bcrt').click()
        cy.get('#msg-signing-btn').should('exist')
        cy.get('#page_overlay_popup_cancel_button').click()
        // Reload fixes issues with sometimes persisting overlays
        cy.reload()
        // Change device type back to DIY
        cy.changeDeviceType("DIY ghost", "specter")
    })

    it('No message signing with Electrum', () => {
        Cypress.on('uncaught:exception', (err, runnable) => {
                     return false
        })
        // returning false here prevents Cypress from
        // failing the test due to this thus far unidentified error:
        // "The following error originated from your application code, not from Cypress.
        // > missing ) after argument list"

        cy.deleteWallet("Wallet that can't sign messages")
        cy.deleteDevice("Electron's Electrum Device")
        cy.get('#toggle_devices_list').click()
        cy.get('#btn_new_device').click()
        cy.get('#electrum_device_card').click()
        cy.get('#device_name').type("Electron's Electrum Device")
        cy.get('#master_pub_key').type("vpub5VGXXixD2pHLFtcKtCF57e8mx2JW6fie8VydXijC8sRKAL4RshgjEmzbmV915NeVB9pd23DVYem6zWM7HXFLNwaffNVHowdD9SJWwESyQhp")
        cy.get('.small-card > .btn').click()
        cy.get('button').contains("Create single key wallet").click()
        cy.get('#wallet_name').type("Wallet that can't sign messages")
        cy.get('#keysform').contains("Create wallet").click()
        cy.get('#btn_continue').click()
        cy.get('main').contains('Addresses').click()
        cy.contains('td', '#0').siblings().contains('bcrt').click()
        cy.get('#msg-signing-btn').should('not.exist')
        // Clean up
        cy.deleteWallet("Wallet that can't sign messages")
        cy.deleteDevice("Electron's Electrum Device")
    })
})