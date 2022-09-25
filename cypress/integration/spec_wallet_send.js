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
        cy.addHotDevice("Hot Device 1","bitcoin")
        cy.addWallet('Test Hot Wallet 1', 'segwit', 'funded', 'btc', 'singlesig', 'Hot Device 1')
        cy.selectWallet("Test Hot Wallet 1")
        cy.get('#btn_send').click()
        cy.get('#recipient_0').find('#address').type("bcrt1qsj30deg0fgzckvlrn5757yk55yajqv6dqx0x7u", { force: true })
        cy.get('#recipient_0').find('#label').type("Burn address", { force: true })
        cy.get('#recipient_0').get('#send_max').click()
        cy.get('#create_psbt_btn').click()
        cy.get('body').contains("Paste signed transaction")
        cy.get('#hot_device_1_tx_sign_btn').click()
        cy.get('#hot_device_1_hot_sign_btn').click()
        cy.get('#hot_enter_passphrase__submit').click()
        cy.get('#broadcast_local_btn').click()
        cy.get('#amount_total', { timeout: Cypress.env("broadcast_timeout") })
        .should(($div) => {
            const n = parseFloat($div.text())
            expect(n).to.be.equals(0)
        })
    })

    // Skipped for now, will only work reliably once the the Cypress tests run without mining loop
    it('Open up transaction details', () => {
        cy.selectWallet("Test Hot Wallet 1")
        cy.get('#btn_transactions').click()
        // Click on the txid in the first row
        cy.get('tbody.tx-tbody').find('tr').eq(0).find('#column-txid').find('.explorer-link').click()
        cy.get('.tx-data-info').contains('Input #0')
        cy.get('.tx-data-info').contains('Transaction id:')
        cy.get('.tx-data-info').contains('Output index:') // Not sure whether it is always 1 - output ordering is random in Core ...
        cy.get('.tx-data-info').contains('Address #0')
        cy.get('.tx-data-info').find('.tx_info').eq(0).contains('Value: 20.00000000 tBTC')
        cy.get('.tx-data-info').contains('Output #0')
        cy.get('.tx-data-info').contains('Burn address') 
        cy.get('.tx-data-info').find('.tx_info').eq(1).contains('Value: 19.99999890 tBTC')   // Fees should always be the same
        cy.get('#page_overlay_popup_cancel_button').click()
        // Change to sats and check amounts and units
        cy.get('[href="/settings/"]').click()
        cy.get('[name="unit"]').select('sats')
        cy.contains('Save').click()
        cy.selectWallet("Test Hot Wallet 1")
        cy.get('#btn_transactions').click()
        cy.get('tbody.tx-tbody').find('tr').eq(0).find('#column-txid').find('.explorer-link').click()
        cy.get('.tx-data-info').contains('Value: 2,000,000,000 tsat')
        cy.get('.tx-data-info').contains('Value: 1,999,999,890 tsat')
        cy.get('#page_overlay_popup_cancel_button').click()
        // Change back to btc
        cy.get('[href="/settings/"]').click()
        cy.get('[name="unit"]').select('BTC')
        cy.contains('Save').click()
    })

    it('Adding and deleting recipients', () => {
        // We need new sats but mine2wallet only works if a wallet is selected
        cy.selectWallet("Test Hot Wallet 1")
        cy.mine2wallet("btc")
        cy.get('#btn_send').click()

        // The addresses are the first 5 from DIY ghost
        cy.get('#recipient_0').find('#address').invoke('val', "bcrt1qvtdx75y4554ngrq6aff3xdqnvjhmct5wck95qs")  // will be deleted, so address doesnt matter
        cy.get('#recipient_0').find('#label').type("Recipient 1 to be deleted", { force: true })
        cy.get('#recipient_0').find('#amount').type(1, { force: true })
        cy.get('main').scrollTo('bottom')

        // Adding 4 more recipients
        cy.get('#add-recipient').click()
        cy.get('#recipient_1').find('#address').invoke('val', "bcrt1qgzmq6e3tn67kveryf2je6nd3nv4txef4sl8wre")  // pasting the address is faster than typing
        cy.get('#recipient_1').find('#label').type("Recipient 2", { force: true })
        cy.get('#recipient_1').find('#amount').type(2, { force: true })
        cy.get('main').scrollTo('bottom')

        cy.get('#add-recipient').click()
        cy.get('#recipient_2').find('#address').invoke('val', "bcrt1q9mkrhmxcn7rslzfv6lke8859m7ntwudfjqmcx7")  // will be deleted, so address doesnt matter
        cy.get('#recipient_2').find('#label').type("Recipient 3 to be deleted", { force: true })
        cy.get('#recipient_2').find('#amount').type(3, { force: true })

        cy.get('#add-recipient').click()
        cy.get('#recipient_3').find('#address').invoke('val', "bcrt1q4gs9fsf8fh4s4s8w39hxtupafm2q047fytmnxp")  // pasting the address is faster than typing
        cy.get('#recipient_3').find('#label').type("Recipient 4", { force: true })
        cy.get('#recipient_3').find('#amount').type(4, { force: true })

        cy.get('#add-recipient').click()
        cy.get('#recipient_4').find('#address').invoke('val', "bcrt1q4e8p7x6n7uhtthtelhv3mle52vsc4pqre7ddwm")  // pasting the address is faster than typing
        cy.get('#recipient_4').find('#label').type("Recipient 5", { force: true })
        cy.get('#recipient_4').find('#amount').type(5, { force: true })
        cy.get('main').scrollTo('bottom')
        
        // Check the fee selection
        cy.get('#toggle_advanced').click()
        cy.get('#fee-selection-component').find('.fee_container').find('input#subtract').click()
        cy.get('#fee-selection-component').find('.fee_container').find('input#subtract').invoke('prop', 'checked').should('eq', true)

        // Check whether the recipient number select field is visible
        cy.get('#fee-selection-component').find('.fee_container').find('span#subtract_from').should('be.visible')

        // Check the values of the hidden inputs in the light DOM which are used for the form
        // Note: Despite identical ids the hidden inputs seem to be fetched first since they are higher up in the DOM
        cy.get('#fee-selection-component').find('#subtract').invoke('attr', 'value').should('eq', 'true')

        // Remove two recipients
        cy.get('#recipient_0').find('#remove').click({ force: true })   
        cy.get('#recipient_2').find('#remove').click({ force: true })  

        // Select different recipients to subtract the fees from
        cy.get('#fee-selection-component').find('.fee_container').find('#subtract_from_recipient_id_select').select('Recipient 4') // html select with cypress: https://www.cypress.io/blog/2020/03/20/working-with-select-elements-and-select2-widgets-in-cypress/
        cy.get('#fee-selection-component').find('.fee_container').find('#subtract_from_recipient_id_select').select('Recipient 5')  
        cy.get('#fee-selection-component').find('.fee_container').find('#subtract_from_recipient_id_select').select('Recipient 2')   
        cy.get('#fee-selection-component').find('.fee_container').find('#subtract_from_recipient_id_select').should('have.value', '1');
        cy.get('#fee-selection-component').find('.fee_container').find('#subtract_from_recipient_id_select').find(':selected').should('have.text', 'Recipient 2');

        cy.get('#create_psbt_btn').click()
        var amount = 0

        // The fee should be subtracted from recipient 2, so the amount should be less than 2
        cy.get('div.tx_info > :nth-child(1) > :nth-child(1)').then(($div) => {  // nth-child is indexed from 1 https://css-tricks.com/almanac/selectors/n/nth-child/
            amount = parseFloat($div.text())
            expect(amount).to.be.lt(2)
            expect(amount).to.be.gt(1)
        })
        cy.get('div.tx_info > :nth-child(2) > :nth-child(1)').then(($div) => {
            amount = parseFloat($div.text())
            expect(amount).to.be.equal(4)
        })
        cy.get('div.tx_info > :nth-child(3) > :nth-child(1)').then(($div) => {
            amount = parseFloat($div.text())
            expect(amount).to.be.equal(5)
        })

        // Delete the PSBT so the utxos can be used in the next test again
        cy.get('#deletepsbt_btn').click()
    })

    it('Create a transaction with multiple recipients and use send max', () => {
        cy.selectWallet("Test Hot Wallet 1")
        cy.get('#btn_send').click()
        /// The addresses are the first three from DIY ghost
        cy.get('#recipient_0').find('#address').type("bcrt1qvtdx75y4554ngrq6aff3xdqnvjhmct5wck95qs", { force: true })
        cy.get('#recipient_0').find('#label').type("Recipient 1", { force: true })
        cy.get('#recipient_0').find('#amount').type(10, { force: true })
        cy.get('main').scrollTo('bottom')
        cy.get('#add-recipient').click()
        cy.get('#recipient_1').find('#address').type("bcrt1qgzmq6e3tn67kveryf2je6nd3nv4txef4sl8wre", { force: true })
        cy.get('#recipient_1').find('#label').type("Recipient 2", { force: true })
        cy.get('#recipient_1').find('#amount').type(5, { force: true })
        cy.get('main').scrollTo('bottom')
        cy.get('#add-recipient').click()
        cy.get('#recipient_2').find('#address').type("bcrt1q9mkrhmxcn7rslzfv6lke8859m7ntwudfjqmcx7", { force: true })
        cy.get('#recipient_2').find('#label').type("Recipient 3", { force: true })
        // Using send max
        cy.get('#recipient_2').find('#send_max').click()
        cy.get('main').scrollTo('bottom')
     
        // Check whether the subtract fees box is ticked (we used send max)
        cy.get('#toggle_advanced').click()
        cy.get('#fee-selection-component').find('.fee_container').find('input#subtract').invoke('prop', 'checked').should('eq', true)
        
        // Check whether the recipient number input field is visible
        cy.get('#fee-selection-component').find('.fee_container').find('span#subtract_from').should('be.visible')
        
        // Check the values of the hidden inputs in the light DOM which are used for the form
        // Note: Despite identical ids the hidden inputs seem to be fetched first since they are higher up in the DOM
        cy.get('#fee-selection-component').find('#subtract').invoke('attr', 'value').should('eq', 'true')
        
        // Check whether send max set subtract_from to Recipient 3
        cy.get('#fee-selection-component').find('.fee_container').find('#subtract_from_recipient_id_select').should('have.value', '2');
        cy.get('#fee-selection-component').find('.fee_container').find('#subtract_from_recipient_id_select').find(':selected').should('have.text', 'Recipient 3');
        
        // Select Recipient 2 to subract the fee from
        cy.get('#fee-selection-component').find('.fee_container').find('#subtract_from_recipient_id_select').select('Recipient 2')
        cy.get('#fee-selection-component').find('.fee_container').find('#subtract_from_recipient_id_select').should('have.value', '1');
        cy.get('#fee-selection-component').find('.fee_container').find('#subtract_from_recipient_id_select').find(':selected').should('have.text', 'Recipient 2');

        // Change it back to Recipient 3
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

    it('No remove button if there is only one recipient', () => {
        cy.selectWallet("Ghost wallet")
        cy.get('#btn_send').click()
        // No remove button when the send dialog is started with only one recipient
        cy.get('#recipient_0').find('#remove').should('not.be.visible')
        cy.get('#add-recipient').click()
        // Now both remove buttons should be visible
        cy.get('#recipient_0').find('#remove').should('be.visible')
        cy.get('#recipient_1').find('#remove').should('be.visible')
        // Remove button should disappear again if only one recipient (here: Recipient 3) remains 
        cy.get('#add-recipient').click()
        cy.get('#recipient_0').find('#remove').click({ force: true })
        cy.get('#recipient_1').find('#remove').click({ force: true })
        cy.get('#recipient_2').find('#remove').should('not.be.visible')
    })

    it('Use an address belonging to the wallet', () => {
        cy.selectWallet("Ghost wallet")
        cy.get('#btn_send').click()
        // Simulating pasting the address, this also reduces the amount of fetch API calls to just one
        cy.get('#recipient_0').find('#address').invoke('val', "bcrt1qvtdx75y4554ngrq6aff3xdqnvjhmct5wck95qs").trigger('input')
        cy.get('#recipient_0').find('#label').type('To my own wallet', { force: true })
        cy.get('#recipient_0').find('#amount').type(10, { force: true })
        // Checking that the background colour of the address is green as it belongs to the wallet
        cy.get('#recipients').find('#recipient_0').find('#address').should('have.css', 'background-color','rgb(28, 65, 28)')
    })
    
    it('Send a transaction from a multisig wallet', () => {
        // We need a second hot wallet
        cy.addHotDevice("Hot Device 2","bitcoin")
        cy.addWallet('Test Multisig Wallet', 'segwit', 'funded', 'btc', 'multisig', 'Hot Device 1', 'Hot Device 2', 'DIY ghost')        
        cy.get('#btn_send').click()
        cy.get('#recipient_0').find('#address').type("bcrt1qsj30deg0fgzckvlrn5757yk55yajqv6dqx0x7u", { force: true })
        cy.get('#recipient_0').find('#label').type("Burn address", { force: true })
        cy.get('#recipient_0').get('#send_max').click()
        cy.get('#create_psbt_btn').click()
        cy.get('body').contains("Paste signed transaction")
        cy.get('#hot_device_1_tx_sign_btn').click()
        cy.get('#hot_device_1_hot_sign_btn').click()
        cy.get('#hot_enter_passphrase__submit').click()
        cy.get('#hot_device_2_tx_sign_btn').click()
        cy.get('#hot_device_2_hot_sign_btn').click()
        cy.get('#hot_enter_passphrase__submit').click()
        cy.get('#broadcast_local_btn').click()
        cy.get('#amount_total', { timeout: Cypress.env("broadcast_timeout") })
        .should(($div) => {
            const n = parseFloat($div.text())
            expect(n).to.be.equals(0)
        })
        // Clean up
        cy.deleteWallet("Test Multisig Wallet")
        cy.deleteDevice("Hot Device 1")
    })
})