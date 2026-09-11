import {
  assertSearchResultExists,
  clearMailSearch,
  searchMail,
} from './controllers/09-search-mail.controller';

import {
  createTestMail,
  loginAsTestUser,
} from './controllers/test-mail.controller';

describe('Orion Mail - Search', () => {

  let subject: string;

  beforeEach(() => {
    subject = `Cypress Search Test ${Date.now()}`;

    createTestMail(
      'test1@mail.orionintelligence.org',
      subject,
      'Automated Cypress search test message.'
    );

    loginAsTestUser('test1');

    cy.visit('/inbox');

    cy.contains(
      '[data-testid="message-subject"]',
      subject
    ).should('be.visible');
  });

  it('searches for a message by subject and clears the search', () => {
    searchMail(subject);

    assertSearchResultExists(subject);

    clearMailSearch();

    cy.get('[data-testid="search-input"]')
      .should('have.value', '');
  });

});
