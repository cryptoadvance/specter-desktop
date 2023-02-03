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
        cy.get('#fullbalance_amount').should('have.text', '20.00000000') // should('have.text') returns ALL textContents (descendants and unvisible text)
        cy.get('#fullbalance_amount').find('span').first().should('have.text', '0').and('not.be.visible')
        cy.get('#fullbalance_amount').find('.thousand-digits-in-btc-amount').children().each((element) => {
            cy.wrap(element).should('have.text', '0') 
            cy.wrap(element).should('not.be.visible') 
        });
        cy.get('#fullbalance_amount').find('.last-digits-in-btc-amount').children().each((element) => {
            cy.wrap(element).should('have.text', '0') 
            cy.wrap(element).should('not.be.visible') 
        });
    })

    it('Unconfirmed balance of 0.05 BTC', () => {
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
        cy.get('#recipient_0').find('#address').invoke('val', 'bcrt1qvtdx75y4554ngrq6aff3xdqnvjhmct5wck95qs') 
        cy.get('#recipient_0').find('#amount').type(0.05, { force: true })
        cy.get('#toggle_advanced').click()
        cy.get('.fee_container').find('#fee_option_manual').click()
        cy.get('#fee_manual').find('#fee_rate').clear( { force: true })
        cy.get('#fee_manual').find('#fee_rate').type(5, { force: true }) // Should be a fee of 709 sats.
        cy.get('#create_psbt_btn').click()
        cy.get('body').contains("Paste signed transaction")
        cy.get('#satoshis_hot_keys_tx_sign_btn').click()
        cy.get('#satoshis_hot_keys_hot_sign_btn').click()
        cy.get('#hot_enter_passphrase__submit').click()
        cy.get('#broadcast_local_btn').click()
        cy.visit("/")
        cy.selectWallet('Ghost wallet')
        // Once again because only once doesn't work for some stupid unknown reason
        cy.selectWallet('Ghost wallet')
        cy.get('#unconfirmed_amount').should('have.text', '0.05000000')
        cy.get('#unconfirmed_amount').find('.thousand-digits-in-btc-amount').children().each((element) => {
            cy.wrap(element).should('have.text', '0') 
            cy.wrap(element).should('not.be.visible') 
        });
        cy.get('#unconfirmed_amount').find('.last-digits-in-btc-amount').children().each((element) => {
            cy.wrap(element).should('have.text', '0') 
            cy.wrap(element).should('not.be.visible') 
        });
    })

    it('Total balance with all digits', () => {
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
        cy.get('#fullbalance_amount').should('have.text', '19.94999291')
        cy.get('#fullbalance_amount').find('.thousand-digits-in-btc-amount').should('have.text', '999') 
        cy.get('#fullbalance_amount').find('.thousand-digits-in-btc-amount').should('have.css', 'color','rgb(145, 145, 145)') 
        cy.get('#fullbalance_amount').find('.last-digits-in-btc-amount').should('have.text', '291') 
        cy.get('#fullbalance_amount').find('.last-digits-in-btc-amount').should('have.css', 'color','rgb(121, 121, 121)') 
        cy.get('#fullbalance_amount').children().each((element) => {
            cy.wrap(element).should('be.visible')
            cy.log(element)
        });
    })

    // TODO: Test (new) amount display once implemented, e.g. in sending dialogue, could probably be done in one of the tests above.

})
