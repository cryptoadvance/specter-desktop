describe('Operating with an elements multisig wallet', () => {
    it('Creates an elements multisig hot wallet 2/3', () => {
        cy.viewport(1200,660)
        cy.visit('/')
        cy.get('#node-switch-icon').click()
        cy.get('#elements_node-select-node-form > .item > div').click()
        
        // Delete Wallet if existing
        cy.deleteWallet("Elm Multi Segwit Wallet")

        // Create the Hot Element Wallets
        cy.addHotDevice("Hot Elements Device 2","elements")
        cy.addHotDevice("Hot Elements Device 3","elements")
        cy.addHotDevice("Hot Elements Device 4","elements")

        // Create multisig wallet
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

        // Fund it and check the balance
        cy.get('#btn_transactions').click()
        cy.task("elm:mine")
        cy.wait(4000)
        cy.reload()
        cy.get('#fullbalance_amount')
            .should(($div) => {
              const n = parseFloat($div.text())
              expect(n).to.be.gt(0).and.be.lte(50)
            }
        )
    }) 
        
    it('Spending to a Confidential address', () => {
        cy.viewport(1200,660)
        cy.visit('/')
        // spend the money again
        cy.get('#btn_send').click()

        cy.get('#address_0').type("el1qqdsywea5scrn7t9q83fd540pw447h0uae30pdp82rzgkl7yzvjz6gra9ls8qu6sslw4s0ck48we06zhqd6kwjy2quh69zwxwn")
        cy.get('#label_0').type("Burn address")
        //cy.get('#send_max_0').click()
        cy.get('#amount_0').type("1.5")
        cy.get('#create_psbt_btn').click()        //cy.addHotWallet("Test Elements Hot Wallet","elements")
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
        cy.get('#fullbalance_amount')
        .should(($div) => {
            const n = parseFloat($div.text())
            expect(n).to.be.lt(19)
        })

        // Workaround: Transaction does not disappear
        cy.get('#btn_send').click()
        // The "delete" button in the first psbt
        cy.get('.row > :nth-child(2) > .btn').click()


    })

    it('Spending to a Unconfidential address', () => {
        cy.viewport(1200,660)
        cy.visit('/')
        // spend the money again
        cy.get('#btn_send').click()

        cy.get('#address_0').type("ert1q38la37ulxgc0uwt334he46eua7h8qagqnlm5phcqk7ntgv3x73cqjtr2fa")
        cy.get('#label_0').type("Burn address")
        //cy.get('#send_max_0').click()
        cy.get('#amount_0').type("1.5")
        cy.get('#create_psbt_btn').click()        //cy.addHotWallet("Test Elements Hot Wallet","elements")
        cy.get('#hot_elements_device_2_tx_sign_btn').click()
        cy.get('#hot_elements_device_2_hot_sign_btn').click()
        cy.get('#hot_enter_passphrase__submit').click()
        cy.get('#hot_elements_device_3_tx_sign_btn').click()
        cy.get('#hot_elements_device_3_hot_sign_btn').click()
        cy.get('#hot_enter_passphrase__submit').click()

        cy.get('#broadcast_local_btn').click()
        cy.get('#fullbalance_amount')
        .should(($div) => {
            const n = parseFloat($div.text())
            expect(n).to.be.lt(17)
        })
    })
})