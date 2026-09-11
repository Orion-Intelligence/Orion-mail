export function createTestMail(
  receiver: string,
  subject: string,
  body: string
) {
  cy.setCookie('orion_mail_test_session', 'test2');

  cy.visit('/inbox');

  void cy.get('[data-testid="inbox-section"]', { timeout: 20000 })
    .should('be.visible');

  void cy.intercept({
    method: 'POST',
    pathname: '**/messages/send',
  }).as('createTestMailSend');

  void cy.get('[data-testid="compose-button"]')
    .should('be.visible')
    .click();

  void cy.get('[data-testid="compose-form"]')
    .filter(':visible')
    .should('have.length', 1)
    .within(() => {
      cy.get('[data-testid="receiver-input"]')
        .should('be.visible')
        .clear()
        .type(receiver);

      cy.get('[data-testid="subject-input"]')
        .should('be.visible')
        .clear()
        .type(subject);

      cy.get(
        '[data-testid="rich-text-editor"], [data-testid="message-input"]'
      )
        .should('be.visible')
        .then(($editor) => {
          if ($editor.attr('data-testid') === 'rich-text-editor') {
            cy.wrap($editor)
              .click()
              .type(body);
          } else {
            cy.wrap($editor)
              .clear()
              .type(body);
          }
        });

      cy.get('[data-testid="send-button"]')
        .should('be.visible')
        .and('not.be.disabled')
        .click();
    });

  void cy.wait('@createTestMailSend', { timeout: 30000 })
    .its('response.statusCode')
    .should('eq', 200);

  void cy.get('body')
    .find('[data-testid="compose-form"]:visible')
    .should('have.length', 0);
}

export function loginAsTestUser(username: string) {
  void cy.setCookie('orion_mail_test_session', username);
}
