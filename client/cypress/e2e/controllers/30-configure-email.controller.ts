export function loginAsUnconfiguredUser() {
  void cy.setCookie('orion_mail_test_session', 'test4');

  // Ensure test4 starts without a mailbox so the setup screen renders.
  void cy.request({
    method: 'DELETE',
    url: '/mailboxes/me',
    headers: { 'x-requested-with': 'XMLHttpRequest' },
    failOnStatusCode: false,
  });
}

export function visitConfigureEmail() {
  void cy.visit('/configure-email');

  void cy.get('[data-testid="configure-email-section"]', { timeout: 15000 })
    .should('be.visible');
}

export function assertSetupScreen() {
  void cy.get('[data-testid="mailbox-address"]')
    .should('be.visible')
    .and('contain.text', 'test4@');

  void cy.get('[data-testid="account-name"]').should('be.visible');
  void cy.get('[data-testid="account-initial"]').should('be.visible');
}

export function submitConfiguration() {
  void cy.intercept({ method: 'POST', pathname: '**/mailboxes' }).as('createMailbox');

  void cy.get('[data-testid="create-email-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.wait('@createMailbox').its('response.statusCode').should('eq', 200);

  void cy.url({ timeout: 15000 }).should('include', '/inbox');
}
