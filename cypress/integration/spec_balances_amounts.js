// 
describe('Test the rendering of balances and amounts', () => {
    before(() => {
        Cypress.config('includeShadowDom', true)
        cy.visit('/')
    })

    // Keeps the session cookie alive, Cypress by default clears all cookies before each test
    beforeEach(() => {
        cy.viewport(1200,660)
        Cypress.Cookies.preserveOnce('session')
    })

    it('Total balance of 20 BTC', () => {
        /* This is how the DOM looks like
        <th id="fullbalance_amount" class="right-align">
            20.0
            <span class="unselectable transparent-text">0</span>
            <span class="thousand-digits-in-btc-amount">
                <span class="unselectable transparent-text">0</span>
                <span class="unselectable transparent-text">0</span>
                <span class="unselectable transparent-text">0</span>
            </span>
            <span class="last-digits-in-btc-amount">
                <span class="unselectable transparent-text">0</span>
                <span class="unselectable transparent-text">0</span>
                <span class="unselectable transparent-text">0</span>
            </span>
        </th>
        */
        cy.selectWallet('Ghost wallet')
        cy.get('#amount_total').should('have.text', '20.00000000') // should('have.text') returns ALL textContents (descendants and unvisible text)
        cy.get('#amount_total').find('span').first().should('have.text', '0').and('not.be.visible')
        cy.get('#amount_total').find('.thousand-digits-in-btc-amount').children().each((element) => {
            cy.wrap(element).should('have.text', '0') 
            cy.wrap(element).should('not.be.visible') 
        });
        cy.get('#amount_total').find('.last-digits-in-btc-amount').children().each((element) => {
            cy.wrap(element).should('have.text', '0') 
            cy.wrap(element).should('not.be.visible') 
        });
    })

    it('Sending a tx with 0.05 tBTC', () => {
        /* This is how the DOM looks like
        <th id="unconfirmed_amount" class="right-align">
            0.05
            <span class="thousand-digits-in-btc-amount">
                <span class="unselectable transparent-text">0</span>
                <span class="unselectable transparent-text">0</span>
                <span class="unselectable transparent-text">0</span>
            </span>
            <span class="last-digits-in-btc-amount">
                <span class="unselectable transparent-text">0</span>
                <span class="unselectable transparent-text">0</span>
                <span class="unselectable transparent-text">0</span>
            </span>
        </th>
        */
        // We get 5 mio. sats from a funding wallet
        // TODO: If this funding wallet is used more, move it to a seperate spec file
        cy.addHotDevice('Satoshis hot keys','bitcoin')
        cy.addWallet('Funding wallet', 'segwit', 'funded', 'btc', 'singlesig', 'Satoshis hot keys')
        cy.selectWallet('Funding wallet')
        cy.get('#btn_send').click()
        // check that the amount_available for sending is displayed correct
        cy.get('#wallet-amount_available').should('have.text', '20.00000000 tBTC') 
        cy.get('#wallet-amount_available').find('.thousand-digits-in-btc-amount').children().each((element) => {
            cy.wrap(element).should('have.text', '0') 
            cy.wrap(element).should('not.be.visible') 
            cy.wrap(element).should('be.hidden') 
        });
        cy.get('#wallet-amount_available').find('.last-digits-in-btc-amount').children().each((element) => {
            cy.wrap(element).should('have.text', '0') 
            cy.wrap(element).should('not.be.visible') 
            cy.wrap(element).should('be.hidden') 
        });

        cy.get('#recipient_0').find('#address').invoke('val', 'bcrt1qvtdx75y4554ngrq6aff3xdqnvjhmct5wck95qs') 
        cy.get('#recipient_0').find('#amount').type(0.05, { force: true })
        cy.get('#toggle_advanced').click()
        cy.get('.fee_container').find('#fee_option_manual').click()
        cy.get('#fee_manual').find('#fee_rate').clear( { force: true })
        cy.get('#fee_manual').find('#fee_rate').type(5, { force: true }) // Should be a fee of 709 sats.
        cy.get('#create_psbt_btn').click()
        // check that the psbt amount is displayed correct
        cy.get('#psbt-amount-0').should('have.text', '0.05000000 tBTC')  
        cy.get('#psbt-amount-0').find('.thousand-digits-in-btc-amount').children().each((element) => {
            cy.wrap(element).should('have.text', '0') 
            cy.wrap(element).should('be.hidden') 
            cy.wrap(element).should('not.be.visible') 
        });
        cy.get('#psbt-amount-0').find('.last-digits-in-btc-amount').children().each((element) => {
            cy.wrap(element).should('have.text', '0') 
            cy.wrap(element).should('be.hidden') 
            cy.wrap(element).should('not.be.visible') 
        });

        cy.get('body').contains("Paste signed transaction")
        cy.get('#satoshis_hot_keys_tx_sign_btn').click()
        cy.get('#satoshis_hot_keys_hot_sign_btn').click()
        cy.get('#hot_enter_passphrase__submit').click()
        cy.get('#broadcast_local_btn').click()
    })


    it('Sending a tx with 0.001234 tBTC', () => {
        // get the ghot receive address to the clipboard
        // cy.selectWallet('Ghost wallet')
        // cy.selectWallet('Ghost wallet')       // Once again because only once doesn't work for some stupid unknown reason
        // cy.get('#btn_receive').click()
        // cy.get('#address').click()  // get receive address from ghost wallet 
        cy.selectWallet('Funding wallet')
        cy.selectWallet('Funding wallet')       // Once again because only once doesn't work for some stupid unknown reason
        cy.get('#btn_send').click()
        // check that the amount_available for sending is displayed correct
        // cy.get('#wallet-amount_available').should('have.text', '20.00000000 tBTC') 
        // cy.get('#wallet-amount_available').find('.thousand-digits-in-btc-amount').children().each((element) => {
        //     cy.wrap(element).should('have.text', '0') 
        //     cy.wrap(element).should('not.be.visible') 
        //     cy.wrap(element).should('be.hidden') 
        // });
        // cy.get('#wallet-amount_available').find('.last-digits-in-btc-amount').children().each((element) => {
        //     cy.wrap(element).should('have.text', '0') 
        //     cy.wrap(element).should('not.be.visible') 
        //     cy.wrap(element).should('be.hidden') 
        // });

                
        //  using the clipboard directly doesn't work
        // cy.window().then((win) => {
        //     win.navigator.clipboard.readText().then((text) => {
        //         cy.get('#recipient_0').find('#address').invoke('val', text, { force: true }) ;
        //     });
        // });        
        cy.get('#recipient_0').find('#address').invoke('val', 'bcrt1q9mkrhmxcn7rslzfv6lke8859m7ntwudfjqmcx7', { force: true }) ;
        cy.get('#recipient_0').find('#amount').type(0.001234, { force: true })
        cy.get('#toggle_advanced').click()
        cy.get('.fee_container').find('#fee_option_manual').click()
        cy.get('#fee_manual').find('#fee_rate').clear( { force: true })
        cy.get('#fee_manual').find('#fee_rate').type(50, { force: true }) // Should be a fee of 7090 sats.
        cy.get('#create_psbt_btn').click()
        // check that the psbt amount is displayed correct
        cy.get('#psbt-amount-0').should('have.text', '0.00123400 tBTC')  
        cy.get('#psbt-amount-0').find('.thousand-digits-in-btc-amount').should('be.visible').should('have.text', '123') 
        cy.get('#psbt-amount-0').find('.last-digits-in-btc-amount').should('be.visible').should('have.text', '400') 

        cy.get('body').contains("Paste signed transaction")
        cy.get('#satoshis_hot_keys_tx_sign_btn').click()
        cy.get('#satoshis_hot_keys_hot_sign_btn').click()
        cy.get('#hot_enter_passphrase__submit').click()
        cy.get('#broadcast_local_btn').click()
    })

    it('Check balances after transmitting tx, Unconfirmed balance of 0.05123400 BTC', () => {
        cy.selectWallet('Ghost wallet')
        cy.selectWallet('Ghost wallet')       // Once again because only once doesn't work for some stupid unknown reason
        // amount_total
        cy.get('#amount_total').should('have.text', '40.05123400')
        cy.get('#amount_total').find('.thousand-digits-in-btc-amount').should('be.visible').should('have.text', '123') 
        cy.get('#amount_total').find('.last-digits-in-btc-amount').should('be.visible').should('have.text', '400')  
        // amount_confirmed
        cy.get('#amount_confirmed').should('have.text', '40.00000000')
        cy.get('#amount_confirmed').find('.thousand-digits-in-btc-amount').children().each((element) => {
            cy.wrap(element).should('have.text', '0') 
            cy.wrap(element).should('not.be.visible') 
        });
        cy.get('#amount_confirmed').find('.last-digits-in-btc-amount').children().each((element) => {
            cy.wrap(element).should('have.text', '0') 
            cy.wrap(element).should('not.be.visible') 
        });
        // amount_unconfirmed
        cy.selectWallet('Ghost wallet')
        cy.get('#amount_unconfirmed').should('have.text', '0.05123400')
        cy.get('#amount_unconfirmed').find('.thousand-digits-in-btc-amount').should('be.visible').should('have.text', '123') 
        cy.get('#amount_unconfirmed').find('.last-digits-in-btc-amount').should('be.visible').should('have.text', '400')   
        // the the address balances
        cy.get('#btn_addresses').click()

        // the 1. tx
        cy.get('.addr-tbody').find('tr').eq(0).find('.amount').should('have.text', '20.05000000 tBTC')
        cy.get('.addr-tbody').find('tr').eq(0).find('.amount').find('.thousand-digits-in-btc-amount').children().each((element) => {
            cy.wrap(element).should('have.text', '0') 
            cy.wrap(element).should('not.be.visible') 
        });
        cy.get('.addr-tbody').find('tr').eq(0).find('.amount').find('.last-digits-in-btc-amount').children().each((element) => {
            cy.wrap(element).should('have.text', '0') 
            cy.wrap(element).should('not.be.visible') 
        });

        // the 2. tx
        cy.get('.addr-tbody').find('tr').eq(2).find('.amount').should('have.text', '0.00123400 tBTC')
        cy.get('.addr-tbody').find('tr').eq(2).find('.amount').find('.thousand-digits-in-btc-amount').should('be.visible').should('have.text', '123') 
        cy.get('.addr-tbody').find('tr').eq(2).find('.amount').find('.last-digits-in-btc-amount').should('be.visible').should('have.text', '400')   


    })


    it('Check balances after transmitting tx in sats, Unconfirmed balance of 0.05123400 BTC', () => {
        cy.get("#settings-bar-btn-settings").click()
        cy.get("#select-global-bitcoin-unit").select('sat')
        cy.get("#settings-save-btn").click()
            
        cy.selectWallet('Ghost wallet')
        cy.selectWallet('Ghost wallet')       // Once again because only once doesn't work for some stupid unknown reason
        // amount_total
        cy.get('#amount_total').should('have.text', '4,005,123,400')
        // amount_confirmed
        cy.get('#amount_confirmed').should('have.text', '4,000,000,000')
        // amount_unconfirmed
        cy.selectWallet('Ghost wallet')
        cy.get('#amount_unconfirmed').should('have.text', '5,123,400')
        // the the address balances
        cy.get('#btn_addresses').click()

        // the 1. tx
        cy.get('.addr-tbody').find('tr').eq(0).find('.amount').should('have.text', '2,005,000,000 tsat')
        // the 2. tx
        cy.get('.addr-tbody').find('tr').eq(2).find('.amount').should('have.text', '123,400 tsat')


        cy.get("#settings-bar-btn-settings").click()
        cy.get("#select-global-bitcoin-unit").select('btc')
        cy.get("#settings-save-btn").click()
    })



    it('Total balance with all digits, which is 20 tBTC - fee', () => {
        /* This is how the DOM looks like
        <th id="fullbalance_amount" class="right-align">
            19.94
            <span class="thousand-digits-in-btc-amount">999</span>
            <span class="last-digits-in-btc-amount">291</span>
        </th>
        */
        // Let's use the funding wallet
        // Works as long as the fee was 709 and the original balance of the funding wallet was 20 BTC
        cy.selectWallet('Funding wallet')
        cy.selectWallet('Funding wallet')
        cy.get('#amount_total').should('have.text', '19.94868791')
        cy.get('#amount_total').find('.thousand-digits-in-btc-amount').should('have.text', '868') 
        cy.get('#amount_total').find('.thousand-digits-in-btc-amount').should('have.css', 'color','rgb(145, 145, 145)') 
        cy.get('#amount_total').find('.last-digits-in-btc-amount').should('have.text', '791') 
        cy.get('#amount_total').find('.last-digits-in-btc-amount').should('have.css', 'color','rgb(121, 121, 121)') 
        cy.get('#amount_total').children().each((element) => {
            cy.wrap(element).should('be.visible')
            cy.log(element)
        });
    })

    // TODO: Test (new) amount display once implemented, e.g. in sending dialogue, could probably be done in one of the tests above.

})
