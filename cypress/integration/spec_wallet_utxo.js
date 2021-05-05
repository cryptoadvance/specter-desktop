describe('Send transactions from wallets', () => {
    it('Freeze and unfreeze UTXO', () => {
        cy.viewport(1200,660)
        cy.task("node:mine")
        cy.wait(10000)
        cy.task("node:mine")
        cy.wait(10000)
        cy.task("node:mine")
        cy.wait(10000)

        cy.visit('/wallets/wallet/test_hot_wallet_1/history')

        cy.wait(1000)
        cy.get('tx-table').shadow().find('.utxo-view-btn').click()

        cy.get('tx-table').shadow().find('tx-row').each(($el, index, $list) => {
            cy.wrap($el).shadow().find('.tx-row').should('not.have.class', 'frozen')
            cy.wrap($el).shadow().find('.frozen-img').should('have.class', 'hidden')
        })

        // Freeze the UTXO
        cy.get('tx-table').shadow().find('tx-row').eq(0).shadow().find('.select-tx-img').click()
        cy.get('tx-table').shadow().find('.freeze-tx-btn').click()

        cy.get('tx-table').shadow().find('tx-row').each(($el, index, $list) => {
            if (index == 0) {
                cy.wrap($el).shadow().find('.tx-row').should('have.class', 'frozen')
                cy.wrap($el).shadow().find('.frozen-img').should('not.have.class', 'hidden')
            } else {
                cy.wrap($el).shadow().find('.tx-row').should('not.have.class', 'frozen')
                cy.wrap($el).shadow().find('.frozen-img').should('have.class', 'hidden')
            }   
        })

        // Test freeze UTXO can't be spend, and unfreeze works for coin selection option
        cy.get('tx-table').shadow().find('tx-row').eq(0).shadow().find('.select-tx-img').click()
        cy.get('tx-table').shadow().find('tx-row').eq(1).shadow().find('.select-tx-img').click()
        cy.get('tx-table').shadow().find('tx-row').eq(3).shadow().find('.select-tx-img').click()
        cy.get('tx-table').shadow().find('.compose-tx-btn').click()

        // cy.get('#coin_selection_table').find('tr').eq(0).find('.coin_select_checkbox').should('be.checked')
        cy.get('.coin_select_checkbox[checked]').should('have.length', 2);

        cy.get('.coin_select_checkbox').eq(0).should('be.checked')
        cy.get('.coin_select_checkbox').eq(1).should('not.be.checked')
        cy.get('.coin_select_checkbox').eq(2).should('be.checked')

        // Unfreeze the UTXO
        cy.get('#btn_transactions').click()
        cy.wait(1000)
        cy.get('tx-table').shadow().find('.utxo-view-btn').click()

        cy.get('tx-table').shadow().find('tx-row').eq(0).shadow().find('.select-tx-img').click()
        cy.get('tx-table').shadow().find('.freeze-tx-btn').click()

        cy.get('tx-table').shadow().find('tx-row').each(($el, index, $list) => {
            cy.wrap($el).shadow().find('.tx-row').should('not.have.class', 'frozen')
            cy.wrap($el).shadow().find('.frozen-img').should('have.class', 'hidden')
        })

        // Ensure selection of unfreeze now works
        cy.get('tx-table').shadow().find('tx-row').eq(0).shadow().find('.select-tx-img').click()
        cy.get('tx-table').shadow().find('tx-row').eq(1).shadow().find('.select-tx-img').click()
        cy.get('tx-table').shadow().find('tx-row').eq(3).shadow().find('.select-tx-img').click()
        cy.get('tx-table').shadow().find('.compose-tx-btn').click()

        cy.get('.coin_select_checkbox[checked]').should('have.length', 3);

        cy.get('.coin_select_checkbox').eq(0).should('be.checked')
        cy.get('.coin_select_checkbox').eq(1).should('be.checked')
        cy.get('.coin_select_checkbox').eq(2).should('not.be.checked')
        cy.get('.coin_select_checkbox').eq(3).should('be.checked')
    })
})