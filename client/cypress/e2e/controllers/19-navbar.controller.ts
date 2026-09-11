export function searchFromNavbar(term: string) {
  void cy.get('[data-testid="search-input"]')
    .should('be.visible')
    .clear()
    .type(`${term}{enter}`);

  void cy.url()
    .should('include', '/search');
}

export function clearNavbarSearch() {
  void cy.get('[data-testid="search-clear"]')
    .should('be.visible')
    .click();

  void cy.get('[data-testid="search-input"]')
    .should('have.value', '');
}

export function changeSearchScope() {
  void cy.get('[data-testid="search-filter-button"]')
    .should('be.visible')
    .click();

  void cy.get('[data-testid="search-scope-menu"]')
    .should('be.visible');

  void cy.get('[data-testid^="search-scope-option-"]')
    .first()
    .should('be.visible')
    .click();

  void cy.get('[data-testid="search-scope-menu"]')
    .should('not.exist');
}

export function openProfileMenu() {
  void cy.get('[data-testid="profile-menu-button"]')
    .should('be.visible')
    .click();

  void cy.get('[data-testid="profile-popover"]')
    .should('be.visible');
}

export function toggleThemeFromProfile() {
  openProfileMenu();

  void cy.get('[data-testid="profile-theme-toggle"]')
    .invoke('attr', 'aria-checked')
    .then((before) => {
      cy.get('[data-testid="profile-theme-toggle"]')
        .click();

      cy.get('[data-testid="profile-theme-toggle"]')
        .invoke('attr', 'aria-checked')
        .should('not.eq', before);
    });
}

export function goToSettingsFromProfile() {
  openProfileMenu();

  void cy.get('[data-testid="profile-settings"]')
    .should('be.visible')
    .click();

  void cy.url()
    .should('include', '/settings');
}

export function navigateFolder(testid: string, path: string) {
  void cy.get(`[data-testid="${testid}"]`)
    .should('be.visible')
    .click();

  void cy.url()
    .should('include', path);
}

export function openComposeFromNavbar() {
  void cy.get('[data-testid="compose-button"]')
    .should('be.visible')
    .click();

  void cy.get('[data-testid="compose-window"]')
    .find('[data-testid="compose-form"]')
    .should('be.visible');
}

export function openCreateLabelDialog() {
  void cy.get('[data-testid="create-label-button"]')
    .filter(':visible')
    .first()
    .click();

  void cy.get('[data-testid="label-dialog"]')
    .find('[data-testid="label-name-input"]')
    .should('be.visible');
}
