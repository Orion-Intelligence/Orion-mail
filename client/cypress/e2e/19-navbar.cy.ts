import {
  changeSearchScope,
  clearNavbarSearch,
  goToSettingsFromProfile,
  navigateFolder,
  openComposeFromNavbar,
  openCreateLabelDialog,
  searchFromNavbar,
  toggleThemeFromProfile,
} from './controllers/19-navbar.controller';

import { loginAsTestUser } from './controllers/test-mail.controller';

describe('Orion Mail - Navbar', () => {

  beforeEach(() => {
    loginAsTestUser('test1');
    cy.visit('/inbox');
    cy.get('[data-testid="mail-navbar"]').should('be.visible');
    cy.get('[data-testid="inbox-section"]').should('be.visible');
  });

  it('searches from the navbar and clears the search', () => {
    searchFromNavbar('test2@mail.orionintelligence.org');
    clearNavbarSearch();
  });

  it('changes the search scope from the filter menu', () => {
    changeSearchScope();
  });

  it('toggles the theme from the profile menu', () => {
    toggleThemeFromProfile();
  });

  it('opens settings from the profile menu', () => {
    goToSettingsFromProfile();
  });

  it('navigates to the Sent folder', () => {
    navigateFolder('sent-section', '/sent');
  });

  it('navigates to the Spam folder', () => {
    navigateFolder('spam-section', '/spam');
  });

  it('opens the compose window from the navbar', () => {
    openComposeFromNavbar();
  });

  it('opens the create-label dialog from the sidebar', () => {
    openCreateLabelDialog();
  });

});
