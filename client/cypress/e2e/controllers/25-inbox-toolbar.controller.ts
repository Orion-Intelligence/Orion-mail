export function assertMessageVisible(subject: string) {
  void cy.contains('[data-testid="message-subject"]', subject, { timeout: 15000 })
    .should('be.visible');
}

export function assertMessageGone(subject: string) {
  void cy.get('[data-testid="inbox-section"]', { timeout: 15000 })
    .should('be.visible')
    .and('not.contain.text', subject);
}

function messageRow(subject: string) {
  return cy.contains('[data-testid="message-subject"]', subject, { timeout: 15000 })
    .closest('[data-testid="inbox-message-item"]');
}

export function archiveViaRowHover(subject: string) {
  void cy.intercept({ method: 'PUT', pathname: '**/messages/bulk' }).as('rowArchive');

  void messageRow(subject)
    .should('be.visible')
    .find('[data-testid="archive-message-button"]')
    .click({ force: true });

  void cy.wait('@rowArchive').then((interception) => {
    expect(interception.request.body.action).to.eq('archive');
    expect(interception.response?.statusCode).to.eq(200);
  });
}

export function trashViaRowHover(subject: string) {
  void cy.intercept({ method: 'PUT', pathname: '**/messages/bulk' }).as('rowTrash');

  void messageRow(subject)
    .should('be.visible')
    .find('[data-testid="trash-message-button"]')
    .click({ force: true });

  void cy.wait('@rowTrash').then((interception) => {
    expect(interception.request.body.action).to.eq('trash');
    expect(interception.response?.statusCode).to.eq(200);
  });
}

