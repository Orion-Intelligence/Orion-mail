function openEdit(name: string) {
  void cy.contains('[data-testid="label-item"]', name)
    .should('be.visible')
    .within(() => {
      cy.get('[data-testid="edit-label-button"]').click({ force: true });
    });

  void cy.get('[data-testid="edit-label-form"]').should('be.visible');
}

export function changeLabelColorFromPalette(name: string) {
  void cy.intercept({ method: 'PATCH', pathname: '**/labels/*' }).as('updateLabel');

  openEdit(name);

  void cy.get('[data-testid="edit-color-palette"]').should('be.visible');

  void cy.get('[data-testid="edit-color-button"]').eq(3).click();
  void cy.get('[data-testid="edit-color-button"]')
    .eq(3)
    .should('have.attr', 'aria-pressed', 'true');

  void cy.get('[data-testid="save-label-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.wait('@updateLabel').its('response.statusCode').should('eq', 200);
  void cy.get('[data-testid="edit-label-form"]').should('not.exist');
}

export function cancelEditingLabel(name: string) {
  openEdit(name);

  void cy.get('[data-testid="cancel-edit-button"]').should('be.visible').click();

  void cy.get('[data-testid="edit-label-form"]').should('not.exist');
}

export function cancelDeletingLabel(name: string) {
  void cy.contains('[data-testid="label-item"]', name)
    .should('be.visible')
    .within(() => {
      cy.get('[data-testid="delete-label-button"]').click({ force: true });
    });

  void cy.get('[data-testid="delete-label-confirmation"]').should('be.visible');

  void cy.get('[data-testid="cancel-delete-button"]').should('be.visible').click();

  void cy.get('[data-testid="delete-label-confirmation"]').should('not.exist');
}

export function refreshLabels() {
  void cy.intercept({ method: 'GET', pathname: '**/labels' }).as('reloadLabels');

  void cy.get('[data-testid="refresh-labels-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.wait('@reloadLabels').its('response.statusCode').should('eq', 200);
}
