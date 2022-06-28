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
    })
 


    it('Delete recipient ids=0,2. Remaining ids=1,3,4 => Recipients 2,4,5', () => {
        // We need new sats but mine2wallet only works if a wallet is selected
        cy.selectWallet("Test Hot Wallet 1")
        cy.mine2wallet("btc")
        cy.get('#btn_send').click()
        /// The addresses are the first three from DIY ghost
        cy.get('#address_0').invoke('val', "bcrt1qvtdx75y4554ngrq6aff3xdqnvjhmct5wck95qs")  // will be deleted, so address doesnt matter
        cy.get('#label_0').type("Recipient 1 to be deleted")
        cy.get('#amount_0').type(1)
        cy.get('#toggle_advanced').click()
        cy.get('main').scrollTo('bottom')
        
        cy.get('#add-recipient').click()
        cy.get('#address_1').invoke('val', "bcrt1qgzmq6e3tn67kveryf2je6nd3nv4txef4sl8wre")  // pasting the address is faster than typing
        cy.get('#label_1').type("Recipient 2")
        cy.get('#amount_1').type(2)
        cy.get('main').scrollTo('bottom')

        cy.get('#add-recipient').click()
        cy.get('#address_2').invoke('val', "bcrt1q9mkrhmxcn7rslzfv6lke8859m7ntwudfjqmcx7")  // will be deleted, so address doesnt matter
        cy.get('#label_2').type("Recipient 3 to be deleted")
        cy.get('#amount_2').type(3)

        cy.get('#add-recipient').click()
        cy.get('#address_3').invoke('val', "bcrt1qvtdx75y4554ngrq6aff3xdqnvjhmct5wck95qs")  // pasting the address is faster than typing
        cy.get('#label_3').type("Recipient 4")
        cy.get('#amount_3').type(4)

        cy.get('#add-recipient').click()
        cy.get('#address_4').invoke('val', "bcrt1q9mkrhmxcn7rslzfv6lke8859m7ntwudfjqmcx7")  // pasting the address is faster than typing
        cy.get('#label_4').type("Recipient 5")
        cy.get('#amount_4').type(5)
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


        cy.get('#remove_0').click({force: true})   
        cy.get('#remove_2').click({force: true})  

        // Change recipient number to Recipient 2 (value = id = 1)
        cy.get('#fee-selection-component').find('.fee_container').find('#subtract_from_recipient_id_select').should('have.length', 3)           
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


        cy.get('#deletepsbt_btn').click()
        // Clean up (Hot Device 1 is still needed below)
        cy.deleteWallet("Test Hot Wallet 1")
    })
 
})