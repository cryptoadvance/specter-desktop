describe('Test the app with multiple users', () => {
    // This test is currently still deactivated due to:
    // See https://github.com/cypress-io/cypress/issues/21138
    if (Cypress.env("CI")) {
        const login = (name,password) => {
            if (!password) {
                password = name+"pass"
            }
            cy.session([name, password], () => {
                cy.visit('/auth/login')
                cy.get('#username').type(name)
                cy.get('#password').type(password)
                cy.get('#login-btn').click()
                cy.url().should('contain', '/welcome/about')
            },
            {
                validate() {
                    cy.visit("/welcome/about")
                    cy.url().should('contain', '/welcome/about')
                }
            }
            )
        }

        before(() => {
            Cypress.config('experimentalSessionSupport',true)
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
            cy.get('#submit-btn').click()
            login("admin","admin")

            cy.get('body').then(($body) => {
                if (! $body.text().includes('user1')) {
                    cy.visit("/settings/auth")
                    cy.get('#generateregistrationlink > .btn').click({timeout:60000})
                    cy.get('message-box').then(($msgbox) => {
                        //expect($msgbox.text()).to.match(/New user link generated (expires in 1 hour):.*/)
                        let matches = $msgbox.text().match(/http:\/\/.*/)
                        cy.log(matches)
                        cy.visit(matches[0])
                        cy.get('[placeholder="Username"]').type("user1")
                        cy.get('[placeholder="Password"]').type("user1pass")
                        cy.get('.row > .btn').click()
                        //cy.wait(500)
                        cy.get('message-box').contains("You have registered successfully")
            
                    })
                }
                if (! $body.text().includes('user2')) {
                    cy.visit("/settings/auth")
                    cy.get('#generateregistrationlink > .btn').click({timeout:60000})
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
                        //cy.wait(500)
                        cy.get('message-box').contains("You have registered successfully")
            
                    })
                }
                cy.get('[href="/auth/logout"] > .svg-white').click()
            })


        })

        it('First Session Login', () => {
            
            cy.visit("/")
            login("user1")
            cy.visit("/welcome")        

            
            
        })
    }
})