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

export function clickForward() {
  void cy.get('[data-testid="forward-button"]')
    .first()
    .scrollIntoView();

  void cy.get('[data-testid="forward-button"]')
    .first()
    .should('be.visible')
    .click();

  void cy.get('[data-testid="inline-compose"]')
    .scrollIntoView();

  void cy.get('[data-testid="inline-compose"]')
    .find('[data-testid="compose-form"]')
    .should('be.visible');
}

export function fillForwardReceiver(receiver: string) {
  void cy.get('[data-testid="inline-compose"]')
    .find('[data-testid="receiver-input"]')
    .should('be.visible')
    .clear()
    .type(receiver);
}

export function sendForward() {
  void cy.intercept({
    method: 'POST',
    pathname: '**/messages/send',
  }).as('sendForwardRequest');

  void cy.get('[data-testid="inline-compose"]')
    .find('[data-testid="send-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.wait('@sendForwardRequest', {
    timeout: 15000,
  })
    .its('response.statusCode')
    .should('eq', 200);
}

export function assertForwardedMessageExists(subject: string) {
  void cy.contains(
    '[data-testid="message-subject"]',
    subject,
    { timeout: 15000 }
  ).should('be.visible');
}

export function assertForwardedBodyExists(originalBody: string) {
  void cy.get('body', {
    timeout: 15000,
  }).should('contain.text', originalBody);
}
