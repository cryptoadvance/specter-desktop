describe('Operating with an Elements multisig wallet', () => {    
    if (Cypress.env("CI")) {

        it('Creates two (segwit/nested) Elements multisig (2/3) hot wallets', () => {

            cy.viewport(1200,660)
            cy.visit('/')
            cy.get('#node-switch-icon').click()
            cy.contains('Elements Node').click()
            
            // Delete wallets if existing
            cy.deleteWallet("Elm Multi Segwit Wallet")
            cy.deleteWallet("Elm Multi Nested Wallet")

            // Add devices for multisig
            cy.addHotDevice("Elm Multisig Device 1","elements")
            cy.addHotDevice("Elm Multisig Device 2","elements")
            cy.addHotDevice("Elm Multisig Device 3","elements")

            // Create Segwit multisig wallet
            cy.get('#btn_new_wallet').click()
            cy.get('[href="./multisig/"]').click()
            cy.get('#elm_multisig_device_1').click()
            cy.get('#elm_multisig_device_2').click()
            cy.get('#elm_multisig_device_3').click()
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
            cy.get('#elm_multisig_device_1').click()
            cy.get('#elm_multisig_device_2').click()
            cy.get('#elm_multisig_device_3').click()
            cy.get('#submit-device').click()
            // Switch to Nested Segwit
            cy.get('#type_nested_segwit_btn').click()
            cy.get('#wallet_name').type("Elm Multi Nested Wallet")
            // 2 of 3
            cy.get(':nth-child(9) > .inline').clear()
            cy.get(':nth-child(9) > .inline').type("2")
            // submit
            cy.get('#keysform > .centered').click()
            // Click cancel (no pdf download)
            cy.get('#page_overlay_popup_cancel_button').click()
            // Get some funds
            cy.mine2wallet("elm")
        }) 
            
        it('Spending to a confidential address from segwit', () => {
            cy.viewport(1200,660)
            cy.visit('/')
            cy.contains("Elm Multi Segwit Wallet").click()
            
            cy.get('#fullbalance_amount', { timeout: Cypress.env("broadcast_timeout") }).then(($div) => {
                // Create PSBT
                const oldBalance = parseFloat($div.text())
                expect(oldBalance).to.be.gte(1.5)
                cy.createPsbt("el1qqdsywea5scrn7t9q83fd540pw447h0uae30pdp82rzgkl7yzvjz6gra9ls8qu6sslw4s0ck48we06zhqd6kwjy2quh69zwxwn", "Burn address","1.5")  
                
                // First signature
                cy.get('#elm_multisig_device_1_tx_sign_btn').click()
                cy.get('#elm_multisig_device_1_hot_sign_btn').click()
                cy.contains('Sign transaction').click()
                
                // Second signature
                cy.get('#elm_multisig_device_2_tx_sign_btn').click()
                cy.get('#elm_multisig_device_2_hot_sign_btn').click()
                cy.contains('Sign transaction').click()
                
                // Send the tx
                cy.get('#broadcast_local_btn').click()
                
                // Redirect to "transactions", check balance there
                cy.get('#fullbalance_amount', { timeout: Cypress.env("broadcast_timeout") })
                .should(($div) => {
                    const newBalance = parseFloat($div.text())
                    expect(newBalance).to.be.lte(oldBalance - 1.5)
                })
            })
        })

        it('Spending to an unnconfidential address from segwit', () => {
            cy.viewport(1200,660)
            cy.visit('/')
            cy.contains("Elm Multi Segwit Wallet").click()

            cy.get('#fullbalance_amount', { timeout: Cypress.env("broadcast_timeout") }).then(($div) => {
                // Create PSBT
                const oldBalance = parseFloat($div.text())
                expect(oldBalance).to.be.gte(1.5)
                cy.createPsbt("ert1q38la37ulxgc0uwt334he46eua7h8qagqnlm5phcqk7ntgv3x73cqjtr2fa", "unconf Burn address","1.5")

                // First signature
                cy.get('#elm_multisig_device_1_tx_sign_btn').click()
                cy.get('#elm_multisig_device_1_hot_sign_btn').click()
                cy.contains('Sign transaction').click()
                
                // Second signature
                cy.get('#elm_multisig_device_2_tx_sign_btn').click()
                cy.get('#elm_multisig_device_2_hot_sign_btn').click()
                cy.contains('Sign transaction').click()

                // Send tx
                cy.get('#broadcast_local_btn').click()
                
                // Redirect to "transactions", check balance there
                cy.get('#fullbalance_amount', { timeout: Cypress.env("broadcast_timeout") })
                .should(($div) => {
                    const newBalance = parseFloat($div.text())
                    expect(newBalance).to.be.lte(oldBalance - 1.5)
                })
            })
        })

        it('Spending to a confidential address from nested', () => {
            cy.viewport(1200,660)
            cy.visit('/')
            cy.contains("Elm Multi Nested Wallet").click()

            cy.get('#fullbalance_amount', { timeout: Cypress.env("broadcast_timeout") }).then(($div) => {
                // Create PSBT
                const oldBalance = parseFloat($div.text())
                expect(oldBalance).to.be.gte(1.5)
                cy.createPsbt("el1qqdsywea5scrn7t9q83fd540pw447h0uae30pdp82rzgkl7yzvjz6gra9ls8qu6sslw4s0ck48we06zhqd6kwjy2quh69zwxwn", "Burn address","1.5")
                
                // First signature
                cy.get('#elm_multisig_device_1_tx_sign_btn').click()
                cy.get('#elm_multisig_device_1_hot_sign_btn').click()
                cy.contains('Sign transaction').click()
                
                // Second signature
                cy.get('#elm_multisig_device_2_tx_sign_btn').click()
                cy.get('#elm_multisig_device_2_hot_sign_btn').click()
                cy.contains('Sign transaction').click()
                
                // Send the tx
                cy.get('#broadcast_local_btn').click()

                // Redirect to "transactions", check balance there
                cy.get('#fullbalance_amount', { timeout: Cypress.env("broadcast_timeout") })
                .should(($div) => {
                    const newBalance = parseFloat($div.text())
                    expect(newBalance).to.be.lte(oldBalance - 1.5)
                })
            })
        })

        it('Spending to a unconfidential address from nested', () => {
            cy.viewport(1200,660)
            cy.visit('/')
            cy.contains("Elm Multi Nested Wallet").click()

            cy.get('#fullbalance_amount', { timeout: Cypress.env("broadcast_timeout") }).then(($div) => {
                // Create PSBT
                const oldBalance = parseFloat($div.text())
                expect(oldBalance).to.be.gte(1.5)
                cy.createPsbt("ert1q38la37ulxgc0uwt334he46eua7h8qagqnlm5phcqk7ntgv3x73cqjtr2fa", "unconf Burn address","1.5")
                
                // First signature
                cy.get('#elm_multisig_device_1_tx_sign_btn').click()
                cy.get('#elm_multisig_device_1_hot_sign_btn').click()
                cy.contains('Sign transaction').click()
                
                // Second signature
                cy.get('#elm_multisig_device_2_tx_sign_btn').click()
                cy.get('#elm_multisig_device_2_hot_sign_btn').click()
                cy.contains('Sign transaction').click()
                
                // Send the tx
                cy.get('#broadcast_local_btn').click()

                // Redirect to "transactions", check balance there
                cy.get('#fullbalance_amount', { timeout: Cypress.env("broadcast_timeout") })
                .should(($div) => {
                    const newBalance = parseFloat($div.text())
                    expect(newBalance).to.be.lte(oldBalance - 1.5)
                })
            })
        })
    }
})