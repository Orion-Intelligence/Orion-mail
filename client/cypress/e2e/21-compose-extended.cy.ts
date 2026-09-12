import {
  assertSubjectValidationError,
  openCompose,
  sendRichMailWithCcBcc,
  toggleRichTextMode,
} from './controllers/21-compose-extended.controller';

import { loginAsTestUser } from './controllers/test-mail.controller';

describe('Orion Mail - Compose Extended', () => {

  beforeEach(() => {
    loginAsTestUser('test1');
    cy.visit('/inbox');
    cy.get('[data-testid="inbox-section"]').should('be.visible');
  });

  it('sends a rich-text message with cc and bcc recipients', () => {
    openCompose();

    sendRichMailWithCcBcc({
      receiver: 'test2@mail.orionintelligence.org',
      cc: 'test3@mail.orionintelligence.org',
      bcc: 'test1@mail.orionintelligence.org',
      subject: `Cypress Rich CC ${Date.now()}`,
      body: 'Rich text body with cc and bcc.',
    });
  });

  it('toggles between rich text and plain text', () => {
    openCompose();

    toggleRichTextMode();
  });

  it('shows a subject validation error when sending without a subject', () => {
    openCompose();

    assertSubjectValidationError();
  });

});
