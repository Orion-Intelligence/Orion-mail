import {
  assertSearchBarVisible,
  createLabelFromSidebarMore,
  logoLinkReturnsToInbox,
  manageLabelsFromHeaderButton,
  manageLabelsFromSidebarMore,
  navigateAllMailFromSidebar,
  openOrionAccount,
  selectScopeThenReopenViaChip,
  settingsFromSidebarMore,
  signOut,
  submitSearchFromSuggestion,
  toggleNavigationCollapse,
} from './controllers/26-navbar-extended.controller';

import { loginAsTestUser } from './controllers/test-mail.controller';

describe('Orion Mail - Navbar Extended', () => {

  beforeEach(() => {
    loginAsTestUser('test1');
    cy.visit('/inbox');
    cy.get('[data-testid="mail-navbar"]').should('be.visible');
    cy.get('[data-testid="inbox-section"]').should('be.visible');
  });

  it('shows the search bar and reopens the scope menu through the chip', () => {
    assertSearchBarVisible();
    selectScopeThenReopenViaChip();
  });

  it('submits a search through the suggestion option', () => {
    submitSearchFromSuggestion('orion');
  });

  it('opens the Orion account link from the profile menu', () => {
    openOrionAccount();
  });

  it('toggles the sidebar with the navigation toggle', () => {
    toggleNavigationCollapse();
  });

  it('returns to the inbox from the navbar logo', () => {
    logoLinkReturnsToInbox();
  });

  it('opens All Mail from the sidebar more section', () => {
    navigateAllMailFromSidebar();
  });

  it('opens the create-label dialog from the sidebar more section', () => {
    createLabelFromSidebarMore();
  });

  it('opens the label manager from the sidebar more section', () => {
    manageLabelsFromSidebarMore();
  });

  it('opens settings from the sidebar more section', () => {
    settingsFromSidebarMore();
  });

  it('opens the label manager from the labels header button', () => {
    manageLabelsFromHeaderButton();
  });

  it('signs out from the profile menu', () => {
    signOut();
  });

});
