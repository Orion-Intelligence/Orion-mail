import {
  assertForwardedBodyExists,
  assertForwardedMessageExists,
  clickForward,
  fillForwardReceiver,
  openMessage,
  sendForward,
} from './controllers/12-forward-mail.controller';

import {
  createTestMail,
  loginAsTestUser,
} from './controllers/test-mail.controller';

describe('Orion Mail - Forward', () => {
  let subject: string;
  let originalBody: string;

  beforeEach(() => {
    subject = `Cypress Forward Test ${Date.now()}`;
    originalBody = `Original Cypress forward body ${Date.now()}`;

    createTestMail(
      'test1@mail.orionintelligence.org',
      subject,
      originalBody
    );

    loginAsTestUser('test1');

    cy.visit('/inbox');

    cy.contains(
      '[data-testid="message-subject"]',
      subject,
      { timeout: 15000 }
    ).should('be.visible');
  });

  it('forwards a received message to another user', () => {
    openMessage(subject);

    clickForward();

    fillForwardReceiver(
      'test3@mail.orionintelligence.org'
    );

    sendForward();

    loginAsTestUser('test3');

    cy.visit('/inbox');

    assertForwardedMessageExists(subject);

    cy.contains(
      '[data-testid="message-subject"]',
      subject,
      { timeout: 15000 }
    ).click();

    assertForwardedBodyExists(originalBody);
  });
});
