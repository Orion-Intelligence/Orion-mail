export function createLabel(labelName: string) {
  void cy.get('[data-testid="create-label-button"]')
    .filter(':visible')
    .first()
    .should('be.visible')
    .click();

  void cy.get('[data-testid="label-name-input"]', { timeout: 10000 })
    .should('be.visible')
    .clear()
    .type(labelName);

  void cy.get('[data-testid="create-label-submit-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.get('[data-testid="label-name-input"]')
    .should('not.exist');
}

export function selectInboxMessage(subject: string) {
  void cy.contains(
    '[data-testid="message-subject"]',
    subject,
    { timeout: 15000 }
  )
    .closest('[data-testid="inbox-message-item"]')
    .within(() => {
      cy.get('[data-testid="message-select-checkbox"]')
        .check({ force: true });
    });
}

export function applyLabelToSelectedMessage(labelName: string) {
  void cy.get('[data-testid="labels-button"]')
    .should('be.visible')
    .click();

  void cy.get('[data-testid="labels-menu"]')
    .should('be.visible');

  void cy.contains(
    '[data-testid="label-option"]',
    labelName
  )
    .should('be.visible')
    .within(() => {
      cy.get('[data-testid="label-checkbox"]')
        .check({ force: true });
    });

  void cy.get('[data-testid="apply-labels-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();
}

export function assertMessageHasLabel(
  subject: string,
  labelName: string
) {
  void cy.contains(
    '[data-testid="message-subject"]',
    subject,
    { timeout: 15000 }
  )
    .closest('[data-testid="inbox-message-item"]')
    .within(() => {
      cy.contains(
        '[data-testid="message-label"]',
        labelName
      ).should('be.visible');
    });
}

export function openLabelFromSidebar(labelName: string) {
  void cy.get('[data-testid="labels-nav"]')
    .should('be.visible')
    .within(() => {
      cy.contains('a', labelName)
        .should('be.visible')
        .click();
    });

  void cy.get('[data-testid="label-messages-section"]')
    .should('be.visible');
}

export function assertLabelPage(
  labelName: string,
  subject: string
) {
  void cy.get('[data-testid="label-name"]')
    .should('contain.text', labelName);

  void cy.contains(
    '[data-testid="message-subject"]',
    subject,
    { timeout: 15000 }
  ).should('be.visible');
}
