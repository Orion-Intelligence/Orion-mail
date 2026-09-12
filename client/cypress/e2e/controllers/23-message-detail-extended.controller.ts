export function openMessage(subject: string) {
  void cy.contains('[data-testid="message-subject"]', subject, { timeout: 15000 })
    .should('be.visible')
    .click();

  void cy.get('[data-testid="message-detail"]')
    .should('be.visible');
}

export function backToInbox() {
  void cy.get('[data-testid="back-button"]')
    .should('be.visible')
    .click();

  void cy.url().should('include', '/inbox');

  void cy.get('[data-testid="inbox-section"]')
    .should('be.visible');
}

function openMoreMenu() {
  void cy.get('[data-testid="more-button"]')
    .should('be.visible')
    .click();
}

export function replyFromDetail() {
  openMoreMenu();

  void cy.get('[data-testid="reply-menu-button"]')
    .should('be.visible')
    .click();

  void cy.get('[data-testid="inline-compose"]')
    .scrollIntoView();

  void cy.get('[data-testid="inline-compose"]')
    .find('[data-testid="compose-form"]')
    .should('be.visible');
}

export function forwardFromDetail() {
  openMoreMenu();

  void cy.get('[data-testid="forward-menu-button"]')
    .should('be.visible')
    .click();

  void cy.get('[data-testid="inline-compose"]')
    .scrollIntoView();

  void cy.get('[data-testid="inline-compose"]')
    .find('[data-testid="compose-form"]')
    .should('be.visible');
}

export function moveToArchiveFromDetail() {
  void cy.intercept({ method: 'PUT', pathname: '**/messages/*/move' }).as('moveMessage');

  void cy.get('[data-testid="move-button"]')
    .should('be.visible')
    .click();

  void cy.contains('[role="menuitem"]', 'Archive')
    .should('be.visible')
    .click();

  void cy.wait('@moveMessage').then((interception) => {
    expect(interception.request.body.destination).to.eq('archive');
    expect(interception.response?.statusCode).to.eq(200);
  });

  void cy.url().should('include', '/inbox');
}

export function reportPhishingFromDetail() {
  void cy.intercept({ method: 'PUT', pathname: '**/messages/*/report' }).as('reportPhishing');

  openMoreMenu();

  void cy.contains('[data-testid="report-menu-button"]', 'Report phishing')
    .should('be.visible')
    .click();

  void cy.wait('@reportPhishing').then((interception) => {
    expect(interception.request.body.report_type).to.eq('phishing');
    expect(interception.response?.statusCode).to.eq(200);
  });

  void cy.url().should('include', '/inbox');
}

export function downloadFromDetail() {
  void cy.intercept({ method: 'GET', pathname: '**/messages/*/download' }).as('downloadMessage');

  openMoreMenu();

  void cy.get('[data-testid="download-message-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.wait('@downloadMessage').its('response.statusCode').should('eq', 200);
}

export function assertGoneFromInbox(subject: string) {
  void cy.get('[data-testid="inbox-section"]', { timeout: 15000 })
    .should('be.visible');

  void cy.contains('[data-testid="message-subject"]', subject)
    .should('not.exist');
}
