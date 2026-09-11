export function moveInboxMessageToTrash(subject: string) {
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

  void cy.get('[data-testid="trash-selected-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();
}

export function openTrash() {
  void cy.get('[data-testid="more-folders-button"]')
    .should('be.visible')
    .then(($button) => {
      if ($button.attr('aria-expanded') !== 'true') {
        cy.wrap($button).click();
      }
    });

  void cy.get('[data-testid="trash-section"]')
    .should('be.visible')
    .click();

  void cy.url()
    .should('include', '/trash');

  void cy.get('[data-testid="folder-title"]')
    .should('be.visible')
    .and('contain.text', 'Trash');
}

export function assertMessageExistsInTrash(subject: string) {
  void cy.contains(
    '[data-testid="message-subject"]',
    subject
  ).should('be.visible');
}

export function restoreMessageFromTrash(subject: string) {
  void cy.contains(
    '[data-testid="message-subject"]',
    subject
  )
    .closest('[data-testid="message-list-item"]')
    .should('be.visible')
    .within(() => {
      cy.get('[data-testid="restore-button"]')
        .should('exist')
        .click({force: true});
    });
}

export function permanentlyDeleteMessageFromTrash(subject: string) {
  void cy.contains(
    '[data-testid="message-subject"]',
    subject
  )
    .closest('[data-testid="message-list-item"]')
    .should('be.visible')
    .within(() => {
      cy.get('[data-testid="delete-forever-button"]')
        .should('exist')
        .click({force: true});
    });
}

export function assertMessageNotInTrash(subject: string) {
  void cy.contains(
    '[data-testid="message-subject"]',
    subject
  ).should('not.exist');
}

export function openInboxFromSidebar() {
  void cy.get('[data-testid="inbox-section"]')
    .should('be.visible')
    .click();

  void cy.url()
    .should('include', '/inbox');
}
