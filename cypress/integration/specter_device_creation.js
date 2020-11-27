describe('Creating a device in Specter', () => {
    it('Visits specter', () => {
      cy.viewport(1200,660)
      cy.visit('http://localhost:25441')
      cy.get('body').then(($body) => {
        if ($body.text().includes('Testdevice Ghost')) {
          cy.get('#devices_list > .item > div').click()
          cy.get('[style="line-height: 1; margin-top: 30px;"] > :nth-child(4) > .btn').click()
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
        cy.get('h2 > input').type("Testdevice Ghost")
        cy.get('#wizard-previous').click()
        cy.get('#step1 > .note').click()
        cy.get(':nth-child(1) > input').type("Testdevice Ghost")
        cy.get('#device_type').select("Specter-DIY")
        cy.get('#txt').type("[8c24a510/84h/1h/0h]vpub5Y24kG7ZrCFRkRnHia2sdnt5N7MmsrNry1jMrP8XptMEcZZqkjQA6bc1f52RGiEoJmdy1Vk9Qck9tAL1ohKvuq3oFXe3ADVse6UiTHzuyKx")
        cy.get('#cold_device > [type="submit"]').click()
        cy.get('#devices_list > .item > div').contains("Testdevice Ghost")
    })
  })
})