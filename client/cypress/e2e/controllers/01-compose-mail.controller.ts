export interface ComposeMailData {
  receiver: string;
  subject: string;
  message: string;
  cc?: string;
  bcc?: string;
}

export function openComposeMail() {
  void cy.get('[data-testid="compose-button"]')
    .should('be.visible')
    .click();

  void cy.get('[data-testid="compose-form"]')
    .should('be.visible');

  void cy.get('[data-testid="compose-title"]')
    .should('be.visible');

  void cy.get('[data-testid="receiver-input"]')
    .should('be.visible');

  void cy.get('[data-testid="subject-input"]')
    .should('be.visible');

  void cy.get('[data-testid="send-button"]')
    .should('be.visible');
}

export function fillComposeMail(mail: ComposeMailData) {
  void cy.get('[data-testid="receiver-input"]')
    .should('be.visible')
    .clear()
    .type(mail.receiver);

  if (mail.cc) {
    void cy.get('[data-testid="cc-input"]')
      .should('be.visible')
      .clear()
      .type(mail.cc);
  }

  if (mail.bcc) {
    void cy.get('[data-testid="bcc-input"]')
      .should('be.visible')
      .clear()
      .type(mail.bcc);
  }

  void cy.get('[data-testid="subject-input"]')
    .should('be.visible')
    .clear()
    .type(mail.subject);

  void cy.get('body').then(($body) => {
    if ($body.find('[data-testid="rich-text-editor"]').length > 0) {
      cy.get('[data-testid="rich-text-editor"]')
        .should('be.visible')
        .click()
        .type(mail.message);
    } else {
      cy.get('[data-testid="message-input"]')
        .should('be.visible')
        .clear()
        .type(mail.message);
    }
  });
}

export function sendComposeMail() {
  void cy.get('[data-testid="send-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();
}

export function closeComposeMail() {
  void cy.get('[data-testid="close-button"]')
    .should('be.visible')
    .click();

  void cy.get('[data-testid="compose-form"]')
    .should('not.exist');
}

export function discardComposeMail() {
  void cy.get('[data-testid="discard-draft-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();
}

export function attachComposeFile(
  fileName: string,
  contents: string,
  mimeType = 'text/plain'
) {
  void cy.get('[data-testid="file-input"]')
    .selectFile({
      contents: Cypress.Buffer.from(contents),
      fileName,
      mimeType,
    }, {force: true});

  void cy.get('[data-testid="selected-attachment"]')
    .should('be.visible')
    .and('contain.text', fileName);
}

export function removeComposeAttachment() {
  void cy.get('[data-testid="remove-attachment-button"]')
    .should('be.visible')
    .click();

  void cy.get('[data-testid="selected-attachment"]')
    .should('not.exist');
}

export function assertEmptyComposeValidation() {
  void cy.get('[data-testid="send-button"]')
    .should('be.visible')
    .click();

  void cy.get('[data-testid="receiver-error"]')
    .should('be.visible')
    .and('contain.text', 'Enter a valid recipient email address.');

  void cy.get('[data-testid="subject-error"]')
    .should('be.visible')
    .and('contain.text', 'Add a subject.');

  void cy.get('[data-testid="message-error"]')
    .should('be.visible')
    .and('contain.text', 'Write a message before sending.');
}

export function switchToRichText() {
  void cy.get('body').then(($body) => {
    if ($body.find('[data-testid="rich-text-editor"]').length === 0) {
      cy.get('[data-testid="rich-text-toggle"]')
        .should('be.visible')
        .click();
    }
  });

  void cy.get('[data-testid="rich-text-editor"]')
    .should('be.visible');
}

export function enterRichTextMessage(message: string) {
  void cy.get('[data-testid="rich-text-editor"]')
    .should('be.visible')
    .click()
    .type(message);
}

export function applyBoldFormatting() {
  void cy.get('[data-testid="bold-button"]')
    .should('be.visible')
    .click();
}

export function applyItalicFormatting() {
  void cy.get('[data-testid="italic-button"]')
    .should('be.visible')
    .click();
}

export function applyUnderlineFormatting() {
  void cy.get('[data-testid="underline-button"]')
    .should('be.visible')
    .click();
}
