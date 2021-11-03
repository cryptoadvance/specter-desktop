describe('Send transactions from bitcoin hotwallets', () => {
    it('Creates a single sig bitcoin hotwallet on specter and send transaction', () => {
        cy.viewport(1200,660)
        cy.visit('/')
        // empty so far
        cy.addHotDevice("Hot Device 1","bitcoin")
        cy.get('body').then(($body) => {
            if ($body.text().includes('Test Hot Wallet 1')) {
                cy.get('#wallets_list > .item > svg').click()
                cy.get(':nth-child(6) > .right').click()
                cy.get('#advanced_settings_tab_btn').click()
                cy.get('.card > :nth-child(9) > .btn').click()
            }
        })
        cy.get('#btn_new_wallet').click()
        cy.get('[href="./simple/"]').click()
        cy.get('#hot_device_1').click()
        cy.get('#wallet_name').type("Test Hot Wallet 1")
        cy.get('#keysform > .centered').click()
        cy.get('body').contains("New wallet was created successfully!")
        // Download PDF
        // unfortunately this results in weird effects in cypress run
        //cy.get('#pdf-wallet-download > img').click()
        cy.get('#btn_continue').click()
        //get some funds
        cy.mine2wallet("btc")

        cy.get('#btn_send').click()
        cy.get('#address_0').type("bcrt1qsj30deg0fgzckvlrn5757yk55yajqv6dqx0x7u")
        cy.get('#label_0').type("Burn address")
        cy.get('#send_max_0').click()
        cy.get('#create_psbt_btn').click()
        cy.get('body').contains("Paste signed transaction")
        cy.get('#hot_device_1_tx_sign_btn').click()
        cy.get('#hot_device_1_hot_sign_btn').click()
        cy.get('#hot_enter_passphrase__submit').click()
        cy.get('#broadcast_local_btn').click()
        cy.get('#fullbalance_amount', { timeout: Cypress.env("broadcast_timeout") })
        .should(($div) => {
            const n = parseFloat($div.text())
            expect(n).to.be.equals(0)
        })
    })

    it('Creates a multi sig wallet on specter and send transaction', () => {
        cy.viewport(1200,660)
        cy.visit('/')
        cy.get('body').then(($body) => {
            if ($body.text().includes('Test Multisig Wallet 1')) {
                cy.get('#wallets_list > .item > svg').click()
                cy.get(':nth-child(6) > .right').click()
                cy.get('#advanced_settings_tab_btn').click()
                cy.get('.card > :nth-child(9) > .btn').click()
            }
        })
        cy.get('#btn_new_wallet').click()
        cy.get('[href="./multisig/"]').click()
        cy.get('#hot_device_1').click()
        cy.get('#testdevice_ghost').click()
        cy.get('#submit-device').click()
        cy.get('#wallet_name').type("Test Multisig Wallet 1")

        cy.get('#keysform > .centered').click()
        cy.get('body').contains("New wallet was created successfully!")
        cy.get('#page_overlay_popup_cancel_button').click()
        // Send transaction

        //get some funds
        cy.mine2wallet("btc")
        
        cy.get('#btn_send').click()
        cy.get('#address_0').type("bcrt1qsj30deg0fgzckvlrn5757yk55yajqv6dqx0x7u")
        cy.get('#label_0').type("Burn address")
        cy.get('#send_max_0').click()
        cy.get('#create_psbt_btn').click()
        cy.get('body').contains("Paste signed transaction")
        cy.get('#hot_device_1_tx_sign_btn').click()
        cy.get('#hot_device_1_hot_sign_btn').click()
        cy.get('#hot_enter_passphrase__submit').click()
        cy.get('#broadcast_local_btn').click()
        cy.get('#fullbalance_amount', { timeout: Cypress.env("broadcast_timeout") })
        .should(($div) => {
            const n = parseFloat($div.text())
            expect(n).to.be.equals(0)
        })
    })
})