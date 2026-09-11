import {
  assertMessageExistsInImportant,
  assertMessageNotInImportant,
  markMessageImportant,
  markMessageNotImportant,
  openImportant,
} from './controllers/04-important-mail.controller';

import {
  createTestMail,
  loginAsTestUser,
} from './controllers/test-mail.controller';

describe('Orion Mail - Important', () => {

  let testSubject: string;

  beforeEach(() => {
    testSubject = `Cypress Important Test ${Date.now()}`;

    createTestMail(
      'test1@mail.orionintelligence.org',
      testSubject,
      'Automated Cypress important test message.'
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

  it('marks a message as important', () => {
    markMessageImportant(testSubject);

    openImportant();

    assertMessageExistsInImportant(testSubject);

    // Cleanup
    markMessageNotImportant(testSubject);
  });

  it('marks a message as not important', () => {
    markMessageImportant(testSubject);

    openImportant();

    assertMessageExistsInImportant(testSubject);

    markMessageNotImportant(testSubject);

    assertMessageNotInImportant(testSubject);
  });

});
