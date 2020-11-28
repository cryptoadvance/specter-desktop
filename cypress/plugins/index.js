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
module.exports = (on, config) => {
  // `config` is the resolved Cypress config
  on('task', {
    'clear:specter-home': () => {
      const homedir = require('os').homedir();
      const specter_home=homedir+"/.specter";
      var rimraf = require("rimraf");
      rimraf.sync(specter_home);
      var fs = require('fs');
      fs.mkdirSync(specter_home);
      fs.mkdirSync(specter_home+"/devices");
      fs.mkdirSync(specter_home+"/wallets");
      return null
    }
  })

  on('task', {
    'seed:node-configuration': () => {
      // do something here
    }
  })



}
