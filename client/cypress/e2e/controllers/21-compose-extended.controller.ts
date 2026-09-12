export function openCompose() {
  void cy.get('[data-testid="compose-button"]')
    .should('be.visible')
    .click();

  void cy.get('[data-testid="compose-form"]')
    .filter(':visible')
    .should('have.length', 1);
}

export function sendRichMailWithCcBcc(options: {
  receiver: string;
  cc: string;
  bcc: string;
  subject: string;
  body: string;
}) {
  void cy.intercept({
    method: 'POST',
    pathname: '**/messages/send',
  }).as('sendRich');

  void cy.get('[data-testid="compose-form"]')
    .filter(':visible')
    .within(() => {
      cy.get('[data-testid="receiver-input"]').should('be.visible').clear().type(options.receiver);
      cy.get('[data-testid="cc-input"]').should('be.visible').clear().type(options.cc);
      cy.get('[data-testid="bcc-input"]').should('be.visible').clear().type(options.bcc);
      cy.get('[data-testid="subject-input"]').should('be.visible').clear().type(options.subject);

      cy.get('[data-testid="rich-text-editor"], [data-testid="message-input"]')
        .should('be.visible')
        .then(($editor) => {
          if ($editor.attr('data-testid') === 'rich-text-editor') {
            cy.wrap($editor).click().type(options.body);
          } else {
            cy.wrap($editor).clear().type(options.body);
          }
        });

      cy.get('[data-testid="send-button"]').should('be.visible').and('not.be.disabled').click();
    });

  void cy.wait('@sendRich', { timeout: 30000 })
    .then((interception) => {
      expect(interception.request.body).to.contain('cc_addresses');
      expect(interception.response?.statusCode).to.eq(200);
    });

  void cy.get('body')
    .find('[data-testid="compose-form"]:visible')
    .should('have.length', 0);
}

export function toggleRichTextMode() {
  void cy.get('[data-testid="compose-form"]')
    .filter(':visible')
    .within(() => {
      cy.get('[data-testid="rich-text-editor"], [data-testid="message-input"]')
        .invoke('attr', 'data-testid')
        .then((before) => {
          cy.get('[data-testid="rich-text-toggle"]').should('be.visible').click();
          const expected = before === 'rich-text-editor' ? 'message-input' : 'rich-text-editor';
          cy.get(`[data-testid="${expected}"]`).should('be.visible');
        });
    });
}

export function assertSubjectValidationError() {
  void cy.intercept({ method: 'POST', pathname: '**/messages/send' }).as('noSend');

  void cy.get('[data-testid="compose-form"]')
    .filter(':visible')
    .within(() => {
      cy.get('[data-testid="receiver-input"]').should('be.visible').clear().type('test2@mail.orionintelligence.org');
      cy.get('[data-testid="send-button"]').should('be.visible').click();
      cy.get('[data-testid="subject-error"]').should('be.visible');
    });
}
