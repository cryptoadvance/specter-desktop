describe('Operating with an elements multisig wallet', () => {
    // 4000ms was often not enough for waiting a elm-transaction
    // So let's try double as much:
    const broadcast_timeout = 8000
    
    it('Creates an two elements multisig hot wallets (segwit/nested) both 2/3', () => {
        cy.viewport(1200,660)
        cy.visit('/')
        cy.get('#node-switch-icon').click()
        cy.get('#elements_node-select-node-form > .item > div').click()
        
        // Delete Wallet if existing
        cy.deleteWallet("Elm Multi Segwit Wallet")
        cy.deleteWallet("Elm Multi Nested Wallet")

        // Create the Hot Element Wallets
        cy.addHotDevice("Hot Elements Device 2","elements")
        cy.addHotDevice("Hot Elements Device 3","elements")
        cy.addHotDevice("Hot Elements Device 4","elements")

        // Create Segwit multisig wallet
        cy.get('#btn_new_wallet').click()
        cy.get('[href="./multisig/"]').click()
        cy.get('#hot_elements_device_2').click()
        cy.get('#hot_elements_device_3').click()
        cy.get('#hot_elements_device_4').click()
        cy.get('#submit-device').click()
        cy.get('#wallet_name').type("Elm Multi Segwit Wallet")
        cy.get(':nth-child(9) > .inline').clear()
        // 2 of 2
        cy.get(':nth-child(9) > .inline').type("2")
        // submit
        cy.get('#keysform > .centered').click()
        // Cancel-button (no pdf download)
        cy.get('#page_overlay_popup_cancel_button').click()
        //Get some funds
        cy.mine2wallet("elm")


        // Create Nested multisig wallet
        cy.get('#btn_new_wallet').click()
        cy.get('[href="./multisig/"]').click()
        cy.get('#hot_elements_device_2').click()
        cy.get('#hot_elements_device_3').click()
        cy.get('#hot_elements_device_4').click()
        cy.get('#submit-device').click()
        cy.get(':nth-child(1) > #type_nested_segwit_btn') // Nested!!
        cy.get('#wallet_name').type("Elm Multi Nested Wallet")
        cy.get(':nth-child(9) > .inline').clear()
        // 2 of 2
        cy.get(':nth-child(9) > .inline').type("2")
        // submit
        cy.get('#keysform > .centered').click()
        // Cancel-button (no pdf download)
        cy.get('#page_overlay_popup_cancel_button').click()
        //Get some funds
        cy.mine2wallet("elm")
    }) 
        
    it('Spending to a Confidential address from segwit', () => {
        cy.viewport(1200,660)
        cy.visit('/')
        // spend the money again
        cy.contains("Elm Multi Segwit Wallet").click()

        cy.get('#fullbalance_amount').then(($div) => {
            const oldBalance = parseFloat($div.text())
            expect(oldBalance).to.be.gte(1.5)
            cy.createPsbt("el1qqdsywea5scrn7t9q83fd540pw447h0uae30pdp82rzgkl7yzvjz6gra9ls8qu6sslw4s0ck48we06zhqd6kwjy2quh69zwxwn", "Burn address","1.5")
            
            
            cy.get('#hot_elements_device_2_tx_sign_btn').click()
            cy.get('#hot_elements_device_2_hot_sign_btn').click()
            cy.get('#hot_enter_passphrase__submit').click()
            cy.get('#hot_elements_device_3_tx_sign_btn').click()
            cy.get('#hot_elements_device_3_hot_sign_btn').click()
            cy.get('#hot_enter_passphrase__submit').click()
            // cy.get('#broadcast_local_btn').click()
            // There is a bug as the first device doesn't seem to have signed and so we can't send the tx just right from here
            // 2 more clicks until to get to the send button
            cy.get('#btn_send').click()
            cy.get('.row > :nth-child(1) > .btn').click()
            cy.get('#send_tx_btn').click()
            cy.get('#broadcast_local_btn').click()
            // gets redirected to "transactions"

            cy.get('#fullbalance_amount', { timeout: broadcast_timeout })
            .should(($div) => {
                const newBalance = parseFloat($div.text())
                expect(newBalance).to.be.lte(oldBalance - 1.5)
            })
        })

        // Workaround: Transaction does not disappear
        cy.get('#btn_send').click()
        // The "delete" button in the first psbt
        cy.get('.row > :nth-child(2) > .btn').click()


    })

    it('Spending to a Unconfidential address from segwit', () => {

        cy.viewport(1200,660)
        cy.visit('/')
        // spend the money again
        cy.contains("Elm Multi Segwit Wallet").click()

        cy.get('#fullbalance_amount').then(($div) => {
            const oldBalance = parseFloat($div.text())
            expect(oldBalance).to.be.gte(1.5)
            cy.createPsbt("ert1q38la37ulxgc0uwt334he46eua7h8qagqnlm5phcqk7ntgv3x73cqjtr2fa", "unconf Burn address","1.5")
            
            
            cy.get('#hot_elements_device_2_tx_sign_btn').click()
            cy.get('#hot_elements_device_2_hot_sign_btn').click()
            cy.get('#hot_enter_passphrase__submit').click()
            cy.get('#hot_elements_device_3_tx_sign_btn').click()
            cy.get('#hot_elements_device_3_hot_sign_btn').click()
            cy.get('#hot_enter_passphrase__submit').click()
            // cy.get('#broadcast_local_btn').click()
            // There is a bug as the first device doesn't seem to have signed and so we can't send the tx just right from here
            // 2 more clicks until to get to the send button
            cy.get('#btn_send').click()
            cy.get('.row > :nth-child(1) > .btn').click()
            cy.get('#send_tx_btn').click()
            cy.get('#broadcast_local_btn').click()
            // gets redirected to "transactions"

            cy.get('#fullbalance_amount', { timeout: broadcast_timeout })
            .should(($div) => {
                const newBalance = parseFloat($div.text())
                expect(newBalance).to.be.lte(oldBalance - 1.5)
            })
        })

        // Workaround: Transaction does not disappear
        // Strange bug, not needed here
        // cy.get('#btn_send').click()
        // The "delete" button in the first psbt
        // cy.get('.row > :nth-child(2) > .btn').click()

    })

    it('Spending to a Confidential address from nested', () => {
        cy.viewport(1200,660)
        cy.visit('/')
        // spend the money again
        cy.contains("Elm Multi Nested Wallet").click()

        cy.get('#fullbalance_amount').then(($div) => {
            const oldBalance = parseFloat($div.text())
            expect(oldBalance).to.be.gte(1.5)
            cy.createPsbt("el1qqdsywea5scrn7t9q83fd540pw447h0uae30pdp82rzgkl7yzvjz6gra9ls8qu6sslw4s0ck48we06zhqd6kwjy2quh69zwxwn", "Burn address","1.5")
            
            
            cy.get('#hot_elements_device_2_tx_sign_btn').click()
            cy.get('#hot_elements_device_2_hot_sign_btn').click()
            cy.get('#hot_enter_passphrase__submit').click()
            cy.get('#hot_elements_device_3_tx_sign_btn').click()
            cy.get('#hot_elements_device_3_hot_sign_btn').click()
            cy.get('#hot_enter_passphrase__submit').click()
            // cy.get('#broadcast_local_btn').click()
            // There is a bug as the first device doesn't seem to have signed and so we can't send the tx just right from here
            // 2 more clicks until to get to the send button
            cy.get('#btn_send').click()
            cy.get('.row > :nth-child(1) > .btn').click()
            cy.get('#send_tx_btn').click()
            cy.get('#broadcast_local_btn').click()
            // gets redirected to "transactions"

            cy.get('#fullbalance_amount', { timeout: broadcast_timeout })
            .should(($div) => {
                const newBalance = parseFloat($div.text())
                expect(newBalance).to.be.lte(oldBalance - 1.5)
            })
        })

        // Workaround: Transaction does not disappear
        cy.get('#btn_send').click()
        // The "delete" button in the first psbt
        cy.get('.row > :nth-child(2) > .btn').click()


    })

    it('Spending to a Unconfidential address from nested', () => {

        cy.viewport(1200,660)
        cy.visit('/')
        // spend the money again
        cy.contains("Elm Multi Nested Wallet").click()

        cy.get('#fullbalance_amount').then(($div) => {
            const oldBalance = parseFloat($div.text())
            expect(oldBalance).to.be.gte(1.5)
            cy.createPsbt("ert1q38la37ulxgc0uwt334he46eua7h8qagqnlm5phcqk7ntgv3x73cqjtr2fa", "unconf Burn address","1.5")
            
            
            cy.get('#hot_elements_device_2_tx_sign_btn').click()
            cy.get('#hot_elements_device_2_hot_sign_btn').click()
            cy.get('#hot_enter_passphrase__submit').click()
            cy.get('#hot_elements_device_3_tx_sign_btn').click()
            cy.get('#hot_elements_device_3_hot_sign_btn').click()
            cy.get('#hot_enter_passphrase__submit').click()
            // cy.get('#broadcast_local_btn').click()
            // There is a bug as the first device doesn't seem to have signed and so we can't send the tx just right from here
            // 2 more clicks until to get to the send button
            cy.get('#btn_send').click()
            cy.get('.row > :nth-child(1) > .btn').click()
            cy.get('#send_tx_btn').click()
            cy.get('#broadcast_local_btn').click()
            // gets redirected to "transactions"
            cy.get('#fullbalance_amount', { timeout: broadcast_timeout})
            .should(($div) => {
                const newBalance = parseFloat($div.text())
                expect(newBalance).to.be.lte(oldBalance - 1.5)
            })
        })

        // Workaround: Transaction does not disappear
        // Strange bug, not needed here
        // cy.get('#btn_send').click()
        // The "delete" button in the first psbt
        // cy.get('.row > :nth-child(2) > .btn').click()

    })
})