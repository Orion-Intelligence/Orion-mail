export function openComposeForDraft() {
  void cy.get('[data-testid="compose-button"]')
    .should('be.visible')
    .click();

  void cy.get('[data-testid="compose-form"]')
    .filter(':visible')
    .should('have.length', 1);
}

export function fillDraft(
  receiver: string,
  subject: string,
  message: string
) {
  void cy.get('[data-testid="compose-form"]')
    .filter(':visible')
    .within(() => {
      cy.get('[data-testid="receiver-input"]')
        .should('be.visible')
        .clear()
        .type(receiver);

      cy.get('[data-testid="subject-input"]')
        .should('be.visible')
        .clear()
        .type(subject);

      cy.get(
        '[data-testid="rich-text-editor"], [data-testid="message-input"]'
      )
        .should('be.visible')
        .then(($editor) => {
          if ($editor.attr('data-testid') === 'rich-text-editor') {
            cy.wrap($editor)
              .click()
              .type(message);
          } else {
            cy.wrap($editor)
              .clear()
              .type(message);
          }
        });
    });
}

export function waitForDraftSave() {
  void cy.get('[data-testid="compose-form"]')
    .filter(':visible')
    .within(() => {
      cy.get('[data-testid="draft-status"]', {
        timeout: 15000,
      }).should('be.visible');
    });
}

export function saveAndCloseDraft() {
  waitForDraftSave();

  void cy.get('[data-testid="compose-form"]')
    .filter(':visible')
    .within(() => {
      cy.get('[data-testid="close-button"]')
        .should('be.visible')
        .click();
    });

  void cy.get('body')
    .find('[data-testid="compose-form"]:visible')
    .should('have.length', 0);
}

export function openDrafts() {
  void cy.get('[data-testid="drafts-section"]')
    .should('be.visible')
    .click();

  void cy.url()
    .should('include', '/drafts');
}

export function assertDraftExists(subject: string) {
  void cy.contains(
    '[data-testid="message-subject"]',
    subject
  ).should('be.visible');
}

export function openDraft(subject: string) {
  void cy.contains(
    '[data-testid="message-subject"]',
    subject
  )
    .closest('[data-testid="message-list-item"]')
    .should('be.visible')
    .click();

  void cy.get('[data-testid="compose-form"]')
    .filter(':visible')
    .should('have.length', 1);
}

export function assertDraftContent(
  receiver: string,
  subject: string,
  message: string
) {
  void cy.get('[data-testid="compose-form"]')
    .filter(':visible')
    .within(() => {
      cy.get('[data-testid="receiver-input"]')
        .should('have.value', receiver);

      cy.get('[data-testid="subject-input"]')
        .should('have.value', subject);

      cy.get(
        '[data-testid="rich-text-editor"], [data-testid="message-input"]'
      ).then(($editor) => {
        if ($editor.attr('data-testid') === 'rich-text-editor') {
          cy.wrap($editor)
            .should('contain.text', message);
        } else {
          cy.wrap($editor)
            .should('have.value', message);
        }
      });
    });
}

export function discardDraft() {
  void cy.intercept({
    method: 'DELETE',
    pathname: '**/messages/*/permanent',
  }).as('discardDraftRequest');

  void cy.get('[data-testid="compose-form"]')
    .filter(':visible')
    .should('have.length', 1)
    .within(() => {
      cy.get('[data-testid="discard-draft-button"]')
        .should('be.visible')
        .click();
    });

  void cy.wait('@discardDraftRequest')
    .its('response.statusCode')
    .should('eq', 200);

  void cy.get('body')
    .find('[data-testid="compose-form"]:visible')
    .should('have.length', 0);
}

export function assertDraftNotExists(subject: string) {
  void cy.intercept({
    method: 'GET',
    pathname: '**/messages/drafts',
  }).as('reloadDrafts');

  void cy.reload();

  void cy.wait('@reloadDrafts')
    .its('response.statusCode')
    .should('eq', 200);

  void cy.get('body')
    .find('[data-testid="message-subject"]')
    .should(($subjects) => {
      const subjects = [...$subjects].map(
        (element) => element.textContent?.trim()
      );

      expect(subjects).not.to.include(subject);
    });
}
