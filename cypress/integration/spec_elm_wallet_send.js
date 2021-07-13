describe('Send transactions from elements wallets', () => {
    it('Creates a single sig elements hot wallet on specter and send transaction', () => {
        cy.viewport(1200,660)
        cy.visit('/')
        cy.get('#node-switch-icon').click()
        cy.get('#elements_node-select-node-form > .item > div').click()
        // empty so far
        cy.addHotDevice("Hot Elements Device 1","elements")
        //cy.addHotWallet("Test Elements Hot Wallet","elements")
        cy.addHotWallet("Test Elements Hot Wallet 1","elements")

        cy.get('#btn_send').click()
        cy.get('#address_0').type("el1qqdsywea5scrn7t9q83fd540pw447h0uae30pdp82rzgkl7yzvjz6gra9ls8qu6sslw4s0ck48we06zhqd6kwjy2quh69zwxwn")
        cy.get('#label_0').type("Burn address")
        //cy.get('#send_max_0').click()
        cy.get('#amount_0').type("1.5")
        cy.get('#create_psbt_btn').click()
        cy.get('#hot_elements_device_1_tx_sign_btn').click()
        cy.get('#hot_elements_device_1_hot_sign_btn').click()
        cy.get('#hot_enter_passphrase__submit').click()
        cy.get('#broadcast_local_btn').click()
        cy.get('#fullbalance_amount')
        .should(($div) => {
            const n = parseFloat($div.text())
            expect(n).to.be.equals(18.49999739)
        })
    })
})