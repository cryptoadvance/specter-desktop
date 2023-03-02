// This spec file assumes that the DIY ghost machine device and wallet from spec_ghost_machine are available
describe('Test QR code signing flow', () => {
    before(() => {
        Cypress.config('includeShadowDom', true)
    })

    it('Message signing with Specter DIY', () => {
        cy.selectWallet('Ghost wallet')
        cy.get('main').contains('Addresses').click()
        // Click on the first address
        cy.contains('td', '#0').siblings().contains('bcrt').click()
        cy.get('#msg-signing-btn').click()
        cy.get('#signing-address').should('have.value', 'bcrt1qvtdx75y4554ngrq6aff3xdqnvjhmct5wck95qs')
        cy.get('#messageDerivationPath').should('have.value', 'm/84h/1h/0h/0/0')
        cy.get('#message').type('The DIY is the best signing device.')
        cy.get('#diy_ghost_qr_sign_msg_btn').click()
        cy.get('[data-cy="scan-qr-code-for-msg-signing-overlay-headline"]').contains('Scan this QR code')
        cy.get('[data-cy="scan-qr-code-for-msg-signing-overlay-close-btn"]').click()
    })

    it('No QR message signing button for a Trezor', () => {
        // Changing the device type to simulate a different device
        cy.changeDeviceType("DIY ghost", "Trezor")
        cy.reload()
        cy.contains("Sign message").click()
        // Only USB signing available for a Trezor device
        cy.contains('Sign message via USB').should('be.visible')
        cy.contains('Sign message via QR code').should('not.exist')
        cy.get('[data-cy="close-msg-signing-overlay-btn"]').click()
        cy.changeDeviceType("DIY ghost", "specter")
    })
    
    it('No message signing with Electrum', () => {
        cy.get('body').then(($body) => {
            if (!$body.text().includes("Electrum Device")) {
                cy.get('#devices_toggle').click()
                cy.get('#btn_new_device').click()
                cy.get('#electrum_device_card').click()
                cy.get('#device_name').type("Electrum Device")
                cy.get('#master_pub_key').type("vpub5VGXXixD2pHLFtcKtCF57e8mx2JW6fie8VydXijC8sRKAL4RshgjEmzbmV915NeVB9pd23DVYem6zWM7HXFLNwaffNVHowdD9SJWwESyQhp")
                cy.get('.small-card > .btn').click()
                cy.contains('Close').click()
            }
        })
        cy.get('body').then(($body) => {
            if (!$body.text().includes("Wallet that cannot sign messages")) {
                cy.get('#btn_new_wallet').click()
                cy.get('[data-cy="singlesig-wallet-btn"]').click()
                cy.get('#electrum_device').click()
                cy.get('#wallet_name').type("Wallet that cannot sign messages")
                cy.get('#keysform').contains("Create wallet").click()
                cy.get('#btn_continue').click()
            }
        })
        cy.selectWallet("Wallet that cannot sign messages")
        cy.get('main').contains('Addresses').click()
        cy.contains('td', '#0').siblings().contains('bcrt').click()
        cy.get('#msg-signing-btn').should('not.exist')
        // Close the address data screen
        cy.get('[data-cy="address-data-screen-close-btn"]').click()

        // Clean up
        cy.deleteWallet("Wallet that cannot sign messages")
        cy.deleteDevice("Electrum Device")
    })
})
