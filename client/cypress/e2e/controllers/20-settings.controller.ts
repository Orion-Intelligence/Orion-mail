export function openSettings() {
  void cy.intercept({
    method: 'GET',
    pathname: '**/mailboxes/me',
  }).as('loadMailbox');

  void cy.visit('/settings');

  void cy.get('[data-testid="settings-section"]')
    .should('be.visible');

  void cy.wait('@loadMailbox')
    .its('response.statusCode')
    .should('eq', 200);
}

export function assertMailboxAddress(fragment: string) {
  void cy.get('[data-testid="mailbox-address"]')
    .should('be.visible')
    .and('contain.text', fragment);
}

export function saveSignature(signature: string) {
  void cy.intercept({
    method: 'PUT',
    pathname: '**/mailboxes/me/settings',
  }).as('saveSettings');

  void cy.get('[data-testid="signature-input"]')
    .should('be.visible')
    .clear()
    .type(signature);

  void cy.get('[data-testid="save-signature-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.wait('@saveSettings')
    .its('response.statusCode')
    .should('eq', 200);

  void cy.get('[data-testid="settings-section"]')
    .should('contain.text', 'Settings saved.');
}

export function saveAttachmentRetention(hours: number) {
  void cy.intercept({
    method: 'PUT',
    pathname: '**/system-config',
  }).as('saveConfig');

  void cy.get('[data-testid="config-input-attachment_retention_hours"]')
    .scrollIntoView()
    .should('be.visible')
    .clear()
    .type(String(hours));

  void cy.get('[data-testid="save-config-button"]')
    .scrollIntoView()
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.wait('@saveConfig')
    .its('response.statusCode')
    .should('eq', 200);

  void cy.get('[data-testid="attachment-config-form"]')
    .should('contain.text', 'Attachment limits saved.');
}

export function resetSignature() {
  void cy.intercept({
    method: 'PUT',
    pathname: '**/mailboxes/me/settings',
  }).as('resetSettings');

  void cy.get('[data-testid="reset-signature-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.get('[data-testid="confirm-dialog-confirm"]')
    .should('be.visible')
    .click();

  void cy.wait('@resetSettings')
    .its('response.statusCode')
    .should('eq', 200);

  void cy.get('[data-testid="settings-section"]')
    .should('contain.text', 'Signature reset');
}
