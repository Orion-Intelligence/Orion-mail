export function starInboxMessage(subject: string) {
  void cy.contains(
    '[data-testid="message-subject"]',
    subject
  )
    .closest('[data-testid="inbox-message-item"]')
    .should('be.visible')
    .within(() => {
      cy.get('[data-testid="star-button"]')
        .should('exist')
        .click({force: true});
    });
}

export function unstarMessage(subject: string) {
  void cy.contains(
    '[data-testid="message-subject"]',
    subject
  )
    .closest('[data-testid="message-list-item"]')
    .should('be.visible')
    .within(() => {
      cy.get('[data-testid="star-button"]')
        .should('exist')
        .click({force: true});
    });
}

export function openStarred() {
  void cy.get('[data-testid="more-folders-button"]')
    .should('be.visible')
    .then(($button) => {
      if ($button.attr('aria-expanded') !== 'true') {
        cy.wrap($button).click();
      }
    });

  void cy.get('[data-testid="starred-section"]')
    .should('be.visible')
    .click();

  void cy.url()
    .should('include', '/starred');

  void cy.get('[data-testid="folder-title"]')
    .should('be.visible')
    .and('contain.text', 'Starred');
}

export function assertMessageExistsInStarred(subject: string) {
  void cy.contains(
    '[data-testid="message-subject"]',
    subject
  ).should('be.visible');
}

export function assertMessageNotInStarred(subject: string) {
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
