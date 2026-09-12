export function openMessage(subject: string) {
  void cy.contains('[data-testid="message-subject"]', subject, { timeout: 15000 })
    .should('be.visible')
    .click();

  void cy.get('[data-testid="message-detail"]')
    .should('be.visible');
}

export function selectInboxMessage(subject: string) {
  void cy.contains('[data-testid="message-subject"]', subject, { timeout: 15000 })
    .closest('[data-testid="inbox-message-item"]')
    .should('be.visible')
    .within(() => {
      cy.get('[data-testid="message-select-checkbox"]').check({ force: true });
    });
}

export function trashSelected() {
  void cy.intercept({ method: 'PUT', pathname: '**/messages/bulk' }).as('trashSelected');

  void cy.get('[data-testid="trash-selected-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.wait('@trashSelected').its('response.statusCode').should('eq', 200);
}

export function openTrash() {
  void cy.intercept({ method: 'GET', pathname: '**/messages/trash' }).as('loadTrash');

  void cy.visit('/trash');

  void cy.wait('@loadTrash').its('response.statusCode').should('eq', 200);

  void cy.get('[data-testid="folder-title"]', { timeout: 15000 })
    .should('be.visible')
    .and('contain.text', 'Trash');
}

export function moveToTrashFromDetail() {
  void cy.intercept({ method: 'PUT', pathname: '**/messages/*/trash' }).as('trashRequest');

  void cy.get('[data-testid="move-to-trash-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.wait('@trashRequest').its('response.statusCode').should('eq', 200);

  void cy.url().should('include', '/inbox');
}

export function restoreFromDetail() {
  void cy.intercept({ method: 'PUT', pathname: '**/messages/*/restore' }).as('restoreRequest');

  void cy.get('[data-testid="restore-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.wait('@restoreRequest').its('response.statusCode').should('eq', 200);

  void cy.url().should('include', '/trash');
}

export function permanentlyDeleteFromDetail() {
  cy.on('window:confirm', () => true);

  void cy.intercept({ method: 'DELETE', pathname: '**/messages/*/permanent' }).as('deleteForever');

  void cy.get('[data-testid="delete-forever-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.wait('@deleteForever').its('response.statusCode').should('eq', 200);
}

export function translateFromDetail(language: string) {
  void cy.intercept({ method: 'POST', pathname: '**/messages/*/translate' }).as('translate');

  void cy.get('[data-testid="more-button"]').should('be.visible').click();
  void cy.get('[data-testid="translate-menu-button"]').should('be.visible').click();

  void cy.get('[data-testid="translation-dialog"]').should('be.visible');

  void cy.get('[data-testid="translation-language-select"]')
    .should('be.visible')
    .select(language);

  void cy.get('[data-testid="translate-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.wait('@translate').its('response').should('exist');
}

export function closeTranslationDialogWithEscape() {
  void cy.get('body').type('{esc}');

  void cy.get('[data-testid="translation-dialog"]').should('not.exist');
}

export function applyLabelFromDetail(labelName: string) {
  void cy.intercept({ method: 'PUT', pathname: '**/messages/*/labels' }).as('setLabels');

  void cy.get('[data-testid="label-button"]').should('be.visible').click();

  void cy.get('[data-testid="label-checkbox"]').first().should('exist').check({ force: true });

  void cy.get('[data-testid="apply-labels-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.wait('@setLabels').its('response.statusCode').should('eq', 200);
}
