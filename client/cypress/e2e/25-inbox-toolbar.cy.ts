import {
  archiveViaRowHover,
  assertMessageGone,
  assertMessageVisible,
  assertNoticeVisible,
  bulkMoreArchive,
  bulkMoreReportPhishing,
  bulkMoreReportSpam,
  bulkMoreToggleImportant,
  bulkMoreToggleRead,
  bulkMoreToggleStar,
  bulkMoreTrash,
  dismissNotice,
  markVisibleRead,
  markVisibleUnread,
  refreshInbox,
  selectAllVisibleFromMoreMenu,
  selectNone,
  selectReadExpectingSome,
  selectStarred,
  selectUnread,
  selectUnstarredExpectingSome,
  sortByNewest,
  trashViaRowHover,
} from './controllers/25-inbox-toolbar.controller';

import {
  createTestMail,
  loginAsTestUser,
} from './controllers/test-mail.controller';

describe('Orion Mail - Inbox Toolbar', () => {

  let subjectA: string;
  let subjectB: string;

  beforeEach(() => {
    const timestamp = Date.now();
    subjectA = `Cypress Inbox A ${timestamp}`;
    subjectB = `Cypress Inbox B ${timestamp}`;

    createTestMail(
      'test1@mail.orionintelligence.org',
      subjectA,
      'Automated Cypress inbox-toolbar message A.'
    );

    createTestMail(
      'test1@mail.orionintelligence.org',
      subjectB,
      'Automated Cypress inbox-toolbar message B.'
    );

    loginAsTestUser('test1');

    cy.visit('/inbox');

    cy.contains('[data-testid="message-subject"]', subjectA, { timeout: 15000 })
      .should('be.visible');
    cy.contains('[data-testid="message-subject"]', subjectB, { timeout: 15000 })
      .should('be.visible');
  });

  it('archives and trashes messages via row hover actions', () => {
    archiveViaRowHover(subjectA);
    assertMessageGone(subjectA);
    assertMessageVisible(subjectB);

    trashViaRowHover(subjectB);
    assertMessageGone(subjectB);
  });

  it('refreshes the inbox', () => {
    refreshInbox();

    assertMessageVisible(subjectA);
    assertMessageVisible(subjectB);
  });

  it('marks visible messages read and unread from the more menu', () => {
    markVisibleRead();
    assertNoticeVisible();
    dismissNotice();

    markVisibleUnread();
    assertNoticeVisible();
  });

  it('selects all visible messages from the more menu', () => {
    selectAllVisibleFromMoreMenu();
  });

  it('filters the selection through the select menu', () => {
    markVisibleRead();
    dismissNotice();

    selectUnread();
    selectReadExpectingSome();
    selectStarred();
    selectUnstarredExpectingSome();
    selectNone();
  });

  it('sorts by newest through the sort menu', () => {
    sortByNewest();

    assertMessageVisible(subjectA);
    assertMessageVisible(subjectB);
  });

  it('archives and trashes through the bulk more menu', () => {
    bulkMoreArchive(subjectA);
    assertMessageGone(subjectA);

    bulkMoreTrash(subjectB);
    assertMessageGone(subjectB);
  });

  it('toggles read, star, and important through the bulk more menu', () => {
    bulkMoreToggleRead(subjectA);
    bulkMoreToggleStar(subjectA);
    bulkMoreToggleImportant(subjectA);

    assertMessageVisible(subjectA);
  });

  it('reports spam and phishing through the bulk more menu', () => {
    bulkMoreReportSpam(subjectA);
    assertMessageGone(subjectA);

    bulkMoreReportPhishing(subjectB);
    assertMessageGone(subjectB);
  });

});
