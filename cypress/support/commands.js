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

Cypress.Commands.add("addDevice", (name, device_type, mnemonic) => { 
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
        cy.contains('Manual configuration').click()
        cy.get('#device_name').type(name)
        // Device types are the names to select from, such as Trezor, Specter-DIY or Electrum
        cy.get('#device_type').select(device_type)
        if (mnemonic === "ghost_machine" || mnemonic === null) { 
          cy.get('#txt').type("[8c24a510/84h/1h/0h]vpub5Y24kG7ZrCFRkRnHia2sdnt5N7MmsrNry1jMrP8XptMEcZZqkjQA6bc1f52RGiEoJmdy1Vk9Qck9tAL1ohKvuq3oFXe3ADVse6UiTHzuyKx")
          cy.get('#txt').type("\n[8c24a510/49h/1h/0h]upub5DCn7wm4SgVmzmtdoi8DVVfxhBJkqL1L6mmKHNgVky1Fj5VyBxV6NzKD957sr5fWXkY5y8THtqSVWWpjLnomBYw4iXpxaPbkXg5Gn6s5tQf")
          cy.get('#txt').type("\n[8c24a510/48h/1h/0h/1h]Upub5S2BXfT5rv2bc2i4Hr8NaBzcu243ztEMJ7LUDK4A9UKRtVmr9EFNdNdPz8rAXQnZDeAoHA8KcR7grVjREWKpBr69bev4rkvxytLZ6fN3sUv")
          cy.get('#txt').type("\n[8c24a510/48h/1h/0h/2h]Vpub5krSqL811ba5VJdUoP42TFmfRkAaR6h4uxdDThCvDd24PR5gXWPHCvASLbEKevdQQjGx3i1WG7ueEARb8Hpo2u4HikY3wnvwvF1VSakkjew")
        }
        if (mnemonic === "hold_accident") {
          cy.get('#txt').type("[ccf2e5c3/84h/1h/0h]vpub5YkPJgRQsev79YZM1NRDKJWDjLFcD2xSFAt6LehC5iiMMqQgMHyCFQzwsu16Rx9rBpXZVXPjWAxybuCpsayaw8qCDZtjwH9vifJ7WiQkHwu")
          cy.get('#txt').type("\n[ccf2e5c3/49h/1h/0h]upub5DH3pJxqyFKA9Xu8mbKie67UvJ5VWsDDtEg2YR98Yy99UGFNnBa6VSk36zW1ZWTrbYa1Nk6zrxSvzL2hdzjbRUatmwaVUPPYzyEniauECJy")
          cy.get('#txt').type("\n[ccf2e5c3/48h/1h/0h/1h]Upub5RyWnpxermQY5L7knm9gDPMQGcFKqat9pDKxhNGoVQHFDubgitAESzyS6QH65ebd7KCs6njXEL1kh1iCweiodWT1xtq69VNx2Cwog97WEDt")
          cy.get('#txt').type("\n[ccf2e5c3/48h/1h/0h/2h]Vpub5kon6Vda1Sx1xfPziprUxjBU9PjxGisfosRz3yvWz9odArUVF4embnoB4rEN76CVc5r1UB5JYXxzHTSQS6M1mAob8Wsw6FXk57RubBaizov")
        }
        cy.contains("Continue").click()
      })
})

Cypress.Commands.add("addHotDevice", (name, node_type) => { 
  // node_type is either elements or bitcoin
  cy.get('body').then(($body) => {
      if ($body.text().includes(name)) {
        cy.deleteDevice(name)
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
          cy.contains(name).click( {force: true} )
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

Cypress.Commands.add("addWallet", (walletName, walletType, funded, nodeType, keyType, deviceNameOne, deviceNameTwo, deviceNameThree) => { 
  if (walletType == null) {
    walletType = "segwit"
  }
  if (deviceNameOne == null) {
    deviceNameOne = "DIY ghost"
  }
  cy.get('body').then(($body) => {
      if ($body.text().includes(walletName)) {
        cy.contains(walletName).click()
        cy.get('#btn_settings' ).click( {force: true})
        cy.get('#advanced_settings_tab_btn').click()
        cy.get('#delete_wallet').click()
      }
      cy.get('#side-content').click()
      cy.get('#btn_new_wallet').click()
      if (keyType == 'singlesig') {
        cy.get('[href="./simple/"]').click()
        var device_button = "#"+deviceNameOne.toLowerCase().replace(/ /g,"_")
        cy.get(device_button).click()
        cy.get('#wallet_name').type(walletName)
        if (walletType == "nested_segwit") {
          cy.get('#type_nested_segwit_btn').click()
        }
        if (walletType == "taproot") {
          cy.get('#type_taproot_btn').click()
        }
      }
      // Makes a 2 out 3 multisig
      else if (keyType == "multisig") {
        cy.get('[href="./multisig/"]').click()
        var deviceButtonOne = "#"+deviceNameOne.toLowerCase().replace(/ /g,"_")
        cy.get(deviceButtonOne).click()
        var deviceButtonTwo = "#"+deviceNameTwo.toLowerCase().replace(/ /g,"_")
        cy.get(deviceButtonTwo).click()
        var deviceButtonThree = "#"+deviceNameThree.toLowerCase().replace(/ /g,"_")
        cy.get(deviceButtonThree).click()
        cy.get('#submit-device').click()
        cy.get('#wallet_name').type(walletName)
        if (walletType == "nested_segwit") {
          cy.get('#type_nested_segwit_btn').click()
        }
        cy.get(':nth-child(9) > .inline').clear()
        cy.get(':nth-child(9) > .inline').type(2)
      }
      cy.get('#keysform > .centered').click()
      cy.get('body').contains("New wallet was created successfully!")
      cy.get('#page_overlay_popup_cancel_button').click()
      if (funded) {
        cy.mine2wallet(nodeType)
      }  
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
    cy.contains(name).click( {force: true} ) 
  })
})

Cypress.Commands.add("mine2wallet", (chain) => { 
  // Fund it and check the balance
  // Only works if a wallet is selected, use addHotWallet / selectWallet commands before if needed
  cy.get('#btn_transactions').click()
  cy.get('#amount_total', { timeout: Cypress.env("broadcast_timeout") }).then(($header) => {
      const oldBalance = parseFloat($header.text())
      if (chain=="elm" || chain=="elements") {
        cy.task("elm:mine")
      } else if (chain=="btc" || chain=="bitcoin") {
        cy.task("btc:mine")
      } else {
        throw new Error("Unknown chain: " + chain)
      }
      cy.waitUntil( () => cy.reload().get('#amount_total', { timeout: 3000 }) 
        .then(($header) => {
          const n = parseFloat($header.text())
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
  // it is not clear why .shadow(), or { includeShadowDom: true } is needed here to find the elements in the ShadowDOM, but not in the other cypresss tests 
  cy.get('#recipient_0').find('#address', { includeShadowDom: true }).type(address, { force: true })   
  cy.get('#recipient_0').find('#label', { includeShadowDom: true }).type(label, { force: true })
  //cy.get('#send_max_0').click()
  cy.get('#recipient_0').find('#amount', { includeShadowDom: true }).type(amount, { force: true })
  cy.get('#create_psbt_btn').click()
})
