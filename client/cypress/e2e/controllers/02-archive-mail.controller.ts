export function openInbox() {
  void cy.get('[data-testid="inbox-section"]')
    .should('be.visible')
    .click();

  void cy.url()
    .should('include', '/inbox');

  void cy.get('[data-testid="inbox-section"]')
    .should('be.visible');
}

export function getFirstInboxMessageSubject() {
  return cy.get('[data-testid="inbox-message-item"]')
    .first()
    .should('be.visible')
    .find('[data-testid="message-subject"]')
    .invoke('text')
    .then((subject) => subject.trim());
}

export function archiveFirstInboxMessage() {
  void cy.get('[data-testid="inbox-message-item"]')
    .first()
    .should('be.visible')
    .within(() => {
      cy.get('[data-testid="message-select-checkbox"]')
        .should('be.visible')
        .check();
    });

  void cy.get('[data-testid="archive-selected-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();
}

export function openArchive() {
  void cy.get('[data-testid="more-folders-button"]')
    .should('be.visible')
    .then(($button) => {
      if ($button.attr('aria-expanded') !== 'true') {
        cy.wrap($button).click();
      }
    });

  void cy.get('[data-testid="archive-section"]')
    .should('be.visible')
    .click();

  void cy.url()
    .should('include', '/archive');

  void cy.get('[data-testid="folder-title"]')
    .should('be.visible')
    .and('contain.text', 'Archive');
}

export function assertMessageExistsInArchive(subject: string) {
  void cy.contains(
    '[data-testid="message-subject"]',
    subject
  ).should('be.visible');
}
export function restoreMessageFromArchive(subject: string) {
  void cy.contains(
    '[data-testid="message-subject"]',
    subject
  )
    .closest('[data-testid="message-list-item"]')
    .should('be.visible')
    .within(() => {
      cy.get('[data-testid="move-to-inbox-button"]')
        .should('exist')
        .click({force: true});
    });
}

export function assertMessageNotInArchive(subject: string) {
  void cy.contains(
    '[data-testid="message-subject"]',
    subject
  ).should('not.exist');
}

export function assertMessageExistsInInbox(subject: string) {
  void cy.contains(
    '[data-testid="message-subject"]',
    subject
  ).should('be.visible');
}
