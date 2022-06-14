describe('Test sending transactions', () => {
    before(() => {
        Cypress.config('includeShadowDom', true)
    })

    // Keeps the session cookie alive, Cypress by default clears all cookies before each test
    beforeEach(() => {
        cy.viewport(1200,660)
        cy.visit('/')
        Cypress.Cookies.preserveOnce('session')
    })

    it('Send a standard transaction', () => {
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

    it('Create a transaction with multiple recipients', () => {
        // We need new sats but mine2wallet only works if a wallet is selected
        cy.selectWallet("Test Hot Wallet 1")
        cy.mine2wallet("btc")
        cy.get('#btn_send').click()
        /// The addresses are the first three from DIY ghost
        cy.get('#address_0').type("bcrt1qvtdx75y4554ngrq6aff3xdqnvjhmct5wck95qs")
        cy.get('#label_0').type("Recipient 1")
        cy.get('#amount_0').type(10)
        cy.get('#toggle_advanced').click()
        cy.get('main').scrollTo('bottom')
        cy.get('#add-recipient').click()
        cy.get('#address_1').type("bcrt1qgzmq6e3tn67kveryf2je6nd3nv4txef4sl8wre")
        cy.get('#label_1').type("Recipient 2")
        cy.get('#amount_1').type(5)
        cy.get('main').scrollTo('bottom')
        cy.get('#add-recipient').click()
        cy.get('#address_2').type("bcrt1q9mkrhmxcn7rslzfv6lke8859m7ntwudfjqmcx7")
        cy.get('#label_2').type("Recipient 3")
        cy.get('#send_max_2').click()
        cy.get('main').scrollTo('bottom')
        // Shadow DOM
        // Check whether the subtract fees box is ticked
        cy.get('#fee-selection-component').find('.fee_container').find('input#subtract').invoke('prop', 'checked').should('eq', true)
        // Check whether the recipient number input field is visible (shadow DOM)
        cy.get('#fee-selection-component').find('.fee_container').find('span#subtract_from').should('be.visible')
        // Light DOM
        // Check the values of the hidden inputs in the light DOM which are used for the form
        // Note: Despite identical ids the hidden inputs seem to be fetched first since they are higher up in the DOM
        cy.get('#fee-selection-component').find('#subtract').invoke('attr', 'value').should('eq', 'true')
        // Send max was applied to the third recipient, so the value should be 3 
        cy.get('#fee-selection-component').find('#subtract_from_input').invoke('attr', 'value').should('eq', '3') 

        // Change recipient number to 2
        // Note: No easy way to increment / decrement by clicking, see: https://stackoverflow.com/questions/47180137/incrementing-and-decrementing-the-value-of-an-input-type-number-in-cypress
        cy.get('#fee-selection-component').find('.fee_container').find('#subtract_from_input').clear()
        cy.get('#fee-selection-component').find('.fee_container').find('#subtract_from_input').click().type('2{enter}')
        cy.get('#fee-selection-component').find('#subtract_from_input').invoke('attr', 'value').should('eq', '2')

        // Change it back to recipient 3
        cy.get('#send_max_2').click()

        // The fee should be subtracted from the third recipient
        cy.get('#create_psbt_btn').click()
        cy.get('div.tx_info > :nth-child(3) > :nth-child(1)').then(($div) => {
            const amount = parseFloat($div.text())
            expect(amount).to.be.lte(5)
        })
        cy.get('#deletepsbt_btn').click()
        // Clean up (Hot Device 1 is still needed below)
        cy.deleteWallet("Test Hot Wallet 1")
    })

    it('Send a transaction from a multisig wallet', () => {
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
        cy.get('#diy_ghost').click()
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
        // Clean up
        cy.deleteWallet("Test Multisig Wallet 1")
        cy.deleteDevice("Hot Device 1")
    })
})