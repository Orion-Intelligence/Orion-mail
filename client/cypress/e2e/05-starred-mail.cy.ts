import {
  assertMessageExistsInStarred,
  assertMessageNotInStarred,
  openStarred,
  starInboxMessage,
  unstarMessage,
} from './controllers/05-starred-mail.controller';

import {
  createTestMail,
  loginAsTestUser,
} from './controllers/test-mail.controller';

describe('Orion Mail - Starred', () => {

  let testSubject: string;

  beforeEach(() => {
    testSubject = `Cypress Starred Test ${Date.now()}`;

    createTestMail(
      'test1@mail.orionintelligence.org',
      testSubject,
      'Automated Cypress starred test message.'
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

  it('stars a message', () => {
    starInboxMessage(testSubject);

    openStarred();

    assertMessageExistsInStarred(testSubject);

    // Cleanup
    unstarMessage(testSubject);
  });

  it('unstars a message', () => {
    starInboxMessage(testSubject);

    openStarred();

    assertMessageExistsInStarred(testSubject);

    unstarMessage(testSubject);

    assertMessageNotInStarred(testSubject);
  });

});
