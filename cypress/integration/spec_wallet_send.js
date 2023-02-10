// This test builds upon the ghost machine test.
describe('Test sending transactions', () => {
    before(() => {
        Cypress.config('includeShadowDom', true)
    })

    it('Send a standard transaction', () => {
        cy.addHotDevice("Hot Device 1","bitcoin")
        cy.addWallet('Test Hot Wallet 1', 'segwit', 'funded', true, 'btc', 'singlesig', 'Hot Device 1')
        cy.selectWallet("Test Hot Wallet 1")
        cy.get('#btn_send').click()
        cy.get('#recipient_0').find('#address').type("bcrt1qsj30deg0fgzckvlrn5757yk55yajqv6dqx0x7u", { force: true })
        cy.get('#recipient_0').find('#label').type("Burn address", { force: true })
        cy.get('#recipient_0').get('#send_max').click()
        cy.get('#create_psbt_btn').click()
        cy.get('body').contains("Paste signed transaction")
        // TODO: Add check of transaction details here
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

    it('Create a transaction with the CSV editor', () => {
        cy.selectWallet("Ghost wallet")
        cy.get('#btn_send').click()
        cy.get('#toggle_advanced').click()
        cy.get('[data-cy="csv-editor-checkbox"]').click()
        cy.get('[data-cy="csv-editor-sats-checkbox"]').click()
        cy.get('[data-cy="csv-editor-textarea"]').type('bcrt1q3fcv4hqd5cw55lh0zeg83vlau07fjceukn0a85, 50000{ctrl}{enter}')
        cy.get('[data-cy="csv-editor-textarea"]').type('bcrt1qs74297wdnd0wmztekcmz3wnd6f6c3glj77ted9, 70000{ctrl}')
        cy.get('#create_psbt_btn').click()
        cy.contains('Sending 0.0005')
        cy.get('[data-cy="delete-tx-btn"]').click()
    })


    it('Open up transaction details', () => {
        cy.selectWallet("Test Hot Wallet 1")
        cy.get('#btn_transactions').click()
        // Click on the first txid with category "send"
        cy.get('[data-cy="tx-category-send"]').click()
        // Input
        cy.get('.tx-data-info').contains('Value: 20 tBTC')
        // Output
        cy.get('.tx-data-info').contains(/Value:\s19\.9999\d{3}/) // The amount from the raw tx has 7 decimals, fees change apparently
        cy.get('[data-cy="transaction-details-screen-close-btn"]').click()
        // Change to sats and check amounts and units
        cy.get('[data-cy="settings-btn"]').click()
        cy.get('[name="unit"]').select('sats')
        cy.contains('Save').click()
        cy.selectWallet("Test Hot Wallet 1")
        cy.get('#btn_transactions').click()
        cy.get('tbody.tx-tbody').find('tr').find('.svg-send').parent().parent().parent().parent().find('#column-txid').find('.explorer-link').click()
        // Input
        cy.get('.tx-data-info').contains('Value: 2,000,000,000 tsat')
        // Output
        cy.get('.tx-data-info').contains(/Value:\s1,999,99\d,\d{3}\stsat/) // Fees change apparently
        cy.get('[data-cy="transaction-details-screen-close-btn"]').click()
        // Change back to btc
        cy.get('[data-cy="settings-btn"]').click()
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
        
        // Check subtract fees from amount checkbox to subtract from a specific recipient
        cy.get('#toggle_advanced').click()
        cy.get('main').scrollTo('bottom')
        cy.get('[data-cy="subtract-fees-checkbox"]').click()
        cy.get('[data-cy="subtract-fees-checkbox"]').should('be.checked')

        // Check whether the recipient number select field popped up
        cy.get('[data-cy="subtract-from-recipient-selection"]').as('subtractFromRecipientSelection')
        cy.get('@subtractFromRecipientSelection').should('be.visible')

        // Check the values of the hidden inputs in the light DOM which are used for the form
        // Note: Despite identical ids the hidden inputs seem to be fetched first since they are higher up in the DOM
        cy.get('#fee-selection-component').find('#subtract').invoke('attr', 'value').should('eq', 'true')

        // Remove two recipients
        cy.get('#recipient_0').find('#remove').click({ force: true })   
        cy.get('#recipient_2').find('#remove').click({ force: true })  

        // Select different recipients to subtract the fees from
        cy.get('[data-cy="subtract-from-recipient-selection"]').as('subtractFromRecipientSelection')
        cy.get('@subtractFromRecipientSelection').select('Recipient 4') // html select with cypress: https://www.cypress.io/blog/2020/03/20/working-with-select-elements-and-select2-widgets-in-cypress/
        cy.get('@subtractFromRecipientSelection').select('Recipient 5')  
        cy.get('@subtractFromRecipientSelection').select('Recipient 2')   
        cy.get('@subtractFromRecipientSelection').should('have.value', '1');
        cy.get('@subtractFromRecipientSelection').find(':selected').should('have.text', 'Recipient 2');

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
        cy.get('[data-cy="subtract-fees-checkbox"]').should('be.checked')

        // Check whether the selection of the recipient to subtract the fees from is visible
        cy.get('main').scrollTo('bottom')
        cy.get('[data-cy="subtract-from-recipient-selection"]').as('subtractFromRecipientSelection')
        cy.get('@subtractFromRecipientSelection').should('be.visible')
        
        // Check the values of the hidden inputs in the light DOM which are used for the form
        // Note: Despite identical ids the hidden inputs seem to be fetched first since they are higher up in the DOM
        cy.get('#fee-selection-component').find('#subtract').invoke('attr', 'value').should('eq', 'true')
        
        // Check whether send max set subtract_from to Recipient 3
        cy.get('@subtractFromRecipientSelection').should('have.value', '2');
        cy.get('@subtractFromRecipientSelection').find(':selected').should('have.text', 'Recipient 3');
        
        // Select Recipient 2 to subract the fee from
        cy.get('@subtractFromRecipientSelection').select('Recipient 2')
        cy.get('@subtractFromRecipientSelection').should('have.value', '1');
        cy.get('@subtractFromRecipientSelection').find(':selected').should('have.text', 'Recipient 2');

        // Change it back to Recipient 3
        cy.get('#recipient_2').find('#send_max').click()

        // The fee should be subtracted from the third recipient
        cy.get('#create_psbt_btn').click()
        // TODO: Avoid nth child
        cy.get('div.tx_info > :nth-child(3) > :nth-child(1)').then(($div) => {
            const amount = parseFloat($div.text())
            // Subtracting fees should give a number with decimals (amount above where whole numbers)
            expect(amount % 1).not.to.equal(0);

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
        cy.get('#recipient_0').find('#label').type('To my own wallet')
        // By passing { force: true }, Cypress will interact with the input element
        // bypassing any constraints that would prevent it from interacting with it, such as the min and step attributes
        cy.get('#recipient_0').find('#amount').type(10, { force: true })
        // Checking that the address belongs to the wallet
        cy.get('#recipients').find('#recipient_0').find('#address').should('have.attr', 'data-cy','address-is-mine')
    })
    
    it('Send a transaction from a multisig wallet', () => {
        // We need a second hot wallet
        cy.addHotDevice("Hot Device 2","bitcoin")
        cy.addWallet('Test Multisig Wallet', 'segwit', 'funded', true, 'btc', 'multisig', 'Hot Device 1', 'Hot Device 2', 'DIY ghost')  
        cy.selectWallet('Test Multisig Wallet')      
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
        cy.get('#fullbalance_amount', { timeout: Cypress.env("broadcast_timeout") })
        .should(($div) => {
            const n = parseFloat($div.text())
            expect(n).to.be.equals(0)
        })
        // Clean up
        cy.deleteWallet("Test Multisig Wallet")
        cy.deleteDevice("Hot Device 1")
    })
})
