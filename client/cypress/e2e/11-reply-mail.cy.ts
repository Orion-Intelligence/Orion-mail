import {
  assertReplyReceived,
  clickReply,
  openMessage,
  sendReply,
  typeReply,
} from './controllers/11-reply-mail.controller';

import {
  createTestMail,
  loginAsTestUser,
} from './controllers/test-mail.controller';

describe('Orion Mail - Reply', () => {
  let subject: string;
  let replyMessage: string;

  beforeEach(() => {
    subject = `Cypress Reply Test ${Date.now()}`;
    replyMessage = `Cypress automated reply ${Date.now()}`;

    createTestMail(
      'test1@mail.orionintelligence.org',
      subject,
      'Original Cypress message for reply testing.'
    );

    loginAsTestUser('test1');

    cy.visit('/inbox');

    cy.contains(
      '[data-testid="message-subject"]',
      subject,
      { timeout: 15000 }
    ).should('be.visible');
  });

  it('replies to a received message', () => {
    openMessage(subject);

    clickReply();

    typeReply(replyMessage);

    sendReply();

    loginAsTestUser('test2');

    cy.visit('/inbox');

    cy.get('[data-testid="inbox-message-list"]', {
      timeout: 15000,
    }).should('be.visible');

    cy.contains(
      '[data-testid="message-subject"]',
      subject,
      { timeout: 15000 }
    )
      .should('be.visible')
      .click();

    assertReplyReceived(replyMessage);
  });
});
