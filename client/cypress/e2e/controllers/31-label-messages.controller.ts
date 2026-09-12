export function refreshLabelMessages(subject: string) {
  void cy.intercept({ method: 'GET', pathname: '**/labels/*/messages' }).as('reloadLabelMessages');

  void cy.get('[data-testid="refresh-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.wait('@reloadLabelMessages').its('response.statusCode').should('eq', 200);

  void cy.contains('[data-testid="message-subject"]', subject, { timeout: 15000 })
    .should('be.visible');
}

export function openLabelMessageRow(subject: string) {
  void cy.contains('[data-testid="message-subject"]', subject, { timeout: 15000 })
    .closest('[data-testid="message-list-item"]')
    .should('be.visible')
    .click();

  void cy.get('[data-testid="message-detail"]', { timeout: 15000 }).should('be.visible');
  void cy.url().should('include', '/message/');
}

export function searchLabelNoMatch(term: string) {
  void cy.get('[data-testid="search-input"]')
    .should('be.visible')
    .clear()
    .type(term);

  void cy.get('[data-testid="empty-message-state"]', { timeout: 15000 }).should('be.visible');
  void cy.get('[data-testid="empty-message-text"]')
    .should('contain.text', 'No messages match your search');
  void cy.get('[data-testid="clear-search-button"]').should('be.visible');
}

export function clearLabelSearch(subject: string) {
  void cy.get('[data-testid="clear-search-button"]').should('be.visible').click();

  void cy.contains('[data-testid="message-subject"]', subject, { timeout: 15000 })
    .should('be.visible');
}
