import {
  assertDraftContent,
  assertDraftExists,
  assertDraftNotExists,
  discardDraft,
  fillDraft,
  openComposeForDraft,
  openDraft,
  openDrafts,
  saveAndCloseDraft,
} from './controllers/07-drafts-mail.controller';

import {
  loginAsTestUser,
} from './controllers/test-mail.controller';

describe('Orion Mail - Drafts', () => {

  let receiver: string;
  let subject: string;
  let message: string;

  beforeEach(() => {
    receiver = 'test2@mail.orionintelligence.org';
    subject = `Cypress Draft Test ${Date.now()}`;
    message = 'Automated Cypress draft test message.';

    loginAsTestUser('test1');

    cy.visit('/inbox');

    cy.get('[data-testid="inbox-section"]')
      .should('be.visible');
  });

  it('saves a composed message as a draft', () => {
    openComposeForDraft();

    fillDraft(
      receiver,
      subject,
      message
    );

    saveAndCloseDraft();

    openDrafts();

    assertDraftExists(subject);

    // Cleanup
    openDraft(subject);
    discardDraft();
  });

  it('opens a saved draft with its original content', () => {
    openComposeForDraft();

    fillDraft(
      receiver,
      subject,
      message
    );

    saveAndCloseDraft();

    openDrafts();

    assertDraftExists(subject);

    openDraft(subject);

    assertDraftContent(
      receiver,
      subject,
      message
    );

    // Cleanup
    discardDraft();
  });

  it('discards a saved draft', () => {
    openComposeForDraft();

    fillDraft(
      receiver,
      subject,
      message
    );

    saveAndCloseDraft();

    openDrafts();

    assertDraftExists(subject);

    openDraft(subject);

    discardDraft();

    assertDraftNotExists(subject);
  });

});
