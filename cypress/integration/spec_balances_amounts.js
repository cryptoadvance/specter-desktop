describe('Test the rendering of balances and amounts', () => {
    before(() => {
        Cypress.config('includeShadowDom', true)
    })

    it('Total balance', () => {
        cy.selectWallet('Ghost wallet')
        cy.get('#fullbalance_amount').then(($amount) => {
            expect(parseFloat($amount.text())).to.be.gt(19)
        }) 
    })

    it('Unconfirmed balance', () => {
        cy.addHotDevice('Satoshis hot keys','bitcoin')
        cy.addWallet('Funding wallet', 'segwit', 'funded', true, 'btc', 'singlesig', 'Satoshis hot keys')
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
        cy.get('#unconfirmed_amount').then(($amount) => {
            expect(parseFloat($amount.text())).to.be.gt(0).and.to.be.lt(1);
        })      
        cy.get('#unconfirmed_amount').find('.thousand-digits-in-btc-amount').children().each((element) => {
            cy.wrap(element).should('have.text', '0') 
        });
        cy.get('#unconfirmed_amount').find('.last-digits-in-btc-amount').children().each((element) => {
            cy.wrap(element).should('have.text', '0') 
        });
    })

    it('Total balance with all digits', () => {
        cy.selectWallet('Funding wallet')
        cy.get('#fullbalance_amount').find('.thousand-digits-in-btc-amount').should(($amount) => {
            expect($amount.text()).to.match(/^\d{3}$/)
        }).and(($amount) => {
            expect(parseFloat($amount.text())).to.be.gt(0);
        }); 
        cy.get('#fullbalance_amount').find('.last-digits-in-btc-amount').should(($amount) => {
            expect($amount.text()).to.match(/^\d{3}$/)
        }).and(($amount) => {
            expect(parseFloat($amount.text())).to.be.gt(0);
        });
        cy.get('#fullbalance_amount').children().each((element) => {
            cy.wrap(element).should('be.visible')
        })
    })
})
