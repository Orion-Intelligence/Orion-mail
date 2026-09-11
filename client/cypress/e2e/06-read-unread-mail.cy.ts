import {
  assertMessageIsRead,
  assertMessageIsUnread,
  markMessageAsRead,
  markMessageAsUnread,
} from './controllers/06-read-unread-mail.controller';

import {
  createTestMail,
  loginAsTestUser,
} from './controllers/test-mail.controller';

describe('Orion Mail - Read / Unread', () => {

  let testSubject: string;

  beforeEach(() => {
    testSubject = `Cypress Read Test ${Date.now()}`;

    createTestMail(
      'test1@mail.orionintelligence.org',
      testSubject,
      'Automated Cypress read and unread test message.'
    );

    loginAsTestUser('test1');

    cy.visit('/inbox');

    cy.get('[data-testid="inbox-section"]')
      .should('be.visible');

    cy.contains(
      '[data-testid="message-subject"]',
      testSubject
    ).should('be.visible');
  });

  it('marks an unread message as read', () => {
    assertMessageIsUnread(testSubject);

    markMessageAsRead(testSubject);

    assertMessageIsRead(testSubject);
  });

  it('marks a read message as unread', () => {
    markMessageAsRead(testSubject);

    assertMessageIsRead(testSubject);

    markMessageAsUnread(testSubject);

    assertMessageIsUnread(testSubject);
  });

});
