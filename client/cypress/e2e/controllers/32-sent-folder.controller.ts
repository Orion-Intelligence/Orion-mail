export function searchFolderNoMatch(term: string) {
  void cy.get('[data-testid="search-input"]')
    .should('be.visible')
    .clear()
    .type(term);

  void cy.get('[data-testid="empty-state"]', { timeout: 15000 }).should('be.visible');
  void cy.get('[data-testid="empty-state-message"]')
    .should('contain.text', 'No messages match your search');
  void cy.get('[data-testid="clear-search-button"]').should('be.visible');
}

export function clearFolderSearch(subject: string) {
  void cy.get('[data-testid="clear-search-button"]').should('be.visible').click();

  void cy.contains('[data-testid="message-subject"]', subject, { timeout: 15000 })
    .should('be.visible');
}

export function openSentRow(subject: string) {
  void cy.contains('[data-testid="message-subject"]', subject, { timeout: 15000 })
    .closest('[data-testid="message-row"]')
    .should('be.visible')
    .click();

  void cy.get('[data-testid="message-detail"]', { timeout: 15000 }).should('be.visible');
  void cy.url().should('include', '/message/');
}

export function visitSentWithLoadError() {
  void cy.intercept({ method: 'GET', pathname: '**/messages/sent' }, { statusCode: 500, body: { detail: 'boom' } }).as('sentError');

  void cy.visit('/sent');

  void cy.wait('@sentError');

  void cy.get('[data-testid="error-message"]', { timeout: 15000 }).should('be.visible');
  void cy.get('[data-testid="retry-button"]').should('be.visible');
}

export function retrySentLoad() {
  void cy.intercept({ method: 'GET', pathname: '**/messages/sent' }, { statusCode: 200, body: [] }).as('sentRetry');

  void cy.get('[data-testid="retry-button"]').should('be.visible').click();

  void cy.wait('@sentRetry').its('response.statusCode').should('eq', 200);

  void cy.get('[data-testid="error-message"]').should('not.exist');
  void cy.get('[data-testid="sent-section"]').should('be.visible');
}
