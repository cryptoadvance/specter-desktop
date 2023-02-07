// This spec file assumes that the Ghost wallet is available, 
// Fetch API values for fees are mocked

describe('Test the fee UI', () => {
    before(() => {
        Cypress.config('includeShadowDom', true)
       })

    it('Using dynamic mode with normal fees', () => {
        // Fees: {"fastestFee": 9, "halfHourFee": 5, "hourFee": 3, "minimumFee": 1}
        cy.selectWallet('Ghost wallet')
        cy.intercept('GET', '/wallets/fees', { fixture: 'fees/normal_fees.json' })
        cy.get('#btn_send').click()
        cy.get('#toggle_advanced').click()
        // Preselected dynamic fee rate
        cy.get('#fee_rate_dynamic_text').should('have.text', '5')
        // Speed text
        cy.get('#fee_rate_speed_text').should('have.text', 'Fast (30 minutes)')
        // Slider 
        cy.get('#fees_slider').should('have.value', '5')
        cy.get('#fees_slider').invoke('attr', 'min').should('eq', '1')
        cy.get('#fees_slider').invoke('attr', 'max').should('eq', '12')
        // Simulate sliding to 1.5
        cy.get('#fees_slider').invoke('val', '1.5').trigger('input')
        cy.get('#fees_slider').should('have.value', '1.5')
        cy.get('#fee_rate_speed_text').should('have.text', 'Very slow')
        // Sliding to 2
        cy.get('#fees_slider').invoke('val', '2').trigger('input')
        cy.get('#fees_slider').should('have.value', '2')
        cy.get('#fee_rate_speed_text').should('have.text', 'Slow')
        // Sliding to 11
        cy.get('#fees_slider').invoke('val', '11').trigger('input')
        cy.get('#fees_slider').should('have.value', '11')
        cy.get('#fee_rate_speed_text').should('have.text', 'Overpaid! (10 minutes)')
    })

    it('Using dynamic mode with low fees', () => {
        // Fees: {"fastestFee": 1, "halfHourFee": 1, "hourFee": 1, "minimumFee": 1}
        cy.selectWallet('Ghost wallet')
        cy.intercept('GET', '/wallets/fees', { fixture: 'fees/low_fees.json' })
        cy.get('#btn_send').click()
        cy.get('#toggle_advanced').click()
        // Preselected dynamic fee rate
        cy.get('#fee_rate_dynamic_text').should('have.text', '1')
        // Speed text
        cy.get('#fee_rate_speed_text').should('have.text', 'Very fast (10 minutes)')
        // Slider 
        cy.get('#fees_slider').should('have.value', '1')
        cy.get('#fees_slider').invoke('attr', 'min').should('eq', '1')
        cy.get('#fees_slider').invoke('attr', 'max').should('eq', '1.5')
        // Simulate sliding to 1.5
        cy.get('#fees_slider').invoke('val', '1.5').trigger('input')
        cy.get('#fees_slider').should('have.value', '1.5')
        cy.get('#fee_rate_speed_text').should('have.text', 'Overpaid! (10 minutes)')
    })

    it('Using dynamic mode with low non-integer fees', () => {
        // Fees: {"fastestFee": 1.1, "halfHourFee": 1, "hourFee": 1, "minimumFee": 1}
        cy.selectWallet('Ghost wallet')
        cy.intercept('GET', '/wallets/fees', { fixture: 'fees/low_non-integer_fees.json' })
        cy.get('#btn_send').click()
        cy.get('#toggle_advanced').click()
        // Preselected dynamic fee rate
        cy.get('#fee_rate_dynamic_text').should('have.text', '1')
        // Speed text
        cy.get('#fee_rate_speed_text').should('have.text', 'Fast (30 minutes)')
        // Slider 
        cy.get('#fees_slider').should('have.value', '1')
        cy.get('#fees_slider').invoke('attr', 'min').should('eq', '1')
        cy.get('#fees_slider').invoke('attr', 'max').should('eq', '2')
        // Simulate sliding to 1.1
        cy.get('#fees_slider').invoke('val', '1.1').trigger('input')
        cy.get('#fees_slider').should('have.value', '1.1')
        cy.get('#fee_rate_speed_text').should('have.text', 'Very fast (10 minutes)')
    })

    it('Using dynamic mode with high fees', () => {
        // Fees: {"fastestFee": 14, "halfHourFee": 10, "hourFee": 7, "minimumFee": 1}
        cy.selectWallet('Ghost wallet')
        cy.intercept('GET', '/wallets/fees', { fixture: 'fees/high_fees.json' })
        cy.get('#btn_send').click()
        cy.get('#toggle_advanced').click()
        // Preselected dynamic fee rate
        cy.get('#fee_rate_dynamic_text').should('have.text', '7')
        // Speed text
        cy.get('#fee_rate_speed_text').should('have.text', 'Medium (1 hour)')
        // Slider 
        cy.get('#fees_slider').should('have.value', '7')
        cy.get('#fees_slider').invoke('attr', 'min').should('eq', '1')
        cy.get('#fees_slider').invoke('attr', 'max').should('eq', '19')
        // Simulate sliding to 3
        cy.get('#fees_slider').invoke('val', '3').trigger('input')
        cy.get('#fees_slider').should('have.value', '3')
        cy.get('#fee_rate_speed_text').should('have.text', 'Very slow')
        // Simulate sliding to 4.5
        cy.get('#fees_slider').invoke('val', '4.5').trigger('input')
        cy.get('#fees_slider').should('have.value', '4.5')
        cy.get('#fee_rate_speed_text').should('have.text', 'Slow')
    })

    it('Using dynamic mode with asymmetric fees', () => {
        // Fees: {"fastestFee": 13, "halfHourFee": 4, "hourFee": 2, "minimumFee": 1}
        cy.selectWallet('Ghost wallet')
        cy.intercept('GET', '/wallets/fees', { fixture: 'fees/asymmetric_fees.json' })
        cy.get('#btn_send').click()
        cy.get('#toggle_advanced').click()
        // Preselected dynamic fee rate
        cy.get('#fee_rate_dynamic_text').should('have.text', '2')
        // Speed text
        cy.get('#fee_rate_speed_text').should('have.text', 'Medium (1 hour)')
        // Slider 
        cy.get('#fees_slider').should('have.value', '2')
        cy.get('#fees_slider').invoke('attr', 'min').should('eq', '1')
        cy.get('#fees_slider').invoke('attr', 'max').should('eq', '18')
        // Simulate sliding to 12.5
        cy.get('#fees_slider').invoke('val', '12.5').trigger('input')
        cy.get('#fees_slider').should('have.value', '12.5')
        cy.get('#fee_rate_speed_text').should('have.text', 'Fast (30 minutes)')
        // Simulate sliding to 4
        cy.get('#fees_slider').invoke('val', '4').trigger('input')
        cy.get('#fees_slider').should('have.value', '4')
        cy.get('#fee_rate_speed_text').should('have.text', 'Fast (30 minutes)')
        // Simulate sliding to 3
        cy.get('#fees_slider').invoke('val', '3').trigger('input')
        cy.get('#fees_slider').should('have.value', '3')
        cy.get('#fee_rate_speed_text').should('have.text', 'Medium (1 hour)')
        // Simulate sliding to 1.6
        cy.get('#fees_slider').invoke('val', '1.6').trigger('input')
        cy.get('#fees_slider').should('have.value', '1.6')
        cy.get('#fee_rate_speed_text').should('have.text', 'Slow')
        // Simulate sliding to 1.2
        cy.get('#fees_slider').invoke('val', '1.2').trigger('input')
        cy.get('#fees_slider').should('have.value', '1.2')
        cy.get('#fee_rate_speed_text').should('have.text', 'Very slow')
    })

    it('Using manual mode', () => {
        cy.selectWallet('Ghost wallet')
        cy.intercept('GET', '/wallets/fees', { fixture: 'fees/normal_fees.json' })
        cy.get('#btn_send').click()
        cy.get('#toggle_advanced').click()
        cy.get('.fee_container').find('#fee_option_manual').click()
        cy.get('#fee_manual').find('#fee_rate').should('have.value', '1')
        cy.get('#fee_manual').find('#fee_rate').clear( { force: true })
        cy.get('#fee_manual').find('#fee_rate').type(5, { force: true })
        cy.get('#fee_manual').find('#fee_rate').should('have.value', '5')
    })

    it('Show estimated fee', () => {
        cy.selectWallet('Ghost wallet')
        cy.get('#btn_send').click()
        cy.intercept('POST', '/wallets/wallet/ghost_wallet/estimate_fee', {fee: 0.00005944})
        cy.get('[data-cy="show-estimated-fee-btn"]').click()
        cy.contains('You provided no address')
        cy.get('#recipient_0').find('#address').invoke('val', "bcrt1qvtdx75y4554ngrq6aff3xdqnvjhmct5wck95qs")
        cy.get('[data-cy="sats-checkbox"]').click()
        cy.get('#recipient_0').find('[data-cy="amount-input"]').type(50000, { force: true })
        cy.get('[data-cy="show-estimated-fee-btn"]').click()
        cy.get('[data-cy="estimated-fee-box"]').contains('5944 sats')
        cy.get('[data-cy="close-fee-box-btn"]').click()
        cy.get('[data-cy="estimated-fee-box"]').should('not.be.visible')
        cy.get('#toggle_advanced').click()
        cy.get('[data-cy="csv-editor-checkbox"]').click()
        cy.get('[data-cy="csv-editor-sats-checkbox"]').click()
        cy.get('[data-cy="csv-editor-textarea"]').type('bcrt1q3fcv4hqd5cw55lh0zeg83vlau07fjceukn0a85, 50000{ctrl}{enter}')
        cy.get('[data-cy="csv-editor-textarea"]').type('bcrt1qs74297wdnd0wmztekcmz3wnd6f6c3glj77ted9, 70000{ctrl}')
        cy.get('[data-cy="show-estimated-fee-btn"]').click()
        cy.get('[data-cy="estimated-fee-box"]').contains('5944 sats')
    })

})