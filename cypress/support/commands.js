// ***********************************************
// This example commands.js shows you how to
// create various custom commands and overwrite
// existing commands.
//
// For more comprehensive examples of custom
// commands please read more here:
// https://on.cypress.io/custom-commands
// ***********************************************
//
//
// -- This is a parent command --
// Cypress.Commands.add("login", (email, password) => { ... })
//
//
// -- This is a child command --
// Cypress.Commands.add("drag", { prevSubject: 'element'}, (subject, options) => { ... })
//
//
// -- This is a dual command --
// Cypress.Commands.add("dismiss", { prevSubject: 'optional'}, (subject, options) => { ... })
//
//
// -- This will overwrite an existing command --
// Cypress.Commands.overwrite("visit", (originalFn, url, options) => { ... })

import 'cypress-wait-until';

Cypress.Commands.add("addDevice", (name) => { 
    cy.get('body').then(($body) => {
        if ($body.text().includes(name)) {
          cy.get('#toggle_devices_list').click()
          cy.contains(name).click()
          cy.get('#forget_device').click()
        } 
        cy.get('#side-content').click()
        if (!cy.get('#btn_new_device').isVisible) {
          cy.get('#toggle_devices_list').click()
        }
        cy.get('#btn_new_device').click()
        // Creating a Device
        cy.contains('Select Your Device Type')
        cy.get('#trezor_device_card')
        cy.get('#device-type-searchbar').type("specter")
        cy.contains('Select Your Device Type')
        cy.get('#trezor_device_card').should('not.have.class', 'disabled')
        cy.get('#specter_device_card').click()
        cy.get('h2 > input').type(name)
        cy.go('back')
        cy.get('#device-type-container > .note').click()
        cy.get('#device_name').type(name)
        cy.get('#device_type').select("Specter-DIY")
        cy.get('#txt').type("[8c24a510/84h/1h/0h]vpub5Y24kG7ZrCFRkRnHia2sdnt5N7MmsrNry1jMrP8XptMEcZZqkjQA6bc1f52RGiEoJmdy1Vk9Qck9tAL1ohKvuq3oFXe3ADVse6UiTHzuyKx")
        cy.get('#txt').type("\n[8c24a510/49h/1h/0h]upub5DCn7wm4SgVmzmtdoi8DVVfxhBJkqL1L6mmKHNgVky1Fj5VyBxV6NzKD957sr5fWXkY5y8THtqSVWWpjLnomBYw4iXpxaPbkXg5Gn6s5tQf")
        cy.get('#txt').type("\n[8c24a510/48h/1h/0h/1h]Upub5S2BXfT5rv2bc2i4Hr8NaBzcu243ztEMJ7LUDK4A9UKRtVmr9EFNdNdPz8rAXQnZDeAoHA8KcR7grVjREWKpBr69bev4rkvxytLZ6fN3sUv")
        cy.get('#txt').type("\n[8c24a510/48h/1h/0h/2h]Vpub5krSqL811ba5VJdUoP42TFmfRkAaR6h4uxdDThCvDd24PR5gXWPHCvASLbEKevdQQjGx3i1WG7ueEARb8Hpo2u4HikY3wnvwvF1VSakkjew")
        cy.get('#cold_device > [type="submit"]').click()
        cy.get('#toggle_devices_list').click()
        cy.get('#devices_list > .item > div').contains(name)
      })
})

Cypress.Commands.add("addHotDevice", (name, node_type) => { 
  // node_type is either elements or bitcoin
  cy.get('body').then(($body) => {
      cy.task("delete:elements-hotwallet")
      if ($body.text().includes(name)) {
        cy.get('#toggle_devices_list').click()
        var refName = "#device_list_item_"+name.toLowerCase().replace(/ /g,"_")
        cy.get(refName).click( {force: true} )
        cy.get('#forget_device').click()
        // We might get an error here, if the device is used in a wallet
        // We assume therefore that this is ok (see below)
      } 
      cy.get('#side-content').click()
      if (!cy.get('#btn_new_device').isVisible) {
        cy.get('#toggle_devices_list').click()
      }
      cy.get('#btn_new_device').click( {force: true} )
      cy.contains('Select Your Device Type')
      cy.get(`#${node_type}core_device_card`).click()
      cy.get('#submit-mnemonic').click()
      cy.get('#device_name').type(name)
      cy.get('#submit-keys').click()
      cy.get('#toggle_devices_list').click()
      // It's a bit hackish as if the device already exists, we'll get an error
      // but continue flaslessly nevertheless
      cy.get('#devices_list > .item > div',  { timeout: 8000 }).contains(name)
    })
})

