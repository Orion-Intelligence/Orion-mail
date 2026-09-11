import {
  assertMessageBackInInbox,
  assertSpamMessageExists,
  openMessage,
  openSpam,
  openSpamMessage,
  reportAsSpam,
  restoreFromSpam,
} from './controllers/13-spam-mail.controller';

import {
  createTestMail,
  loginAsTestUser,
} from './controllers/test-mail.controller';

describe('Orion Mail - Spam', () => {
  let subject: string;

  beforeEach(() => {
    subject = `Cypress Spam Test ${Date.now()}`;

    createTestMail(
      'test1@mail.orionintelligence.org',
      subject,
      'Automated Cypress spam test message.'
    );

    loginAsTestUser('test1');

    cy.visit('/inbox');

    cy.contains(
      '[data-testid="message-subject"]',
      subject,
      { timeout: 15000 }
    ).should('be.visible');
  });

  it('moves a received message to spam and restores it', () => {
    openMessage(subject);

    reportAsSpam();

    openSpam();

    assertSpamMessageExists(subject);

    openSpamMessage(subject);

    restoreFromSpam();

    assertMessageBackInInbox(subject);
  });
});
