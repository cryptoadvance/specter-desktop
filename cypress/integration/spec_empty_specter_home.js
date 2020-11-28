
describe('Completely empty specter-home', () => {
  beforeEach(() => {
    cy.task("clear:specter-home")
  })
  it('Visits specter and clicks around', () => {
    cy.viewport(1200,660)
    cy.visit('http://localhost:25441')
    cy.contains('Welcome to Specter Desktop')
    cy.get('[href="/settings/"] > img').click()
    cy.contains('Bitcoin Core settings - Specter Desktop custom')
    cy.get('.mobile-right').click()
    cy.contains('General settings - Specter Desktop custom')
    cy.get('[href="/settings/auth"]').click()
    cy.contains('Authentication settings - Specter Desktop custom')
    cy.get('.right').click()
    cy.contains('HWI Bridge settings - Specter Desktop custom')
  })

  it('Creates a device in Specter', () => {
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

  it('Configures the node in Specter', () => {
    cy.viewport(1200,660)
    cy.visit('http://localhost:25441')
    cy.get('[href="/settings/"] > img').click()
    cy.get('#datadir-container').then(($datadir) => {
      cy.log($datadir)
      if (!Cypress.dom.isVisible($datadir)) {
        cy.get('.slider').click()
      }
      cy.get('.slider').click()
      cy.get('#username').clear()
      cy.get('#username').type("bitcoin")
      cy.get('#password').clear()
      cy.get('#password').type("wrongPassword") // wrong Password
      cy.get('#host').clear()
      // This is hopefully correct for some longer time. If the connection fails, check the 
      // output of python3 -m cryptoadvance.specter bitcoind (in the CI-output !!) for a better ip-address.
      // AUtomating that is probably simply not worth it.
      //cy.get('#host').type("http://172.17.0.3")
      cy.get('#host').type("http://localhost")
      cy.get('#port').clear()
      cy.get('#port').type("18443")
      cy.get('[value="test"]').click()
      cy.get(':nth-child(2) > button > div').should('have.css', 'color', 'rgb(0, 128, 0)') // connectable: green
      cy.get(':nth-child(5) > button > div').should('have.css', 'color', 'rgb(255, 0, 0)') // Credentials: red
      cy.get('#password').clear()
      cy.get('#password').type("secret")
      cy.get('[value="test"]').click()
      cy.get(':nth-child(2) > button > div').should('have.css', 'color', 'rgb(0, 128, 0)') // connectable: green
      cy.get(':nth-child(5) > button > div').should('have.css', 'color', 'rgb(0, 128, 0)') // Credentials: green
      cy.get(':nth-child(8) > button > div').should('have.css', 'color', 'rgb(0, 128, 0)') // Version green
      cy.get(':nth-child(11) > button > div').should('have.css', 'color', 'rgb(0, 128, 0)') // Walletsenabled green
      cy.get('[value="save"]').click()
    })
  })

})


