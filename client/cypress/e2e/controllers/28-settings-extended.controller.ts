export function deleteDisposableKeepPgp(signature: string) {
  void cy.intercept({
    method: 'DELETE',
    pathname: '**/sender-identities/disposable/*',
  }).as('deleteDisposableKeep');

  void cy.contains('[data-testid="disposable-email-item"]', signature)
    .should('be.visible')
    .within(() => {
      cy.get('[data-testid="delete-disposable-button"]').click();
    });

  void cy.get('[data-testid="delete-disposable-keep-pgp"]')
    .should('be.visible')
    .click();

  void cy.wait('@deleteDisposableKeep')
    .its('response.statusCode')
    .should('eq', 200);

  void cy.contains('[data-testid="disposable-email-item"]', signature)
    .should('not.exist');

  void cy.get('[data-testid="settings-section"]')
    .should('contain.text', 'PGP key saved');
}

export function backToInboxFromSettings() {
  void cy.get('[data-testid="back-button"]')
    .should('be.visible')
    .click();

  void cy.url().should('include', '/inbox');
}
