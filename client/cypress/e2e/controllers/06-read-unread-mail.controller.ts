function selectInboxMessage(subject: string) {
  void cy.contains(
    '[data-testid="message-subject"]',
    subject
  )
    .closest('[data-testid="inbox-message-item"]')
    .should('be.visible')
    .within(() => {
      cy.get('[data-testid="message-select-checkbox"]')
        .should('be.visible')
        .check();
    });
}

export function markMessageAsRead(subject: string) {
  selectInboxMessage(subject);

  void cy.get('[data-testid="toggle-selected-read-button"]')
    .should('be.visible')
    .and('have.attr', 'data-mail-action', 'mark-read')
    .click();
}

export function markMessageAsUnread(subject: string) {
  selectInboxMessage(subject);

  void cy.get('[data-testid="toggle-selected-read-button"]')
    .should('be.visible')
    .and('have.attr', 'data-mail-action', 'mark-unread')
    .click();
}

export function assertMessageIsUnread(subject: string) {
  void cy.contains(
    '[data-testid="message-subject"]',
    subject
  )
    .should('be.visible')
    .and('have.class', 'font-semibold');
}

export function assertMessageIsRead(subject: string) {
  void cy.contains(
    '[data-testid="message-subject"]',
    subject
  )
    .should('be.visible')
    .and('not.have.class', 'font-semibold');
}
