// This test just needs a Bitcoin Core connection
describe('Test the actions in UTXO list', () => {
    
    before(() => {
        cy.visit('/')
        Cypress.config('includeShadowDom', true)
        const device_name = "UTXO device"
        const wallet_name = "UTXO wallet"
        cy.addHotDevice(device_name, "bitcoin")
        cy.addHotWallet(wallet_name, device_name, "bitcoin", "segwit")
        cy.get('#fullbalance_amount').then(($span) => {
            const balance = parseFloat($span.text())
            if (balance === 20) {
                cy.mine2wallet("btc")
                cy.mine2wallet("btc")
                // We are having 3 UTXO in the end (addHotWallet creates one automatically)
            }
            else {
                return
            }
        })
    })

    it('Freezing', () => {
        cy.selectWallet('UTXO wallet')
        cy.get('[data-cy="utxo-list-btn"]').click()
        cy.wait(500)
        // Freeze 2 UTXOs 
        cy.get('tx-table').find('tx-row').eq(0).find('.select-tx-img').click( {position: 'top'} )
        cy.get('tx-table').find('tx-row').eq(0).find('.select-tx-value').invoke('attr', 'value').should('eq', 'true') // Check whether click worked
        cy.wait(100)
        cy.get('tx-table').find('tx-row').eq(1).find('.select-tx-img').click( {position: 'top'} )
        cy.get('tx-table').find('tx-row').eq(1).find('.select-tx-value').invoke('attr', 'value').should('eq', 'true') 
        cy.wait(100)
        cy.get('tx-table').find('.freeze-tx-btn').click()
        cy.wait(500)
        // Check that we have 2 frozen outputs now
        cy.get('tx-table').find('tx-row').each(($el, index) => {
            if (index == 0 || index == 1) {
                cy.wrap($el).find('.tx-row').should('have.class', 'frozen')
                cy.wrap($el).find('.frozen-img').should('not.have.class', 'hidden')
            } else {
                cy.wrap($el).find('.tx-row').should('not.have.class', 'frozen')
                cy.wrap($el).find('.frozen-img').should('have.class', 'hidden')
            }   
        })
        // Check that we can't create a transaction when a frozen UTXO is selected ...
        cy.get('tx-table').find('tx-row').eq(2).find('.select-tx-img').click( {position: 'top'} ) // not frozen
        cy.get('tx-table').find('tx-row').eq(0).find('.select-tx-img').click( {position: 'top'} ) // frozen
        cy.get('tx-table').find('.compose-tx-btn').should('be.hidden')
        // ... and that the checkboxes disappear for the non-frozen UTXO and get unticked
        cy.get('tx-table').find('tx-row').eq(2).find('.select-tx-img').should('be.hidden')
        cy.get('tx-table').find('tx-row').eq(2).find('.select-tx-img').should('have.attr', 'src').and('contain', 'untick')
        // Unselect the first UTXO (frozen) again and check that all checkboxes are visible and none are selected
        cy.get('tx-table').find('tx-row').eq(0).find('.select-tx-img').click( {position: 'top'} )
        cy.wait(100)
        cy.get('tx-table').find('tx-row').each(($el, index, $list) => {
            cy.wrap($el).find('.tx-row').find('.select-tx-img').should('not.be.hidden').should('have.attr', 'src').and('contain', 'untick')
        })
    })

    it('Creating a transaction', () => {
        cy.selectWallet('UTXO wallet')
        cy.get('[data-cy="utxo-list-btn"]').click()
        cy.wait(500)
        // Unfreeze the first UTXO in the list (Address #2) and try to make a transaction with it
        cy.get('tx-table').find('tx-row').eq(0).find('.select-tx-img').click( {position: 'top'} )
        cy.wait(100)
        cy.get('tx-table').find('.freeze-tx-btn').click()
        cy.wait(200)
        // Select it
        cy.get('tx-table').find('tx-row').eq(0).find('.select-tx-img').click( {position: 'top'} );
        cy.get('tx-table').find('tx-row').eq(0).find('.select-tx-value').invoke('attr', 'value').should('eq', 'true') // Check that the click flow is (still) in order
        cy.wait(200)
        cy.get('tx-table').find('.compose-tx-btn').click()
        // Switch to coin selection, check that the right amount of coins are preselected in the coin selection
        cy.get('.coinselect-hidden').should('have.length', 1);
    })

    it('Managing unsigned transactions', () => {
        // At this point we have one frozen output left
        // Make an unsigned tx
        cy.selectWallet('UTXO wallet')
        cy.get('#btn_send').click()
        cy.get('[data-cy="coin-selection-toggle"]').click() 
        // Make an alias of the tx row with Address #0 label 
        cy.get('address-label[data-label="Address #0"]').closest('tr').as('unsignedTxRow')
        cy.get('address-label[data-label="Address #1"]').closest('tr').as('frozenTxRow')
        cy.get('address-label[data-label="Address #2"]').closest('tr').as('normalTxRow')
        // Select this UTXO in the coin selection
        cy.get('@unsignedTxRow').find('[data-cy="selectable-utxo-checkbox"]').click()
        cy.get('#recipient_0').find('#address').type("bcrt1qvtdx75y4554ngrq6aff3xdqnvjhmct5wck95qs") // address from "Ghost wallet"
        cy.get('#recipient_0').get('#send_max').click()
        cy.get('#create_psbt_btn').click()
        // Check the labeling of the unsigned UTXO
        cy.get('#btn_transactions').click()
        cy.wait(1000)
        cy.get('[data-cy="utxo-list-btn"]').click()
        cy.wait(500)
        cy.get('@unsignedTxRow').should('have.attr', 'data-cy', 'unsigned-tx-row')
        // Check that only the checkbox of the unsigned UTXO are visible if it is selected
        cy.get('@unsignedTxRow').find('.select-tx-img').click( {position: 'top'} )
        cy.get('@unsignedTxRow').find('.select-tx-img').should('be.visible')
        cy.get('@frozenTxRow').find('.select-tx-img').should('be.hidden')
        cy.get('@normalTxRow').find('.select-tx-img').should('be.hidden')
        // Unselect the UTXO again and check that all checkboxes are visible and none are selected
        cy.get('@unsignedTxRow').find('.select-tx-img').click( {position: 'top'} )
        cy.get('tx-table').find('tx-row').each(($el, index, $list) => {
            cy.wrap($el).find('.tx-row').find('.select-tx-img').should('be.visible')
        })
        // Select a normal UTXO and select an unsigned UTXO, then check that the checkbox for the normal UTXO is hidden
        cy.get('@normalTxRow').find('.select-tx-img').click()
        cy.get('@unsignedTxRow').find('.select-tx-img').click( {position: 'top'} )
        cy.get('@normalTxRow').find('.select-tx-img').should('be.hidden')
        // Unselect the unsigned UTXO again
        cy.get('@unsignedTxRow').find('.select-tx-img').click( {position: 'top'} )
        // Check that all checkboxes are visible again and none are selected
        cy.get('tx-table').find('tr.tx-row').each(($el) => {
            cy.wrap($el).find('[data-cy="checkbox-utxo-actions"]').should('be.visible')
        })
        // Check that the manage PSBT button is working
        cy.get('@unsignedTxRow').find('.select-tx-img').click( {position: 'top'} )
        cy.get('tx-table').find('#manage-psbt-btn').should('be.visible').click()
        cy.contains("Here you can manage PSBTs") 
    })
})