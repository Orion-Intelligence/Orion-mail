import {
  assertMessageExistsInTrash,
  assertMessageNotInTrash,
  moveInboxMessageToTrash,
  openInboxFromSidebar,
  openTrash,
  permanentlyDeleteMessageFromTrash,
  restoreMessageFromTrash,
} from './controllers/03-trash-mail.controller';

import {
  createTestMail,
  loginAsTestUser,
} from './controllers/test-mail.controller';

describe('Orion Mail - Trash', () => {

  let testSubject: string;

  beforeEach(() => {
    testSubject = `Cypress Trash Test ${Date.now()}`;

    createTestMail(
      'test1@mail.orionintelligence.org',
      testSubject,
      'Automated Cypress trash test message.'
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

  it('moves a message from inbox to trash', () => {
    moveInboxMessageToTrash(testSubject);

    cy.contains(
      '[data-testid="message-subject"]',
      testSubject
    ).should('not.exist');

    openTrash();

    assertMessageExistsInTrash(testSubject);

    // Cleanup
    restoreMessageFromTrash(testSubject);
  });

  it('restores a message from trash back to inbox', () => {
    moveInboxMessageToTrash(testSubject);

    openTrash();

    assertMessageExistsInTrash(testSubject);

    restoreMessageFromTrash(testSubject);

    assertMessageNotInTrash(testSubject);

    openInboxFromSidebar();

    cy.contains(
      '[data-testid="message-subject"]',
      testSubject
    ).should('be.visible');
  });

  it('permanently deletes a message from trash', () => {
    moveInboxMessageToTrash(testSubject);

    openTrash();

    assertMessageExistsInTrash(testSubject);

    permanentlyDeleteMessageFromTrash(testSubject);

    assertMessageNotInTrash(testSubject);
  });

});
