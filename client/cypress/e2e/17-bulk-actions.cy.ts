import {
  assertMessageGone,
  assertSelectedCount,
  assertSelectionCleared,
  bulkArchive,
  bulkMarkRead,
  bulkTrash,
  selectMessage,
} from './controllers/17-bulk-actions.controller';

import {
  createTestMail,
  loginAsTestUser,
} from './controllers/test-mail.controller';

describe('Orion Mail - Bulk Actions', () => {

  let subjectA: string;
  let subjectB: string;

  beforeEach(() => {
    const timestamp = Date.now();
    subjectA = `Cypress Bulk A ${timestamp}`;
    subjectB = `Cypress Bulk B ${timestamp}`;

    createTestMail(
      'test1@mail.orionintelligence.org',
      subjectA,
      'Automated Cypress bulk test message A.'
    );

    createTestMail(
      'test1@mail.orionintelligence.org',
      subjectB,
      'Automated Cypress bulk test message B.'
    );

    loginAsTestUser('test1');

    cy.visit('/inbox');

    cy.contains('[data-testid="message-subject"]', subjectA, { timeout: 15000 })
      .should('be.visible');
    cy.contains('[data-testid="message-subject"]', subjectB, { timeout: 15000 })
      .should('be.visible');
  });

  it('archives multiple selected messages in bulk', () => {
    selectMessage(subjectA);
    selectMessage(subjectB);

    assertSelectedCount(2);

    bulkArchive();

    assertMessageGone(subjectA);
    assertMessageGone(subjectB);
  });

  it('moves multiple selected messages to trash in bulk', () => {
    selectMessage(subjectA);
    selectMessage(subjectB);

    assertSelectedCount(2);

    bulkTrash();

    assertMessageGone(subjectA);
    assertMessageGone(subjectB);
  });

  it('marks multiple selected messages as read in bulk', () => {
    selectMessage(subjectA);
    selectMessage(subjectB);

    assertSelectedCount(2);

    bulkMarkRead();

    assertSelectionCleared();
  });

});
