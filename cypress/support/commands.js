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
        cy.get('#step1 > [type="text"]').type("specter")
        cy.contains('Select Your Device Type')
        cy.get('#trezor_device_card').should('not.have.class', 'disabled')
        cy.get('#specter_device_card').click()
        cy.get('h2 > input').type(name)
        cy.get('#wizard-previous').click()
        cy.get('#step1 > .note').click()
        cy.get('#device_name').type(name)
        cy.get('#device_type').select("Specter-DIY")
        cy.get('#txt').type("[8c24a510/84h/1h/0h]vpub5Y24kG7ZrCFRkRnHia2sdnt5N7MmsrNry1jMrP8XptMEcZZqkjQA6bc1f52RGiEoJmdy1Vk9Qck9tAL1ohKvuq3oFXe3ADVse6UiTHzuyKx")
        cy.get('#cold_device > [type="submit"]').click()
        cy.get('#devices_list > .item > div').contains(name)
      })
})

Cypress.Commands.add("addHotDevice", (name) => { 
  cy.get('body').then(($body) => {
      if ($body.text().includes(name)) {
        cy.get('#devices_list > .item > div').click()
        cy.get('#forget_device').click()
      } 
      cy.get('#side-content').click()
      cy.get('#btn_new_device').click()
      // Creating a Device
      cy.contains('Select Your Device Type')
      cy.get('#bitcoincore_device_card').click()
      cy.get('#wizard-next').click()
      cy.get('#device_name').type(name)
      cy.get('#wizard-submit').click()
      cy.get('#devices_list > .item > div').contains(name)
    })
})