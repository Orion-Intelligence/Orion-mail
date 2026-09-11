import {
  assertMessageExistsInSent,
  assertSentMessageContent,
  fillSendMail,
  openComposeForSend,
  openSent,
  openSentMessage,
  sendMail,
} from './controllers/08-sent-mail.controller';

import {
  loginAsTestUser,
} from './controllers/test-mail.controller';

describe('Orion Mail - Sent', () => {

  let receiver: string;
  let subject: string;
  let message: string;

  beforeEach(() => {
    receiver = 'test2@mail.orionintelligence.org';
    subject = `Cypress Sent Test ${Date.now()}`;
    message = 'Automated Cypress sent mail test message.';

    loginAsTestUser('test1');

    cy.visit('/inbox');

    cy.get('[data-testid="inbox-section"]')
      .should('be.visible');
  });

  it('sends a message and shows it in Sent', () => {
    openComposeForSend();

    fillSendMail(
      receiver,
      subject,
      message
    );

    sendMail();

    openSent();

    assertMessageExistsInSent(subject);
  });

  it('opens a sent message and verifies its content', () => {
    openComposeForSend();

    fillSendMail(
      receiver,
      subject,
      message
    );

    sendMail();

    openSent();

    assertMessageExistsInSent(subject);

    openSentMessage(subject);

    assertSentMessageContent(
      receiver,
      subject,
      message
    );
  });

});
