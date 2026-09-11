import {
  applyBoldFormatting,
  applyItalicFormatting,
  applyUnderlineFormatting,
  assertEmptyComposeValidation,
  attachComposeFile,
  closeComposeMail,
  discardComposeMail,
  enterRichTextMessage,
  fillComposeMail,
  openComposeMail,
  removeComposeAttachment,
  sendComposeMail,
  switchToRichText,
} from './controllers/01-compose-mail.controller';

describe('Orion Mail - Compose Mail', () => {

  beforeEach(() => {
    cy.setCookie('orion_mail_test_session', 'test1');

    cy.visit('/inbox');

    cy.get('[data-testid="inbox-section"]')
      .should('be.visible');
  });

  afterEach(() => {
    cy.get('body').then(($body) => {
      if ($body.find('[data-testid="compose-form"]').length > 0) {
        cy.get('[data-testid="discard-draft-button"]')
          .click({force: true});
      }
    });
  });

  it('opens the compose mail window', () => {
    openComposeMail();

    cy.get('[data-testid="receiver-input"]')
      .should('be.visible');

    cy.get('[data-testid="cc-input"]')
      .should('be.visible');

    cy.get('[data-testid="bcc-input"]')
      .should('be.visible');

    cy.get('[data-testid="subject-input"]')
      .should('be.visible');

    cy.get(
      '[data-testid="rich-text-editor"], [data-testid="message-input"]'
    ).should('be.visible');

    cy.get('[data-testid="send-button"]')
      .should('be.visible');
  });

  it('shows validation errors when empty mail is submitted', () => {
    openComposeMail();

    assertEmptyComposeValidation();
  });

  it('fills all compose mail fields', () => {
    openComposeMail();

    fillComposeMail({
      receiver: 'receiver@example.com',
      cc: 'cc@example.com',
      bcc: 'bcc@example.com',
      subject: 'Orion Mail Cypress Test',
      message: 'This is an automated Orion Mail compose test.',
    });

    cy.get('[data-testid="receiver-input"]')
      .should('have.value', 'receiver@example.com');

    cy.get('[data-testid="cc-input"]')
      .should('have.value', 'cc@example.com');

    cy.get('[data-testid="bcc-input"]')
      .should('have.value', 'bcc@example.com');

    cy.get('[data-testid="subject-input"]')
      .should('have.value', 'Orion Mail Cypress Test');

    cy.get('body').then(($body) => {
      if ($body.find('[data-testid="rich-text-editor"]').length > 0) {
        cy.get('[data-testid="rich-text-editor"]')
          .should('contain.text', 'This is an automated Orion Mail compose test.');
      } else {
        cy.get('[data-testid="message-input"]')
          .should('have.value', 'This is an automated Orion Mail compose test.');
      }
    });
  });

  it('attaches and removes a file', () => {
    openComposeMail();

    attachComposeFile(
      'orion-mail-test.txt',
      'Orion Mail Cypress attachment test'
    );

    cy.get('[data-testid="attachments-list"]')
      .should('be.visible');

    cy.get('[data-testid="selected-attachment"]')
      .should('contain.text', 'orion-mail-test.txt');

    removeComposeAttachment();
  });

  it('switches to rich text mode and checks formatting controls', () => {
    openComposeMail();

    switchToRichText();

    enterRichTextMessage('Orion Mail rich text test');

    applyBoldFormatting();
    applyItalicFormatting();
    applyUnderlineFormatting();

    cy.get('[data-testid="rich-text-editor"]')
      .should('contain.text', 'Orion Mail rich text test');
  });

  it('closes the compose mail window', () => {
    openComposeMail();

    closeComposeMail();
  });

  it('discards a compose draft', () => {
    openComposeMail();

    fillComposeMail({
      receiver: 'receiver@example.com',
      subject: 'Discard Test',
      message: 'This draft should be discarded.',
    });

    discardComposeMail();

    cy.get('[data-testid="compose-form"]')
      .should('not.exist');
  });

  it('sends a mail successfully', () => {
    openComposeMail();

    fillComposeMail({
      receiver: 'receiver@example.com',
      subject: 'Orion Mail Send Test',
      message: 'This message is sent through Cypress.',
    });

    sendComposeMail();

    cy.get('[data-testid="compose-form"]', {timeout: 30000})
      .should('not.exist');
  });
});
