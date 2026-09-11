export function selectMessage(subject: string) {
  void cy.contains(
    '[data-testid="message-subject"]',
    subject,
    { timeout: 15000 }
  )
    .closest('[data-testid="inbox-message-item"]')
    .should('be.visible')
    .within(() => {
      cy.get('[data-testid="message-select-checkbox"]')
        .check({ force: true });
    });
}

export function assertSelectedCount(count: number) {
  void cy.get('[data-testid="selected-count"]')
    .should('be.visible')
    .and('contain.text', `${count} selected`);
}

export function bulkArchive() {
  void cy.intercept({
    method: 'PUT',
    pathname: '**/messages/bulk',
  }).as('bulkArchive');

  void cy.get('[data-testid="archive-selected-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.wait('@bulkArchive')
    .then((interception) => {
      expect(interception.request.body.action).to.eq('archive');
      expect(interception.response?.statusCode).to.eq(200);
    });
}

export function bulkTrash() {
  void cy.intercept({
    method: 'PUT',
    pathname: '**/messages/bulk',
  }).as('bulkTrash');

  void cy.get('[data-testid="trash-selected-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.wait('@bulkTrash')
    .then((interception) => {
      expect(interception.request.body.action).to.eq('trash');
      expect(interception.response?.statusCode).to.eq(200);
    });
}

export function bulkMarkRead() {
  void cy.intercept({
    method: 'PUT',
    pathname: '**/messages/bulk',
  }).as('bulkMarkRead');

  void cy.get('[data-testid="toggle-selected-read-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.wait('@bulkMarkRead')
    .then((interception) => {
      expect(interception.request.body.action).to.eq('mark_read');
      expect(interception.response?.statusCode).to.eq(200);
    });
}

export function assertMessageGone(subject: string) {
  void cy.get('[data-testid="inbox-section"]', { timeout: 15000 })
    .should('be.visible')
    .and('not.contain.text', subject);
}

export function assertSelectionCleared() {
  void cy.get('[data-testid="selected-count"]')
    .should('not.exist');
}
