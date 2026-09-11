export function markMessageImportant(subject: string) {
  void cy.contains(
    '[data-testid="message-subject"]',
    subject
  )
    .closest('[data-testid="inbox-message-item"]')
    .should('be.visible')
    .within(() => {
      cy.get('[data-testid="important-button"]')
        .should('exist')
        .click({force: true});
    });
}

export function markMessageNotImportant(subject: string) {
  void cy.contains(
    '[data-testid="message-subject"]',
    subject
  )
    .closest('[data-testid="message-list-item"]')
    .should('be.visible')
    .within(() => {
      cy.get('[data-testid="important-button"]')
        .should('exist')
        .click({force: true});
    });
}

export function openImportant() {
  void cy.get('[data-testid="more-folders-button"]')
    .should('be.visible')
    .then(($button) => {
      if ($button.attr('aria-expanded') !== 'true') {
        cy.wrap($button).click();
      }
    });

  void cy.get('[data-testid="important-section"]')
    .should('be.visible')
    .click();

  void cy.url()
    .should('include', '/important');

  void cy.get('[data-testid="folder-title"]')
    .should('be.visible')
    .and('contain.text', 'Important');
}

export function assertMessageExistsInImportant(subject: string) {
  void cy.contains(
    '[data-testid="message-subject"]',
    subject
  ).should('be.visible');
}

export function assertMessageNotInImportant(subject: string) {
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
