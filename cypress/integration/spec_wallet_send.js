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
        cy.get('#recipient_0').find('#address').type("bcrt1qsj30deg0fgzckvlrn5757yk55yajqv6dqx0x7u")
        cy.get('#recipient_0').find('#label').type("Burn address")
        cy.get('#recipient_0').get('#send_max').click()
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
    


    it('Delete recipient ids=0,2. Remaining ids=1,3,4 => Recipients 2,4,5', () => {
        // We need new sats but mine2wallet only works if a wallet is selected
        cy.selectWallet("Test Hot Wallet 1")
        // mine in this wallet only ONCE, otherwise the expected amounts when send-max is clicked are not accurate any more.
        cy.mine2wallet("btc")
        cy.get('#btn_send').click()
        /// The addresses are the first three from DIY ghost
        cy.get('#recipient_0').find('#address').invoke('val', "bcrt1qvtdx75y4554ngrq6aff3xdqnvjhmct5wck95qs")  // will be deleted, so address doesnt matter
        cy.get('#recipient_0').find('#label').type("Recipient 1 to be deleted")
        cy.get('#recipient_0').find('#amount').type(1)
        cy.get('#toggle_advanced').click()
        cy.get('main').scrollTo('bottom')
        
        cy.get('#add-recipient').click()
        cy.get('#recipient_1').find('#address').invoke('val', "bcrt1qgzmq6e3tn67kveryf2je6nd3nv4txef4sl8wre")  // pasting the address is faster than typing
        cy.get('#recipient_1').find('#label').type("Recipient 2")
        cy.get('#recipient_1').find('#amount').type(2)
        cy.get('main').scrollTo('bottom')

        cy.get('#add-recipient').click()
        cy.get('#recipient_2').find('#address').invoke('val', "bcrt1q9mkrhmxcn7rslzfv6lke8859m7ntwudfjqmcx7")  // will be deleted, so address doesnt matter
        cy.get('#recipient_2').find('#label').type("Recipient 3 to be deleted")
        cy.get('#recipient_2').find('#amount').type(3)

        cy.get('#add-recipient').click()
        cy.get('#recipient_3').find('#address').invoke('val', "bcrt1qvtdx75y4554ngrq6aff3xdqnvjhmct5wck95qs")  // pasting the address is faster than typing
        cy.get('#recipient_3').find('#label').type("Recipient 4")
        cy.get('#recipient_3').find('#amount').type(4)

        cy.get('#add-recipient').click()
        cy.get('#recipient_4').find('#address').invoke('val', "bcrt1q9mkrhmxcn7rslzfv6lke8859m7ntwudfjqmcx7")  // pasting the address is faster than typing
        cy.get('#recipient_4').find('#label').type("Recipient 5")
        cy.get('#recipient_4').find('#amount').type(5)
        cy.get('main').scrollTo('bottom')
        // Shadow DOM
        // Check the fee selection
        cy.get('#fee-selection-component').find('.fee_container').find('input#subtract').click()
        cy.get('#fee-selection-component').find('.fee_container').find('input#subtract').invoke('prop', 'checked').should('eq', true)
        // Check whether the recipient number input field is visible (shadow DOM)
        cy.get('#fee-selection-component').find('.fee_container').find('span#subtract_from').should('be.visible')
        // Light DOM
        // Check the values of the hidden inputs in the light DOM which are used for the form
        // Note: Despite identical ids the hidden inputs seem to be fetched first since they are higher up in the DOM
        cy.get('#fee-selection-component').find('#subtract').invoke('attr', 'value').should('eq', 'true')
        // Send max was applied to the third recipient, so the value (identical with the id) should be 2


        cy.get('#recipient_0').find('#remove').click({force: true})   
        cy.get('#recipient_2').find('#remove').click({force: true})  

        // Change recipient number to Recipient 2 (value = id = 1)
        // cy.get('#fee-selection-component').find('.fee_container').find('#subtract_from_recipient_id_select').should('have.length', 3)   // TODO: why does this not work?
        cy.get('#fee-selection-component').find('.fee_container').find('#subtract_from_recipient_id_select').select('Recipient 4')   // select all Recipients, to check that the correct recipients are present
        cy.get('#fee-selection-component').find('.fee_container').find('#subtract_from_recipient_id_select').select('Recipient 5')   // select all Recipients, to check that the correct recipients are present
        cy.get('#fee-selection-component').find('.fee_container').find('#subtract_from_recipient_id_select').select('Recipient 2')   // html select with cypress: https://www.cypress.io/blog/2020/03/20/working-with-select-elements-and-select2-widgets-in-cypress/
        cy.get('#fee-selection-component').find('.fee_container').find('#subtract_from_recipient_id_select').should('have.value', '1');
        cy.get('#fee-selection-component').find('.fee_container').find('#subtract_from_recipient_id_select').find(':selected').should('have.text', 'Recipient 2');

        // The fee should be subtracted from the third recipient
        cy.get('#create_psbt_btn').click()
        var amount = 0

        // Check that the tx was created with the correct amounts
        cy.get('div.tx_info > :nth-child(1) > :nth-child(1)').then(($div) => {  // nth-child is indexed from 1 https://css-tricks.com/almanac/selectors/n/nth-child/
            amount = parseFloat($div.text())
            expect(amount).to.be.lt(2)
            expect(amount).to.be.gt(1)
        })

        cy.get('div.tx_info > :nth-child(2) > :nth-child(1)').then(($div) => {  // nth-child is indexed from 1 https://css-tricks.com/almanac/selectors/n/nth-child/
            amount = parseFloat($div.text())
            expect(amount).to.be.equal(4)
        })

        cy.get('div.tx_info > :nth-child(3) > :nth-child(1)').then(($div) => {  // nth-child is indexed from 1 https://css-tricks.com/almanac/selectors/n/nth-child/
            amount = parseFloat($div.text())
            expect(amount).to.be.equal(5)
        })

        // delete the PSBT so the utxos can be used in the next test again
        cy.get('#deletepsbt_btn').click()
    })

    it('Create a transaction with multiple recipients', () => {
        // We need new sats but mine2wallet only works if a wallet is selected
        cy.selectWallet("Test Hot Wallet 1")
        cy.get('#btn_send').click()
        /// The addresses are the first three from DIY ghost
        cy.get('#recipient_0').find('#address').type("bcrt1qvtdx75y4554ngrq6aff3xdqnvjhmct5wck95qs")
        cy.get('#recipient_0').find('#label').type("Recipient 1")
        cy.get('#recipient_0').find('#amount').type(10)
        cy.get('#toggle_advanced').click()
        cy.get('main').scrollTo('bottom')
        cy.get('#add-recipient').click()
        cy.get('#recipient_1').find('#address').type("bcrt1qgzmq6e3tn67kveryf2je6nd3nv4txef4sl8wre")
        cy.get('#recipient_1').find('#label').type("Recipient 2")
        cy.get('#recipient_1').find('#amount').type(5)
        cy.get('main').scrollTo('bottom')
        cy.get('#add-recipient').click()
        cy.get('#recipient_2').find('#address').type("bcrt1q9mkrhmxcn7rslzfv6lke8859m7ntwudfjqmcx7")
        cy.get('#recipient_2').find('#label').type("Recipient 3")
        cy.get('#recipient_2').find('#send_max').click()
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
        // Send max was applied to the third recipient, so the value (identical with the id) should be 2
        cy.get('#fee-selection-component').find('.fee_container').find('#subtract_from_recipient_id_select').should('have.value', '2');
        // the displayed value of id=2 should be 3
        cy.get('#fee-selection-component').find('.fee_container').find('#subtract_from_recipient_id_select').find(':selected').should('have.text', 'Recipient 3');
        
        // Change where to deduct fee to "Recipient 2" with id = 1
        cy.get('#fee-selection-component').find('.fee_container').find('#subtract_from_recipient_id_select').select('Recipient 2')   // html select with cypress: https://www.cypress.io/blog/2020/03/20/working-with-select-elements-and-select2-widgets-in-cypress/
        cy.get('#fee-selection-component').find('.fee_container').find('#subtract_from_recipient_id_select').should('have.value', '1');
        // the displayed value of id=1 should be 2
        cy.get('#fee-selection-component').find('.fee_container').find('#subtract_from_recipient_id_select').find(':selected').should('have.text', 'Recipient 2');

        // Change it back to "Recipient 3" with id = 2
        cy.get('#recipient_2').find('#send_max').click()

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
        cy.get('#recipient_0').find('#address').type("bcrt1qsj30deg0fgzckvlrn5757yk55yajqv6dqx0x7u")
        cy.get('#recipient_0').find('#label').type("Burn address")
        cy.get('#recipient_0').get('#send_max').click()
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