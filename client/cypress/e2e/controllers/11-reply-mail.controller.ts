export function openMessage(subject: string) {
  void cy.contains(
    '[data-testid="message-subject"]',
    subject,
    { timeout: 15000 }
  )
    .should('be.visible')
    .click();

  void cy.get('[data-testid="message-detail"]')
    .should('be.visible');
}

export function clickReply() {
  void cy.get('[data-testid="reply-button"]')
    .filter(':visible')
    .first()
    .click();

  void cy.get('[data-testid="inline-compose"]')
    .scrollIntoView();

  void cy.get('[data-testid="inline-compose"]')
    .find('[data-testid="compose-form"]')
    .should('be.visible');
}

export function typeReply(message: string) {
  void cy.get('[data-testid="inline-compose"]')
    .find(
      '[data-testid="rich-text-editor"], [data-testid="message-input"]'
    )
    .should('be.visible')
    .then(($editor) => {
      if ($editor.attr('data-testid') === 'rich-text-editor') {
        cy.wrap($editor)
          .click()
          .type(message);
      } else {
        cy.wrap($editor)
          .clear()
          .type(message);
      }
    });
}

export function sendReply() {
  void cy.intercept({
    method: 'POST',
    pathname: '**/messages/send',
  }).as('sendReplyRequest');

  void cy.get('[data-testid="inline-compose"]')
    .find('[data-testid="send-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.wait('@sendReplyRequest', {
    timeout: 15000,
  })
    .its('response.statusCode')
    .should('eq', 200);
}

export function assertReplyReceived(replyMessage: string) {
  void cy.get('body', {
    timeout: 15000,
  }).should('contain.text', replyMessage);
}
