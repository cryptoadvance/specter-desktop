/// <reference types="cypress" />
// ***********************************************************
// This example plugins/index.js can be used to load plugins
//
// You can change the location of this file or turn off loading
// the plugins file with the 'pluginsFile' configuration option.
//
// You can read more here:
// https://on.cypress.io/plugins-guide
// ***********************************************************

// This function is called when a project is opened or re-opened (e.g. due to
// the project's config changing)

/**
 * @type {Cypress.PluginConfig}
 */
const fs = require('fs');

module.exports = (on, config) => {
  // `config` is the resolved Cypress config
  const conn_file = fs.readFileSync('btcd-conn.json');
  const conn = JSON.parse(conn_file);
  on('task', {
    'clear:specter-home': () => {
      console.log('Removing and recreating Specter-data-folder %s', conn["specter_data_folder"])
      const specter_home=conn["specter_data_folder"];
      var rimraf = require("rimraf");
      rimraf.sync(specter_home);
      fs.mkdirSync(specter_home);
      fs.mkdirSync(specter_home+"/devices");
      fs.mkdirSync(specter_home+"/wallets");
      return null
    }
  })

  on('task', {
    'node:mine': () => {
      // sending the bitcoind-process a signal SIGUSR1 (10) will cause mining towards all specter-wallets
      // See the signal-handler in bitcoind
      console.log('Sending SIGUSR1 to '+conn["pid"])
      process.kill(parseInt(conn["pid"], 10), 'SIGUSR1');
      return null
    }
  })



}
