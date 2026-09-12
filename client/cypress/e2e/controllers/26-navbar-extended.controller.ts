import { openProfileMenu } from './19-navbar.controller';

export function assertSearchBarVisible() {
  void cy.get('[data-testid="mail-search"]').should('be.visible');
  void cy.get('[data-testid="search-input"]').should('be.visible');
}

export function selectScopeThenReopenViaChip() {
  void cy.get('[data-testid="search-filter-button"]').should('be.visible').click();
  void cy.get('[data-testid="search-scope-menu"]').should('be.visible');

  void cy.get('[data-testid="search-scope-option-inbox"]').should('be.visible').click();
  void cy.get('[data-testid="search-scope-menu"]').should('not.exist');

  void cy.get('[data-testid="search-scope-chip"]')
    .should('be.visible')
    .and('contain.text', 'Inbox')
    .click();

  void cy.get('[data-testid="search-scope-menu"]').should('be.visible');
}

export function submitSearchFromSuggestion(term: string) {
  void cy.get('[data-testid="search-input"]').should('be.visible').clear().type(term);

  void cy.get('[data-testid="search-submit-option"]')
    .should('be.visible')
    .and('contain.text', term)
    .click();

  void cy.url().should('include', '/search');
}

export function openOrionAccount() {
  void cy.intercept('GET', '**/auth/me', (req) => {
    req.continue((res) => {
      if (res.body && typeof res.body === 'object') {
        res.body.orion_account_url = '/settings';
      }
    });
  }).as('meAccount');

  void cy.visit('/inbox');
  void cy.get('[data-testid="mail-navbar"]').should('be.visible');

  openProfileMenu();

  void cy.get('[data-testid="profile-orion-account"]').should('be.visible').click();

  void cy.url({ timeout: 15000 }).should('include', '/settings');
}

export function signOut() {
  void cy.intercept('POST', '**/auth/logout', {
    statusCode: 200,
    body: { message: 'Logged out', redirect_url: '/settings' },
  }).as('logoutRequest');

  openProfileMenu();

  void cy.get('[data-testid="profile-sign-out"]').should('be.visible').click();

  void cy.wait('@logoutRequest');
  void cy.url({ timeout: 15000 }).should('include', '/settings');
}

function expandMore() {
  void cy.get('[data-testid="more-folders-button"]')
    .should('be.visible')
    .then(($btn) => {
      if ($btn.attr('aria-expanded') !== 'true') {
        cy.wrap($btn).click();
      }
    });

  void cy.get('[data-testid="all-mail-section"]').should('be.visible');
}

export function navigateAllMailFromSidebar() {
  expandMore();

  void cy.get('[data-testid="all-mail-section"]').should('be.visible').click();
  void cy.url().should('include', '/all');
}

export function createLabelFromSidebarMore() {
  expandMore();

  void cy.get('[data-testid="sidebar-create-label"]').should('be.visible').click();

  void cy.get('[data-testid="label-dialog"]')
    .find('[data-testid="label-name-input"]')
    .should('be.visible');
}

export function manageLabelsFromSidebarMore() {
  expandMore();

  void cy.get('[data-testid="sidebar-manage-labels"]').should('be.visible').click();
  void cy.url().should('include', '/settings/labels');
}

export function settingsFromSidebarMore() {
  expandMore();

  void cy.get('[data-testid="sidebar-settings"]').should('be.visible').click();
  void cy.url().should('include', '/settings');
}

export function manageLabelsFromHeaderButton() {
  void cy.get('[data-testid="manage-labels-button"]')
    .filter(':visible')
    .first()
    .click();

  void cy.url().should('include', '/settings/labels');
}

export function toggleNavigationCollapse() {
  void cy.get('[data-testid="navigation-toggle"]')
    .invoke('attr', 'aria-expanded')
    .then((before) => {
      cy.get('[data-testid="navigation-toggle"]').click();
      cy.get('[data-testid="navigation-toggle"]')
        .invoke('attr', 'aria-expanded')
        .should('not.eq', before);
    });
}

export function logoLinkReturnsToInbox() {
  void cy.get('[data-testid="sent-section"]').should('be.visible').click();
  void cy.url().should('include', '/sent');

  void cy.get('[data-testid="navbar-logo-link"]').should('be.visible').click();
  void cy.url().should('include', '/inbox');
}
