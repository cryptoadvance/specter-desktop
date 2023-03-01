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
  const btc_conn_file = fs.readFileSync('btcd-conn.json');
  const btc_conn = JSON.parse(btc_conn_file);
  const elm_conn_file_path = 'elmd-conn.json';
  // Elementsd is not always started
  let elm_conn
  if (fs.existsSync(elm_conn_file_path)) {
    const elm_conn_file = fs.readFileSync(elm_conn_file_path);
    elm_conn = JSON.parse(elm_conn_file);
  }
  else {
    elm_conn = ''
  }

  on('task', {
    'clear:specter-home': () => {
      console.log('Removing and recreating Specter-data-folder %s', btc_conn["specter_data_folder"])
      const specter_home=btc_conn["specter_data_folder"];
      var rimraf = require("rimraf");
      rimraf.sync(specter_home);
      fs.mkdirSync(specter_home);
      fs.mkdirSync(specter_home+"/nodes");
      fs.mkdirSync(specter_home+"/devices");
      fs.mkdirSync(specter_home+"/wallets");
      return null
    }
  })

  on('task', {
    'delete:elements-hotwallet': (name) => {
      console.log('connection details: %s', elm_conn)
      const elements_data_dir=elm_conn["elements_data_dir"];
      var rimraf = require("rimraf");
      console.log('Removing all wallets in %s', elements_data_dir+"/elreg/wallets/specter123456_hotstorage")
      rimraf.sync(elements_data_dir+"/elreg/wallets/specter123456_hotstorage");
      return null
    }
  })

  on('task', {
    'delete:bitcoin-hotwallet': (name) => {
      console.log('connection details: %s', btc_conn)
      const bitcoin_data_dir=btc_conn["bitcoin_data_dir"];
      var rimraf = require("rimraf");
      console.log('Removing all wallets in %s', bitcoin_data_dir+"/regtest/wallets/specter123456_hotstorage")
      rimraf.sync(bitcoin_data_dir+"/regtest/wallets/specter123456_hotstorage");
      return null
    }
  })

  on('task', {
    'btc:mine': () => {
      // sending the bitcoind-process a signal SIGUSR1 (10) will cause mining towards all specter-wallets
      // See the signal-handler in bitcoind
      console.log('Sending SIGUSR1 to '+btc_conn["pid"]+ ' to mine some btc')
      process.kill(parseInt(btc_conn["pid"], 10), 'SIGUSR1');
      return null
    }
  })

  on('task', {
    'elm:mine': () => {
      // sending the bitcoind-process a signal SIGUSR1 (10) will cause mining towards all specter-wallets
      // See the signal-handler in bitcoind
      console.log('Sending SIGUSR1 to '+elm_conn["pid"] + ' to mine some lbtc')
      process.kill(parseInt(elm_conn["pid"], 10), 'SIGUSR1');
      return null
    }
  })

  on("task", {
    isElementsRunning: () => {
      const elm_conn_file_path = "elmd-conn.json";
      if (fs.existsSync(elm_conn_file_path)) {
        return true;
      } 
      else {
        return false;
      }
    },
  });

}
