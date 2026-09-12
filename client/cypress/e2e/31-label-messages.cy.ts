import {
  applyLabelToSelectedMessage,
  createLabel,
  openLabelFromSidebar,
  selectInboxMessage,
} from './controllers/14-label-mail.controller';

import {
  clearLabelSearch,
  openLabelMessageRow,
  refreshLabelMessages,
  searchLabelNoMatch,
} from './controllers/31-label-messages.controller';

import {
  createTestMail,
  loginAsTestUser,
} from './controllers/test-mail.controller';

describe('Orion Mail - Label Messages', () => {

  let subject: string;

  beforeEach(() => {
    const timestamp = Date.now();
    subject = `Cypress Label Msg ${timestamp}`;
    const labelName = `Cypress Label Folder ${timestamp}`;

    createTestMail(
      'test1@mail.orionintelligence.org',
      subject,
      'Automated Cypress label-messages test.'
    );

    loginAsTestUser('test1');

    cy.visit('/inbox');

    cy.contains('[data-testid="message-subject"]', subject, { timeout: 15000 })
      .should('be.visible');

    createLabel(labelName);
    selectInboxMessage(subject);
    applyLabelToSelectedMessage(labelName);

    openLabelFromSidebar(labelName);

    cy.contains('[data-testid="message-subject"]', subject, { timeout: 15000 })
      .should('be.visible');
  });

  it('refreshes the label messages list', () => {
    refreshLabelMessages(subject);
  });

  it('opens a labeled message from its row', () => {
    openLabelMessageRow(subject);
  });

  it('clears a label search that matches nothing', () => {
    searchLabelNoMatch('zzz-no-such-message-zzz');
    clearLabelSearch(subject);
  });

});
