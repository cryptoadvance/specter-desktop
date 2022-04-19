describe('Test the actions in UTXO list', () => {
    
    before(() => {

        cy.viewport(1200,660)
        cy.visit('/')
        cy.get('body').then(($body) => {
            if ($body.text().includes('Login to Specter')) {
                cy.get('#username').type("admin")
                cy.get('#password').type("admin")
                cy.get('#login-btn').click()
            }
        })
        cy.get('[href="/settings/"] > .svg-white').click()
        cy.get('[href="/settings/auth"]').click()
        cy.get('select').select("usernamepassword")
        cy.get('#submit-btn')

        cy.get('body').then(($body) => {
            if (! $body.text().includes('user1')) {
                cy.get('#generateregistrationlink > .btn').click()
                cy.get('message-box').then(($msgbox) => {
                    //expect($msgbox.text()).to.match(/New user link generated (expires in 1 hour):.*/)
                    let matches = $msgbox.text().match(/http:\/\/.*/)
                    cy.log(matches)
                    cy.visit(matches[0])
                    cy.get('[placeholder="Username"]').type("user1")
                    cy.get('[placeholder="Password"]').type("user1pass")
                    cy.get('.row > .btn').click()
                    cy.get('message-box').contains("You have registered successfully")
        
                })
            }
            if (! $body.text().includes('user2')) {
                cy.get('#generateregistrationlink > .btn').click()
                cy.get('message-box').then(($msgbox) => {
                    cy.log($msgbox)
                    cy.log($msgbox.text())
                    //expect($msgbox.text()).to.match(/New user link generated (expires in 1 hour):.*/)
                    let matches = $msgbox.text().match(/http:\/\/.*/)
                    cy.log(matches)
                    cy.visit(matches[0])
                    cy.get('[placeholder="Username"]').type("user2")
                    cy.get('[placeholder="Password"]').type("user2pass")
                    cy.get('.row > .btn').click()
                    cy.get('message-box').contains("You have registered successfully")
        
                })
            }
        })


    })

    it('First Session Login', () => {
        Cypress.config('experimentalSessionSupport','true')
        /*
        This doesn't work yet because we need a more recent version of cypress which
        support session-management

        cy.session( () => {
            cy.visit('/auth/login')
            cy.get('#username').type("user1")
            cy.get('#password').type("user1pass")
            cy.get('#login-btn')
          })
        */
        
    })
})