describe('Test the actions in UTXO list', () => {
    
    before(() => {
        Cypress.config('includeShadowDom', true)
        const device_name = "UTXO device"
        const wallet_name = "UTXO wallet"
        var wallet_name_ref = wallet_name.toLowerCase().replace(/ /g,"_")
        cy.viewport(1200,660)
        cy.visit('/')
        cy.get('#toggle_devices_list').click()
        cy.addHotDevice(device_name, "bitcoin")
        cy.addHotWallet(wallet_name, device_name, "bitcoin", "segwit")
        cy.get('#amount_total').then(($span) => {
            const balance = parseFloat($span.text())
            if (balance <= 20) {
                cy.log("balance " + balance + " too low. Mining!")
                cy.mine2wallet("btc")
                cy.mine2wallet("btc")
                cy.mine2wallet("btc")
                cy.mine2wallet("btc")
                // We are having 5 UTXO in the end
            }
        })
    })

    // Keeps the session cookie alive, Cypress by default clears all cookies before each test
    beforeEach(() => {
        Cypress.Cookies.preserveOnce('session')
    })

    it('Freezing', () => {
        cy.contains("UTXO wallet").click()
        cy.get('tx-table').find('.utxo-view-btn').click({ force: true })
        cy.wait(500)
        // Freeze 3 UTXOs 
        cy.log("Freeze 3 UTXO")
        cy.get('tx-table').find('tx-row').eq(0).find('.select-tx-img').click( {position: 'top'} )
        cy.get('tx-table').find('tx-row').eq(0).find('.select-tx-value').invoke('attr', 'value').should('eq', 'true') // Check whether click worked
        cy.wait(100)
        cy.get('tx-table').find('tx-row').eq(1).find('.select-tx-img').click( {position: 'top'} )
        cy.get('tx-table').find('tx-row').eq(1).find('.select-tx-value').invoke('attr', 'value').should('eq', 'true') 
        cy.wait(100)
        cy.get('tx-table').find('tx-row').eq(3).find('.select-tx-img').click( {position: 'top'} )
        cy.get('tx-table').find('tx-row').eq(3).find('.select-tx-value').invoke('attr', 'value').should('eq', 'true') 
        cy.wait(100)
        cy.get('tx-table').find('.freeze-tx-btn').click()
        cy.wait(500)
        // We should have 3 frozen outputs now, let's check that
        cy.log("Check whether we have 3 frozen outputs")
        cy.get('tx-table').find('tx-row').each(($el, index, $list) => {
            if (index == 0 || index == 1 || index == 3) {
                cy.wrap($el).find('.tx-row').should('have.class', 'frozen')
                cy.wrap($el).find('.frozen-img').should('not.have.class', 'hidden')
            } else {
                cy.wrap($el).find('.tx-row').should('not.have.class', 'frozen')
                cy.wrap($el).find('.frozen-img').should('have.class', 'hidden')
            }   
        })
        // Check that we can't create a transaction when a frozen UTXO is selected ...
        cy.log("Check that we can't create a transaction when frozen UTXO is selected")
        cy.get('tx-table').find('tx-row').eq(2).find('.select-tx-img').click( {position: 'top'} )
        cy.get('tx-table').find('tx-row').eq(0).find('.select-tx-img').click( {position: 'top'} )
        cy.get('tx-table').find('.compose-tx-btn').should('be.hidden')
        // ... and that the checkboxes disappear for non-frozen UTXO and get unticked
        cy.log("... and that the checkboxes disappear for non-frozen UTXO and get unticked")
        cy.get('tx-table').find('tx-row').eq(2).find('.select-tx-img').should('be.hidden')
        cy.get('tx-table').find('tx-row').eq(2).find('.select-tx-img').should('have.attr', 'src').and('contain', 'untick')
        cy.get('tx-table').find('tx-row').eq(4).find('.select-tx-img').should('be.hidden')
        cy.get('tx-table').find('tx-row').eq(4).find('.select-tx-img').should('have.attr', 'src').and('contain', 'untick')
        // Unselect the first UTXO again and check that all checkboxes are visible and none are selected
        cy.log("Unselect the first UTXO again and check that all checkboxes are visible and none are selected")
        cy.get('tx-table').find('tx-row').eq(0).find('.select-tx-img').click( {position: 'top'} )
        cy.wait(100)
        cy.get('tx-table').find('tx-row').each(($el, index, $list) => {
            cy.wrap($el).find('.tx-row').find('.select-tx-img').should('not.be.hidden').should('have.attr', 'src').and('contain', 'untick')
        })
    })

    it('Creating a transaction', () => {
        // Make a transaction with the third and forth UTXO
        cy.log("Make a transaction with the third and forth UTXO")
        // Unfreeze necessary for the forth UTXO
        cy.get('tx-table').find('tx-row').eq(3).find('.select-tx-img').click( {position: 'top'} )
        cy.wait(100)
        cy.get('tx-table').find('.freeze-tx-btn').click()
        cy.wait(200)
        cy.get('tx-table').find('tx-row').eq(2).find('.select-tx-img').click( {position: 'top'} );
        cy.get('tx-table').find('tx-row').eq(2).find('.select-tx-value').invoke('attr', 'value').should('eq', 'true') // Check that the click flow is (still) in order
        cy.get('tx-table').find('tx-row').eq(3).find('.select-tx-img').click( {position: 'top'} )
        cy.get('tx-table').find('tx-row').eq(3).find('.select-tx-value').invoke('attr', 'value').should('eq', 'true')
        cy.wait(100)
        cy.get('tx-table').find('.compose-tx-btn').should('not.be.hidden')
        cy.get('tx-table').find('.compose-tx-btn').click()
        // Switch to coin selection, check that the right amount of coins are preselected in the coin selection
        cy.log("Switch to coin selection, check that the right amount of coins are preselected in the coin selection")
        cy.get('.coinselect-hidden').should('have.length', 2);
    })

    it('Managing unsigned transactions', () => {
        // Make an unsigned tx
        cy.get('#recipient_0').find('#address').type("bcrt1qvtdx75y4554ngrq6aff3xdqnvjhmct5wck95qs") // address from "Ghost wallet"
        cy.get('#recipient_0').get('#send_max').click()
        cy.get('#create_psbt_btn').click()
        // Check the labeling of the unsigned UTXO
        cy.log("Check the labeling of the unsigned UTXO")
        cy.get('#btn_transactions').click()
        cy.wait(1000)
        cy.get('tx-table').find('.utxo-view-btn').click()
        cy.get('tx-table').find('tx-row').eq(2).find('#column-category').should('contain', 'Unsigned')
        cy.get('tx-table').find('tx-row').eq(3).find('#column-category').should('contain', 'Unsigned')
        // Check that only the two checkboxes of the unsigned UTXO are visible
        cy.log("Check that only the two checkboxes of the unsigned UTXO are visible")
        cy.get('tx-table').find('tx-row').eq(2).find('.select-tx-img').click( {position: 'top'} )
        cy.wait(200)
        cy.get('tx-table').find('tx-row').each(($el, index, $list) => {
            if (index == 0 || index == 1) {
            cy.wrap($el).find('.tx-row').find('.select-tx-img').should('be.hidden').should('have.attr', 'src').and('contain', 'untick')
            }   
        })
        // Unselect the third UTXO again and check that all checkboxes are visible and none are selected
        cy.log("Unselect the third UTXO again and check that all checkboxes are visible and none are selected")
        cy.get('tx-table').find('tx-row').eq(2).find('.select-tx-img').click( {position: 'top'} )
        cy.get('tx-table').find('tx-row').eq(2).find('.select-tx-value').invoke('attr', 'value').should('eq', '')
        cy.wait(100)
        cy.get('tx-table').find('tx-row').each(($el, index, $list) => {
            cy.wrap($el).find('.tx-row').find('.select-tx-img').should('not.be.hidden')
        })
        // Select a normal UTXO, select an unsigned UTXO and then unselect the unsigned again
        cy.log("Select a normal UTXO, select an unsigned UTXO and then unselect the unsigned again")
        cy.get('tx-table').find('tx-row').eq(4).find('.select-tx-img').click( {position: 'top'} )
        cy.get('tx-table').find('tx-row').eq(4).find('.select-tx-value').invoke('attr', 'value').should('eq', 'true')
        cy.wait(100)
        cy.get('tx-table').find('tx-row').eq(3).find('.select-tx-img').click( {position: 'top'} )
        cy.get('tx-table').find('tx-row').eq(3).find('.select-tx-value').invoke('attr', 'value').should('eq', 'true')
        cy.wait(100)
        cy.get('tx-table').find('tx-row').eq(3).find('.select-tx-img').click( {position: 'top'} )
        cy.get('tx-table').find('tx-row').eq(3).find('.select-tx-value').invoke('attr', 'value').should('eq', '')
        cy.wait(100)
        // Check that all checkboxes are visible again and none are selected
        cy.get('tx-table').find('tx-row').each(($el, index, $list) => {
            cy.wrap($el).find('.tx-row').find('.select-tx-img').should('not.be.hidden').should('have.attr', 'src').and('contain', 'untick')
        })
        // Check that the manage PSBT button is working
        cy.get('tx-table').find('tx-row').eq(2).find('.select-tx-img').click( {position: 'top'} )
        cy.wait(100)
        cy.get('tx-table').find('#manage-psbt-btn').should('not.be.hidden').click()
        cy.wait(200)
        cy.contains("Here you can manage PSBTs") 
    })
})