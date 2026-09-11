export function searchMail(term: string) {
  void cy.get('[data-testid="search-input"]')
    .should('be.visible')
    .clear()
    .type(term);

  void cy.intercept(
    {
      method: 'GET',
      pathname: '**/messages/search',
    },
    (req) => {
      const url = new URL(req.url);

      // Ignore navbar search-hint request.
      if (url.searchParams.get('limit') !== '6') {
        req.alias = 'searchResultsRequest';
      }
    }
  );

  void cy.get('[data-testid="search-input"]')
    .type('{enter}');

  void cy.url()
    .should('include', '/search');

  void cy.wait('@searchResultsRequest', {
    timeout: 15000,
  })
    .its('response.statusCode')
    .should('eq', 200);
}

export function assertSearchResultExists(subject: string) {
  void cy.contains(
    '[data-testid="message-subject"]',
    subject,
    {
      timeout: 15000,
    }
  ).should('be.visible');
}

export function clearMailSearch() {
  void cy.get('[data-testid="search-clear"]')
    .should('be.visible')
    .click();

  void cy.get('[data-testid="search-input"]')
    .should('have.value', '');
}

export function assertSearchResultNotExists(subject: string) {
  void cy.get('body')
    .should('not.contain.text', subject);
}
