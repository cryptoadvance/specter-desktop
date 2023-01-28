describe('Operating with an elements singlesig wallet', () => {
    if (Cypress.env("CI")) {
            
        it('Creates a single sig elements hot wallet', () => {
            cy.viewport(1300,660)
            cy.visit('/')
            cy.get('#node-switch-icon').click()
            cy.contains('Elements Node').click()

            // Delete Wallet if existing
            cy.deleteWallet("Elm Single Segwit Hot Wallet")
            cy.deleteWallet("Elm Single Nested Hot Wallet")

            cy.addHotDevice("Hot Elements Device 1","elements")
        
            // Segwit Wallet
            cy.addHotWallet("Elm Single Segwit Hot Wallet","Hot Elements Device 1", "elements", "segwit")
            
            // Nested Segwit Wallet
            cy.addHotWallet("Elm Single Nested Hot Wallet","Hot Elements Device 1", "elements", "nested_segwit")
        })

        it('send confidential transaction from segwit', () => {
            cy.viewport(1300,660)
            cy.visit('/')
            cy.contains("Elm Single Segwit Hot Wallet").click()

            cy.get('#fullbalance_amount').then(($div) => {
                const oldBalance = parseFloat($div.text())
                expect(oldBalance).to.be.gte(1.5)
                cy.createPsbt("el1qqdsywea5scrn7t9q83fd540pw447h0uae30pdp82rzgkl7yzvjz6gra9ls8qu6sslw4s0ck48we06zhqd6kwjy2quh69zwxwn", "Burn address","1.5")
                cy.get('#hot_elements_device_1_tx_sign_btn').click()
                cy.get('#hot_elements_device_1_hot_sign_btn').click()
                cy.get('#hot_enter_passphrase__submit').click()
                cy.get('#broadcast_local_btn').click()
                cy.get('#fullbalance_amount', { timeout: Cypress.env("broadcast_timeout") })
                .should(($div) => {
                    const newBalance = parseFloat($div.text())
                    expect(newBalance).to.be.lte(oldBalance - 1.5)
                })
            })
        })

        it('send unconfidential transaction from segwit', () => {
            cy.viewport(1300,660)
            cy.visit('/')
            cy.contains("Elm Single Segwit Hot Wallet").click()
            cy.get('#fullbalance_amount').then(($div) => {
                const oldBalance = parseFloat($div.text())
                expect(oldBalance).to.be.gte(1.5)
                cy.createPsbt("ert1q38la37ulxgc0uwt334he46eua7h8qagqnlm5phcqk7ntgv3x73cqjtr2fa", "Burn address","1.5")
                cy.get('#hot_elements_device_1_tx_sign_btn').click()
                cy.get('#hot_elements_device_1_hot_sign_btn').click()
                cy.get('#hot_enter_passphrase__submit').click()
                cy.get('#broadcast_local_btn').click()
                cy.get('#fullbalance_amount', { timeout: Cypress.env("broadcast_timeout") })
                .should(($div) => {
                    const newBalance = parseFloat($div.text())
                    expect(newBalance).to.be.lte(oldBalance - 1.5)
                })
            })
        })

        it('send confidential transaction from nested segwit', () => {
            cy.viewport(1300,660)
            cy.visit('/')
            cy.contains("Elm Single Nested Hot Wallet").click()

            cy.get('#fullbalance_amount').then(($div) => {
                const oldBalance = parseFloat($div.text())
                expect(oldBalance).to.be.gte(1.5)
                cy.createPsbt("el1qqdsywea5scrn7t9q83fd540pw447h0uae30pdp82rzgkl7yzvjz6gra9ls8qu6sslw4s0ck48we06zhqd6kwjy2quh69zwxwn", "Burn address","1.5")
                cy.get('#hot_elements_device_1_tx_sign_btn').click()
                cy.get('#hot_elements_device_1_hot_sign_btn').click()
                cy.get('#hot_enter_passphrase__submit').click()
                cy.get('#broadcast_local_btn').click()
                cy.get('#fullbalance_amount', { timeout: Cypress.env("broadcast_timeout") })
                .should(($div) => {
                    const newBalance = parseFloat($div.text())
                    expect(newBalance).to.be.lte(oldBalance - 1.5)
                })
            })
        })

        it('send unconfidential transaction from nested segwit', () => {
            cy.viewport(1300,660)
            cy.visit('/')
            cy.contains("Elm Single Nested Hot Wallet").click()
            cy.get('#fullbalance_amount').then(($div) => {
                const oldBalance = parseFloat($div.text())
                expect(oldBalance).to.be.gte(1.5)
                cy.createPsbt("ert1q38la37ulxgc0uwt334he46eua7h8qagqnlm5phcqk7ntgv3x73cqjtr2fa", "Burn address","1.5")
                cy.get('#hot_elements_device_1_tx_sign_btn').click()
                cy.get('#hot_elements_device_1_hot_sign_btn').click()
                cy.get('#hot_enter_passphrase__submit').click()
                cy.get('#broadcast_local_btn').click()
                cy.get('#fullbalance_amount', { timeout: Cypress.env("broadcast_timeout") })
                .should(($div) => {
                    const newBalance = parseFloat($div.text())
                    expect(newBalance).to.be.lte(oldBalance - 1.5)
                })
            })
        })

    }
})