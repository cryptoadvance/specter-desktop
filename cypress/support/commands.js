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

Cypress.Commands.add("addDevice", (name) => { 
    cy.get('body').then(($body) => {
        if ($body.text().includes(name)) {
          cy.get('#devices_list > .item > div').click()
          cy.get('#forget_device').click()
        } 
        cy.get('#side-content').click()
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
        cy.get('#txt').type("[6ea15da6/84h/1h/0h]vpub5Yw9Qps1aUVBpD3eyKVUhe5K8gbaWav9ArB4FudKeCLPb5vSsX8afAWfYvEASbkv4qxKzxSRyd3wqdgM3ir2fbrUJwiHDAJUNWGeqMDQfTj")
        cy.get('#txt').type("\n[6ea15da6/49h/1h/0h]upub5DANnftqN2Tj4S185offdMnaM6Qea3jinT57VfScASP2fuENSrFn9ixZ7zFX7ZmLovp7j2oEiWYSpCcPkeBuR2ULCiiEn8TW8P8mjaaydR3")
        cy.get('#txt').type("\n[6ea15da6/48h/1h/0h/2h]Vpub5mvDKGjRsucYGM7PWahGKJKkC3um3oJMqCYDf6SzdkPp8yES65bLfvxhE1bCZsqWobZKpcdTk3niqKR3f6T4B2zJDSyDdes3TyRM17vXYQs")
        cy.get('#txt').type("\n[6ea15da6/48h/1h/0h/1h]Upub5T5x1c4WjE54P7PsaPCUa9WNtcZuNyijXdytoHAzcK5AWrMHXX8ebWyQCXaBJuRVLDgKJMjTGSmZUans2ghMGBA8g9xRjdhuFrTyJxKYKDE")
        cy.get('#cold_device > [type="submit"]').click()
        cy.get('#devices_list > .item > div').contains(name)
      })
})

Cypress.Commands.add("addHotDevice", (name, node_type) => { 
  // node_type is either elements or bitcoin
  cy.get('body').then(($body) => {
      cy.task("delete:elements-hotwallet")
      if ($body.text().includes(name)) {
        cy.get('#devices_list > .item > div').click()
        cy.get('#forget_device').click()
      } 
      cy.get('#side-content').click()
      cy.get('#btn_new_device').click()
      cy.contains('Select Your Device Type')
      cy.get(`#${node_type}core_device_card`).click()
      cy.get('#submit-mnemonic').click()
      cy.get('#device_name').type(name)
      cy.get('#submit-keys').click()
      cy.get('#devices_list > .item > div').contains(name)
    })
})

Cypress.Commands.add("addHotWallet", (name, node_type, single_multi) => { 
  cy.get('body').then(($body) => {
      if ($body.text().includes(name)) {
        cy.contains(name).click()
        cy.get('#btn_settings' ).click( {force: true})
        cy.get('#advanced_settings_tab_btn').click()
        cy.get('#delete_wallet').click()
      }
       
      cy.get('#side-content').click()
      
      cy.get('#btn_new_wallet').click()
      cy.get('[href="./simple/"]').click()
      cy.get('#hot_elements_device_1').click()
      cy.get('#wallet_name').type(name)
      cy.get('#keysform > .centered').click()
      cy.get('body').contains("New wallet was created successfully!")
      // // Download PDF
      // // unfortunately this results in weird effects in cypress run
      // //cy.get('#pdf-wallet-download > img').click()
      cy.get('#btn_continue').click()
      cy.get('#btn_transactions').click()
      cy.task("elm:mine")
      cy.wait(4000)
      cy.reload()
      cy.get('#fullbalance_amount')
          .should(($div) => {
            const n = parseFloat($div.text())
            expect(n).to.be.gt(0).and.be.lte(50)
          })

    })
})