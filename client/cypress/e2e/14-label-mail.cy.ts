import {
  applyLabelToSelectedMessage,
  assertLabelPage,
  assertMessageHasLabel,
  createLabel,
  openLabelFromSidebar,
  selectInboxMessage,
} from './controllers/14-label-mail.controller';

import {
  createTestMail,
  loginAsTestUser,
} from './controllers/test-mail.controller';

describe('Orion Mail - Labels', () => {
  it('creates a label and applies it to a message', () => {
    const timestamp = Date.now();

    const subject = `Cypress Label Test ${timestamp}`;
    const labelName = `Cypress Label ${timestamp}`;

    createTestMail(
      'test1@mail.orionintelligence.org',
      subject,
      'Automated Cypress label test message.'
    );

    loginAsTestUser('test1');

    cy.visit('/inbox');

    cy.contains(
      '[data-testid="message-subject"]',
      subject,
      { timeout: 15000 }
    ).should('be.visible');

    createLabel(labelName);

    selectInboxMessage(subject);

    applyLabelToSelectedMessage(labelName);

    assertMessageHasLabel(
      subject,
      labelName
    );

    openLabelFromSidebar(labelName);

    assertLabelPage(
      labelName,
      subject
    );
  });
});
