export function openMessage(subject: string) {
  void cy.contains(
    '[data-testid="message-subject"]',
    subject,
    { timeout: 15000 }
  )
    .should('be.visible')
    .click();

  void cy.get('[data-testid="message-detail"]')
    .should('be.visible');
}

export function archiveFromDetail() {
  void cy.intercept({
    method: 'PUT',
    pathname: '**/messages/*/archive',
  }).as('archiveRequest');

  void cy.get('[data-testid="archive-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.wait('@archiveRequest')
    .its('response.statusCode')
    .should('eq', 200);

  void cy.url()
    .should('include', '/inbox');
}

export function markUnreadFromDetail() {
  void cy.intercept({
    method: 'PUT',
    pathname: '**/messages/*/unread',
  }).as('unreadRequest');

  void cy.get('[data-testid="mark-unread-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.wait('@unreadRequest')
    .its('response.statusCode')
    .should('eq', 200);

  void cy.url()
    .should('include', '/inbox');
}

export function viewOriginalSource() {
  void cy.intercept({
    method: 'GET',
    pathname: '**/messages/*/source',
  }).as('sourceRequest');

  void cy.get('[data-testid="more-button"]')
    .should('be.visible')
    .click();

  void cy.get('[data-testid="show-original-button"]')
    .should('be.visible')
    .click();

  void cy.wait('@sourceRequest')
    .its('response.statusCode')
    .should('eq', 200);

  void cy.get('[data-testid="source-dialog"]')
    .should('be.visible');
}

function openMoreMenu() {
  void cy.get('[data-testid="more-button"]')
    .should('be.visible')
    .click();
}

export function starFromDetail() {
  void cy.intercept({
    method: 'PUT',
    pathname: '**/messages/bulk',
  }).as('starRequest');

  openMoreMenu();

  void cy.get('[data-testid="star-menu-button"]')
    .should('be.visible')
    .click();

  void cy.wait('@starRequest')
    .then((interception) => {
      expect(interception.request.body.action).to.be.oneOf(['star', 'unstar']);
      expect(interception.response?.statusCode).to.eq(200);
    });
}

export function markImportantFromDetail() {
  void cy.intercept({
    method: 'PUT',
    pathname: '**/messages/bulk',
  }).as('importantRequest');

  openMoreMenu();

  void cy.get('[data-testid="important-menu-button"]')
    .should('be.visible')
    .click();

  void cy.wait('@importantRequest')
    .then((interception) => {
      expect(interception.request.body.action).to.be.oneOf(['mark_important', 'mark_not_important']);
      expect(interception.response?.statusCode).to.eq(200);
    });
}

export function reportSpamFromDetail() {
  cy.on('window:confirm', () => true);

  void cy.intercept({
    method: 'PUT',
    pathname: '**/messages/*/report',
  }).as('reportRequest');

  void cy.get('[data-testid="report-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.wait('@reportRequest')
    .its('response.statusCode')
    .should('eq', 200);

  void cy.url()
    .should('include', '/inbox');
}

export function replyAllFromDetail() {
  openMoreMenu();

  void cy.get('[data-testid="reply-all-menu-button"]')
    .should('be.visible')
    .click();

  void cy.get('[data-testid="inline-compose"]')
    .scrollIntoView();

  void cy.get('[data-testid="inline-compose"]')
    .find('[data-testid="compose-form"]')
    .should('be.visible');
}

export function moveToTrashFromDetail() {
  void cy.intercept({ method: 'PUT', pathname: '**/messages/*/trash' }).as('trashRequest');

  openMoreMenu();

  void cy.get('[data-testid="delete-menu-button"]')
    .should('be.visible')
    .click();

  void cy.wait('@trashRequest').its('response.statusCode').should('eq', 200);
  void cy.url().should('include', '/inbox');
}

export function blockSenderFromDetail() {
  void cy.intercept({ method: 'PUT', pathname: '**/messages/*/block-sender' }).as('blockRequest');

  openMoreMenu();

  void cy.get('[data-testid="block-sender-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.wait('@blockRequest').its('response.statusCode').should('eq', 200);
}

export function assertMessageGone(subject: string) {
  void cy.get('[data-testid="inbox-section"]', { timeout: 15000 })
    .should('be.visible')
    .and('not.contain.text', subject);
}