export function refreshInbox() {
  void cy.intercept({ method: 'GET', pathname: '**/messages/inbox' }).as('refreshInbox');

  void cy.get('[data-testid="refresh-inbox-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.wait('@refreshInbox').its('response.statusCode').should('eq', 200);
  void cy.get('[data-testid="inbox-section"]').should('be.visible');
}

function openInboxMoreMenu() {
  void cy.get('[data-testid="inbox-more-button"]').should('be.visible').click();
  void cy.get('[data-testid="inbox-more-menu"]').should('be.visible');
}

export function markVisibleRead() {
  void cy.intercept({ method: 'PUT', pathname: '**/messages/bulk' }).as('markVisibleRead');

  openInboxMoreMenu();
  void cy.get('[data-testid="mark-visible-read-button"]').should('be.visible').click();

  void cy.wait('@markVisibleRead').then((interception) => {
    expect(interception.request.body.action).to.eq('mark_read');
    expect(interception.response?.statusCode).to.eq(200);
  });
}

export function markVisibleUnread() {
  void cy.intercept({ method: 'PUT', pathname: '**/messages/bulk' }).as('markVisibleUnread');

  openInboxMoreMenu();
  void cy.get('[data-testid="mark-visible-unread-button"]').should('be.visible').click();

  void cy.wait('@markVisibleUnread').then((interception) => {
    expect(interception.request.body.action).to.eq('mark_unread');
    expect(interception.response?.statusCode).to.eq(200);
  });
}

export function assertNoticeVisible() {
  void cy.get('[data-testid="action-notice"]', { timeout: 15000 }).should('be.visible');
}

export function dismissNotice() {
  void cy.get('[data-testid="dismiss-notice-button"]').should('be.visible').click();
  void cy.get('[data-testid="action-notice"]').should('not.exist');
}

export function selectAllVisibleFromMoreMenu() {
  openInboxMoreMenu();
  void cy.get('[data-testid="select-all-visible-button"]').should('be.visible').click();
  void cy.get('[data-testid="selected-count"]').should('be.visible');
}

function openSelectMenu() {
  void cy.get('[data-testid="select-options-button"]').should('be.visible').click();
  void cy.get('[data-testid="select-menu"]').should('be.visible');
}

export function selectUnread() {
  openSelectMenu();
  void cy.get('[data-testid="select-unread-button"]').should('be.visible').click();
  // Selected count is state-dependent in a full suite (poll may deliver unread
  // mail); just confirm the filter ran and closed the menu.
  void cy.get('[data-testid="select-menu"]').should('not.exist');
}

export function selectReadExpectingSome() {
  openSelectMenu();
  void cy.get('[data-testid="select-read-button"]').should('be.visible').click();
  void cy.get('[data-testid="selected-count"]').should('be.visible');
}

export function selectStarred() {
  openSelectMenu();
  void cy.get('[data-testid="select-starred-button"]').should('be.visible').click();
  // Prior specs leave starred mail in the mailbox, so the count is not
  // deterministic here; just confirm the filter ran and closed the menu.
  void cy.get('[data-testid="select-menu"]').should('not.exist');
}

export function selectUnstarredExpectingSome() {
  openSelectMenu();
  void cy.get('[data-testid="select-unstarred-button"]').should('be.visible').click();
  void cy.get('[data-testid="selected-count"]').should('be.visible');
}

export function selectNone() {
  openSelectMenu();
  void cy.get('[data-testid="select-none-button"]').should('be.visible').click();
  void cy.get('[data-testid="selected-count"]').should('not.exist');
}

export function sortByNewest() {
  void cy.intercept({ method: 'GET', pathname: '**/messages/inbox' }).as('sortNewest');

  void cy.get('[data-testid="sort-button"]').should('be.visible').click();
  void cy.get('[data-testid="sort-menu"]').should('be.visible');
  void cy.get('[data-testid="sort-newest-button"]').should('be.visible').click();

  void cy.wait('@sortNewest').its('response.statusCode').should('eq', 200);
  void cy.get('[data-testid="inbox-section"]').should('be.visible');
}

export function selectMessage(subject: string) {
  void messageRow(subject)
    .should('be.visible')
    .within(() => {
      cy.get('[data-testid="message-select-checkbox"]').check({ force: true });
    });
}

function openBulkMoreMenu() {
  void cy.get('[data-testid="bulk-more-button"]').should('be.visible').click();
  void cy.get('[data-testid="bulk-more-menu"]').should('be.visible');
}

export function bulkMoreArchive(subject: string) {
  void cy.intercept({ method: 'PUT', pathname: '**/messages/bulk' }).as('bulkMoreArchive');

  selectMessage(subject);
  openBulkMoreMenu();
  void cy.get('[data-testid="more-archive-button"]').should('be.visible').click();

  void cy.wait('@bulkMoreArchive').then((interception) => {
    expect(interception.request.body.action).to.eq('archive');
    expect(interception.response?.statusCode).to.eq(200);
  });
}

export function bulkMoreTrash(subject: string) {
  void cy.intercept({ method: 'PUT', pathname: '**/messages/bulk' }).as('bulkMoreTrash');

  selectMessage(subject);
  openBulkMoreMenu();
  void cy.get('[data-testid="more-trash-button"]').should('be.visible').click();

  void cy.wait('@bulkMoreTrash').then((interception) => {
    expect(interception.request.body.action).to.eq('trash');
    expect(interception.response?.statusCode).to.eq(200);
  });
}

export function bulkMoreToggleRead(subject: string) {
  void cy.intercept({ method: 'PUT', pathname: '**/messages/bulk' }).as('bulkMoreRead');

  selectMessage(subject);
  openBulkMoreMenu();
  void cy.get('[data-testid="more-toggle-read-button"]').should('be.visible').click();

  void cy.wait('@bulkMoreRead').then((interception) => {
    expect(interception.request.body.action).to.be.oneOf(['mark_read', 'mark_unread']);
    expect(interception.response?.statusCode).to.eq(200);
  });
}

export function bulkMoreToggleStar(subject: string) {
  void cy.intercept({ method: 'PUT', pathname: '**/messages/bulk' }).as('bulkMoreStar');

  selectMessage(subject);
  openBulkMoreMenu();
  void cy.get('[data-testid="more-toggle-star-button"]').should('be.visible').click();

  void cy.wait('@bulkMoreStar').then((interception) => {
    expect(interception.request.body.action).to.be.oneOf(['star', 'unstar']);
    expect(interception.response?.statusCode).to.eq(200);
  });
}

export function bulkMoreToggleImportant(subject: string) {
  void cy.intercept({ method: 'PUT', pathname: '**/messages/bulk' }).as('bulkMoreImportant');

  selectMessage(subject);
  openBulkMoreMenu();
  void cy.get('[data-testid="more-toggle-important-button"]').should('be.visible').click();

  void cy.wait('@bulkMoreImportant').then((interception) => {
    expect(interception.request.body.action).to.be.oneOf(['mark_important', 'mark_not_important']);
    expect(interception.response?.statusCode).to.eq(200);
  });
}

export function bulkMoreReportSpam(subject: string) {
  cy.on('window:confirm', () => true);

  void cy.intercept({ method: 'PUT', pathname: '**/messages/bulk' }).as('bulkMoreSpam');

  selectMessage(subject);
  openBulkMoreMenu();
  void cy.get('[data-testid="more-report-spam-button"]').should('be.visible').click();

  void cy.wait('@bulkMoreSpam').then((interception) => {
    expect(interception.request.body.action).to.eq('report_spam');
    expect(interception.response?.statusCode).to.eq(200);
  });
}

export function bulkMoreReportPhishing(subject: string) {
  cy.on('window:confirm', () => true);

  void cy.intercept({ method: 'PUT', pathname: '**/messages/bulk' }).as('bulkMorePhishing');

  selectMessage(subject);
  openBulkMoreMenu();
  void cy.get('[data-testid="more-report-phishing-button"]').should('be.visible').click();

  void cy.wait('@bulkMorePhishing').then((interception) => {
    expect(interception.request.body.action).to.eq('report_phishing');
    expect(interception.response?.statusCode).to.eq(200);
  });
}
