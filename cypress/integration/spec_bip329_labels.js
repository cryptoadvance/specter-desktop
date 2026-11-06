// BIP-329 label interoperability: export/import of address labels and frozen
// state (spendable flag).
//
// Registered at the end of cypress-tests.json so it runs as part of the regular
// `./utils/test-cypress.sh run` suite. That suite is stateful and ordered, so the
// spec creates its own hot wallet instead of assuming a fresh home, and only
// connects the node when there is none yet (which is the case when running this
// spec on its own). Pages are visited by URL so the spec does not depend on the
// page it inherits from the previous spec.
describe('BIP-329 label interoperability', () => {
    const walletName = 'BIP329 wallet'
    const alias = walletName.toLowerCase().replace(/ /g, '_')
    const exportedFile = `./cypress/downloads/${alias}-labels.jsonl`
    const walletUrl = `/wallets/wallet/${alias}`
    let address
    let frozenOutpoint

    before(() => {
        Cypress.config('includeShadowDom', true)
        cy.visit('/')
        cy.get('body').then(($body) => {
            if ($body.find('[data-cy="no-core-connection"]').length) {
                cy.connect()
            }
        })
        // Hot wallet, funded by the node (addHotWallet mines into all wallets).
        cy.addHotDevice('BIP329 device', 'bitcoin')
        cy.addHotWallet(walletName, 'BIP329 device', 'bitcoin', 'segwit')
    })

    beforeEach(() => {
        cy.viewport('macbook-13')
    })

    it('Freezes a UTXO and labels an address', () => {
        // Freeze the first UTXO in the UTXO list (tx-table on the wallet page).
        cy.visit(`${walletUrl}/history/`)
        cy.get('[data-cy="utxo-list-btn"]').click()
        cy.get('tx-table').find('tx-row').should('have.length.at.least', 1)
        cy.get('tx-table').find('tx-row').eq(0).find('.select-tx-img').click({ position: 'top' })
        cy.get('tx-table').find('.freeze-tx-btn').click()
        cy.wait(500)
        cy.get('tx-table').find('tx-row').eq(0).find('.tx-row').should('have.class', 'frozen')

        // Label an address on the address overview.
        cy.visit(`${walletUrl}/addresses/`)
        cy.get('[data-cy="edit-label-btn"]').last().click()
        cy.get('[data-cy="edit-label-btn"]').last().type('{selectall}{backspace}')
        cy.get('[data-cy="edit-label-btn"]').last().type('Sparrow savings')
        cy.get('[data-cy="update-label-btn"]').last().click()
        cy.contains('Sparrow savings')
    })

    it('Exports BIP-329 labels from the wallet settings', () => {
        cy.visit(`${walletUrl}/settings/`)
        cy.get('#export_settings_tab_btn').click()
        cy.contains('Wallet labels (BIP-329)')
        cy.get('#export_bip329_labels').click()
        cy.readFile(exportedFile).then((content) => {
            const records = content.trim().split('\n').map((line) => JSON.parse(line))
            const addrRecord = records.find((r) => r.type === 'addr')
            const frozenRecord = records.find((r) => r.type === 'output' && r.spendable === false)
            expect(addrRecord.label).to.eq('Sparrow savings')
            expect(frozenRecord).to.exist
            address = addrRecord.ref
            frozenOutpoint = frozenRecord.ref
        })
    })

    it('Imports BIP-329 labels and spendable state', () => {
        cy.visit(`${walletUrl}/settings/`)
        cy.get('#advanced_settings_tab_btn').click()
        cy.contains('Import wallet labels (BIP-329, Electrum or Specter)')
        const payload = [
            JSON.stringify({ type: 'addr', ref: address, label: 'Imported from Sparrow' }),
            JSON.stringify({ type: 'output', ref: frozenOutpoint, spendable: true }),
        ].join('\n')
        cy.get('#textarea-content').type(payload, { parseSpecialCharSequences: false })
        cy.get('button[value="import_address_labels"]').click()
        cy.contains('Successfully imported 1 address labels and updated 1 frozen UTXOs.')

        // The new label shows up on the address list.
        cy.visit(`${walletUrl}/addresses/`)
        cy.contains('Imported from Sparrow')

        // And the UTXO list no longer marks the output as frozen.
        cy.visit(`${walletUrl}/history/`)
        cy.get('[data-cy="utxo-list-btn"]').click()
        cy.wait(500)
    })

    it('Exports the imported state again', () => {
        cy.visit(`${walletUrl}/settings/`)
        cy.get('#export_settings_tab_btn').click()
        cy.get('#export_bip329_labels').click()
        cy.readFile(exportedFile).then((content) => {
            const records = content.trim().split('\n').map((line) => JSON.parse(line))
            expect(records.find((r) => r.type === 'addr').label).to.eq('Imported from Sparrow')
            expect(records.filter((r) => r.spendable === false)).to.have.length(0)
        })
    })
})
