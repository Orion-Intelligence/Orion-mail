import {
  assertAttachmentExists,
  attachTestFile,
  fillAttachmentMail,
  openComposeForAttachment,
  openInboxMessage,
  sendAttachmentMail,
} from './controllers/10-attachments-mail.controller';

import {
  loginAsTestUser,
} from './controllers/test-mail.controller';

describe('Orion Mail - Attachments', () => {
  let subject: string;

  const receiver = 'test2@mail.orionintelligence.org';
  const fileName = 'cypress-attachment.txt';
  const fileContent = 'Orion Mail Cypress attachment test.';

  beforeEach(() => {
    subject = `Cypress Attachment Test ${Date.now()}`;

    loginAsTestUser('test1');

    cy.visit('/inbox');

    cy.get('[data-testid="inbox-section"]')
      .should('be.visible');
  });

  it('sends and receives a message with an attachment', () => {
    openComposeForAttachment();

    fillAttachmentMail(
      receiver,
      subject,
      'Automated Cypress attachment test message.'
    );

    attachTestFile(
      fileName,
      fileContent
    );

    sendAttachmentMail();

    loginAsTestUser('test2');

    cy.visit('/inbox');

    cy.contains(
      '[data-testid="message-subject"]',
      subject,
      {
        timeout: 15000,
      }
    ).should('be.visible');

    openInboxMessage(subject);

    assertAttachmentExists(fileName);
  });
});
