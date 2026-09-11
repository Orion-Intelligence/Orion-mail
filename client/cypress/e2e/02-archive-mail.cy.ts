import {
  assertMessageExistsInArchive,
  assertMessageExistsInInbox,
  openArchive,
  openInbox,
  restoreMessageFromArchive,
} from './controllers/02-archive-mail.controller';

import {
  createTestMail,
  loginAsTestUser,
} from './controllers/test-mail.controller';

describe('Orion Mail - Archive', () => {

  let testSubject: string;

  beforeEach(() => {
    testSubject = `Cypress Archive Test ${Date.now()}`;

    createTestMail(
      'test1@mail.orionintelligence.org',
      testSubject,
      'Automated Cypress archive test message.'
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

  it('archives a message from inbox', () => {
    cy.contains(
      '[data-testid="message-subject"]',
      testSubject
    )
      .closest('[data-testid="inbox-message-item"]')
      .should('be.visible')
      .within(() => {
        cy.get('[data-testid="message-select-checkbox"]')
          .should('be.visible')
          .check();
      });

    cy.get('[data-testid="archive-selected-button"]')
      .should('be.visible')
      .and('not.be.disabled')
      .click();

    cy.contains(
      '[data-testid="message-subject"]',
      testSubject
    ).should('not.exist');

    openArchive();

    assertMessageExistsInArchive(testSubject);

    // Cleanup
    restoreMessageFromArchive(testSubject);
  });

  it('restores an archived message back to inbox', () => {
    cy.contains(
      '[data-testid="message-subject"]',
      testSubject
    )
      .closest('[data-testid="inbox-message-item"]')
      .should('be.visible')
      .within(() => {
        cy.get('[data-testid="message-select-checkbox"]')
          .should('be.visible')
          .check();
      });

    cy.get('[data-testid="archive-selected-button"]')
      .should('be.visible')
      .and('not.be.disabled')
      .click();

    openArchive();

    assertMessageExistsInArchive(testSubject);

    restoreMessageFromArchive(testSubject);

    openInbox();

    assertMessageExistsInInbox(testSubject);
  });

});
