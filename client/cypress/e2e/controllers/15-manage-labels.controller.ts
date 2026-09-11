export function openLabelManager() {
  void cy.visit('/settings/labels');

  void cy.get('[data-testid="label-manager"]')
    .should('be.visible');
}

export function renameLabel(currentName: string, newName: string) {
  void cy.contains('[data-testid="label-item"]', currentName)
    .should('be.visible')
    .within(() => {
      cy.get('[data-testid="edit-label-button"]')
        .click({ force: true });
    });

  void cy.get('[data-testid="edit-label-name-input"]')
    .should('be.visible')
    .clear()
    .type(newName);

  void cy.get('[data-testid="save-label-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.get('[data-testid="edit-label-form"]')
    .should('not.exist');
}

export function deleteLabel(name: string) {
  void cy.contains('[data-testid="label-item"]', name)
    .should('be.visible')
    .within(() => {
      cy.get('[data-testid="delete-label-button"]')
        .click({ force: true });
    });

  void cy.get('[data-testid="delete-label-confirmation"]')
    .should('be.visible');

  void cy.get('[data-testid="confirm-delete-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();
}

export function assertLabelExists(name: string) {
  void cy.contains('[data-testid="label-name"]', name)
    .should('be.visible');
}

export function assertLabelRemoved(name: string) {
  void cy.contains('[data-testid="label-name"]', name)
    .should('not.exist');
}
