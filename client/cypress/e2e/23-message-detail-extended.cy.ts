import {
  assertGoneFromInbox,
  backToInbox,
  downloadFromDetail,
  forwardFromDetail,
  moveToArchiveFromDetail,
  openMessage,
  replyFromDetail,
  reportPhishingFromDetail,
} from './controllers/23-message-detail-extended.controller';

import {
  createTestMail,
  loginAsTestUser,
} from './controllers/test-mail.controller';

describe('Orion Mail - Message Detail Extended', () => {

  let subject: string;

  beforeEach(() => {
    subject = `Cypress Detail Extended ${Date.now()}`;

    createTestMail(
      'test1@mail.orionintelligence.org',
      subject,
      'Automated Cypress message-detail extended test.'
    );

    loginAsTestUser('test1');

    cy.visit('/inbox');

    cy.contains('[data-testid="message-subject"]', subject, { timeout: 15000 })
      .should('be.visible');
  });

  it('returns to the inbox with the back button', () => {
    openMessage(subject);

    backToInbox();
  });

  it('opens the reply composer from the detail view', () => {
    openMessage(subject);

    replyFromDetail();
  });

  it('opens the forward composer from the detail view', () => {
    openMessage(subject);

    forwardFromDetail();
  });

  it('moves a message to Archive from the detail view', () => {
    openMessage(subject);

    moveToArchiveFromDetail();

    assertGoneFromInbox(subject);
  });

  it('downloads the original message from the detail view', () => {
    openMessage(subject);

    downloadFromDetail();
  });

  it('reports a message as phishing from the detail view', () => {
    openMessage(subject);

    reportPhishingFromDetail();

    assertGoneFromInbox(subject);
  });

});