Cypress.Commands.add("deleteDevice", (name) => { 
    cy.get('body').then(($body) => {
        if ($body.text().includes(name)) {
          cy.get('#toggle_devices_list').click()
          cy.contains(name).click()
          cy.get('#forget_device').click()
          cy.reload()
          // For hot wallets only
          cy.task("delete:bitcoin-hotwallet")
          cy.task("delete:elements-hotwallet")
        } 
      })
})

Cypress.Commands.add("changeDeviceType", (nameDevice, newType) => { 
    cy.get('body').then(($body) => {
        if ($body.text().includes(nameDevice)) {
          cy.get('#toggle_devices_list').click()
          cy.contains(nameDevice).click()
          cy.get('#device_type').select(newType)
          cy.get('#settype').click()
        } 
      })
})

Cypress.Commands.add("addHotWallet", (wallet_name, device_name, node_type, wallet_type, single_multi) => { 
  if (wallet_type == null) {
    wallet_type = "segwit"
  }
  if (device_name == null) {
    device_name = "Hot Elements Device 1"
  }
  cy.get('body').then(($body) => {
      if ($body.text().includes(wallet_name)) {
        cy.contains(wallet_name).click()
        cy.get('#btn_settings' ).click( {force: true})
        cy.get('#advanced_settings_tab_btn').click()
        cy.get('#delete_wallet').click()
      }
      cy.get('#side-content').click()
      cy.get('#btn_new_wallet').click()
      cy.get('[href="./simple/"]').click()
      var device_button = "#"+device_name.toLowerCase().replace(/ /g,"_")
      cy.get(device_button).click()
      cy.get('#wallet_name').type(wallet_name)
      if (wallet_type == "nested_segwit") {
        cy.get(':nth-child(1) > #type_nested_segwit_btn').click()
      }
      // Create Wallet button:
      cy.get('#keysform > .centered').click()
      cy.get('body').contains("New wallet was created successfully!")
      // // Download PDF
      // // unfortunately this results in weird effects in cypress run
      // //cy.get('#pdf-wallet-download > img').click()
      cy.get('#btn_continue').click()

      //Get some funds
      cy.mine2wallet(node_type)

    })
})

Cypress.Commands.add("deleteWallet", (name) => { 
  cy.get('body').then(($body) => {
    if ($body.text().includes(name)) {
        cy.contains(name).click()
        cy.get('#btn_settings').click( {force: true} )
        cy.get('#advanced_settings_tab_btn').click()
        cy.get('#delete_wallet').click()
        // That does not seem to delete the wallet-file in elements, though
        // So let's do that as well
        cy.task("delete:elements-hotwallet")
    } 
  })
})

Cypress.Commands.add("selectWallet", (name) => { 
  cy.get('body').then(($body) => {
    if ($body.text().includes(name)) {
        cy.contains(name).click()
    } 
  })
})

Cypress.Commands.add("mine2wallet", (chain) => { 
  // Fund it and check the balance
  // Only works if a wallet is selected, use addHotWallet / selectWallet commands before if needed
  cy.get('#btn_transactions').click()
  cy.get('#fullbalance_amount', { timeout: Cypress.env("broadcast_timeout") }).then(($span) => {
      const oldBalance = parseFloat($span.text())
      if (chain=="elm" || chain=="elements") {
        cy.task("elm:mine")
      } else if (chain=="btc" || chain=="bitcoin") {
        cy.task("btc:mine")
      } else {
        throw new Error("Unknown chain: " + chain)
      }
      cy.waitUntil( () => cy.reload().get('#fullbalance_amount', { timeout: 3000 }) 
        .then(($span) => {
          const n = parseFloat($span.text())
          return n > oldBalance
        })
      , {
        errorMsg: 'Waited for the funds arriving in the wallet from chain mining but it never did (timeout 30s) ',
        timeout: 60000,
        interval: 2000
      })
  })
})

// Quick and easy way to fill out the send form and create a psbt
Cypress.Commands.add("createPsbt", (address, label="a_label", amount=0.01) => { 
  cy.get('#btn_send').click()
  cy.get('#address_0').type(address)
  cy.get('#label_0').type(label)
  //cy.get('#send_max_0').click()
  cy.get('#amount_0').type(amount)
  cy.get('#create_psbt_btn').click()
})
