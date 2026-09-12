import {
  applyListAndClearFormatting,
  attachOversizedFileShowsError,
  attachSmallFileAndRemove,
  fillCcAndBcc,
  insertLinkViaToolbar,
  openCompose,
} from './controllers/27-compose-rich.controller';

import { loginAsTestUser } from './controllers/test-mail.controller';

describe('Orion Mail - Compose Rich Text and Attachments', () => {

  beforeEach(() => {
    loginAsTestUser('test1');
    cy.visit('/inbox');
    cy.get('[data-testid="inbox-section"]').should('be.visible');
    openCompose();
  });

  it('applies bulleted, numbered, and clear formatting in the rich editor', () => {
    applyListAndClearFormatting();
  });

  it('inserts a link through the toolbar', () => {
    insertLinkViaToolbar();
  });

  it('fills the cc and bcc fields', () => {
    fillCcAndBcc(
      'test2@mail.orionintelligence.org',
      'test3@mail.orionintelligence.org'
    );
  });

  it('attaches a small file and removes it', () => {
    attachSmallFileAndRemove();
  });

  it('shows a file error for an oversized attachment', () => {
    attachOversizedFileShowsError();
  });

});
