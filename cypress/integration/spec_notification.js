describe('Sending notifications', () => {
    before(() => {
        Cypress.config('includeShadowDom', true)
    })

    // Keeps the session cookie alive, Cypress by default clears all cookies before each test
    beforeEach(() => {
        cy.viewport(1200,660)
        cy.visit('/')
        Cypress.Cookies.preserveOnce('session')
    })

    it('Create js_message_box', () => {
        // wait until page fully loaded
        cy.wait(1000)



        var some_title = "1234567890abcdef_____////";
        var cmd = `createNotification('${some_title}', {target_uis:['js_message_box'], image:'/static/img/ghost_3d.png', timeout:0})`;
        

        cy.window().then((win) => {
            win.eval(cmd);
        }).then((response) => {
            // wait for the msgbox-area to appear, then test the content
            cy.get('.msgbox-area', { timeout: 10000 }).then(()=>{

                cy.get('.msgbox-area').get('.msgbox-title').invoke('text').should('eq', some_title)
                cy.get('.msgbox-area').get('.msgbox-close').click()
                cy.get('.msgbox-area').get('.msgbox-title').should('not.exist');                    
            })
        });

        
    })

})