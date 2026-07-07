const { defineConfig } = require('cypress')
const setupNodeEvents = require('./cypress/plugins')

const specPattern = [
  'cypress/integration/spec_empty_specter_home.js',
  'cypress/integration/spec_connections.js',
  'cypress/integration/spec_devices.js',
  'cypress/integration/spec_ghost_machine.js',
  'cypress/integration/spec_fees.js',
  'cypress/integration/spec_rescan.js',
  'cypress/integration/spec_qr_signing.js',
  'cypress/integration/spec_labeling.js',
  'cypress/integration/spec_balances_amounts.js',
  'cypress/integration/spec_wallet_send.js',
  'cypress/integration/spec_wallet_utxo.js',
  'cypress/integration/spec_plugins.js',
]

module.exports = defineConfig({
  e2e: {
    baseUrl: 'http://localhost:25444',
    specPattern,
    supportFile: 'cypress/support/index.js',
    testIsolation: false,
    setupNodeEvents,
  },
  env: {
    broadcast_timeout: 8000,
  },
  includeShadowDom: false,
  reporter: 'junit',
  reporterOptions: {
    mochaFile: 'cypresstest-output.xml',
    toConsole: true,
  },
  retries: {
    runMode: 1,
    openMode: 0,
  },
})
