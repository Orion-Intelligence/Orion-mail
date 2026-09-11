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

export function reportAsSpam() {
  void cy.intercept({
    method: 'PUT',
    pathname: '**/messages/*/report',
  }).as('reportSpamRequest');

  void cy.get('[data-testid="report-button"]')
    .filter(':visible')
    .first()
    .should('be.visible')
    .click();

  void cy.wait('@reportSpamRequest', {
    timeout: 15000,
  })
    .its('response.statusCode')
    .should('eq', 200);
}

export function openSpam() {
  void cy.get('[data-testid="more-folders-button"]')
    .filter(':visible')
    .first()
    .click();

  void cy.get('[data-testid="spam-section"]')
    .should('be.visible')
    .click();

  void cy.url()
    .should('include', '/spam');
}

export function assertSpamMessageExists(subject: string) {
  void cy.contains(
    '[data-testid="message-subject"]',
    subject,
    { timeout: 15000 }
  ).should('be.visible');
}

export function openSpamMessage(subject: string) {
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

export function restoreFromSpam() {
  void cy.intercept({
    method: 'PUT',
    pathname: '**/messages/*/restore',
  }).as('restoreSpamRequest');

  void cy.get('[data-testid="restore-button"]')
    .filter(':visible')
    .first()
    .should('be.visible')
    .click();

  void cy.wait('@restoreSpamRequest', {
    timeout: 15000,
  })
    .its('response.statusCode')
    .should('eq', 200);
}

export function assertMessageBackInInbox(subject: string) {
  void cy.get('[data-testid="inbox-section"]')
    .should('be.visible')
    .click();

  void cy.contains(
    '[data-testid="message-subject"]',
    subject,
    { timeout: 15000 }
  ).should('be.visible');
}
