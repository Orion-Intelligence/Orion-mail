export function selectInboxMessage(subject: string) {
  void cy.contains('[data-testid="message-subject"]', subject, { timeout: 15000 })
    .closest('[data-testid="inbox-message-item"]')
    .should('be.visible')
    .within(() => {
      cy.get('[data-testid="message-select-checkbox"]')
        .should('be.visible')
        .check();
    });
}

export function archiveSelected() {
  void cy.intercept({ method: 'PUT', pathname: '**/messages/bulk' }).as('archiveSelected');

  void cy.get('[data-testid="archive-selected-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.wait('@archiveSelected').its('response.statusCode').should('eq', 200);
}

export function trashSelected() {
  void cy.intercept({ method: 'PUT', pathname: '**/messages/bulk' }).as('trashSelected');

  void cy.get('[data-testid="trash-selected-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.wait('@trashSelected').its('response.statusCode').should('eq', 200);
}

export function openFolder(path: string, title: string) {
  void cy.intercept({ method: 'GET', pathname: `**/messages/${path}` }).as(`load_${path}`);

  void cy.visit(`/${path}`);

  void cy.wait(`@load_${path}`).its('response.statusCode').should('eq', 200);

  void cy.get('[data-testid="folder-title"]', { timeout: 15000 })
    .should('be.visible')
    .and('contain.text', title);
}

export function assertInFolder(subject: string) {
  void cy.contains('[data-testid="message-subject"]', subject, { timeout: 15000 })
    .should('be.visible');
}

export function refreshFolder(path: string) {
  void cy.intercept({ method: 'GET', pathname: `**/messages/${path}` }).as(`refresh_${path}`);

  void cy.get('[data-testid="refresh-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.wait(`@refresh_${path}`).its('response.statusCode').should('eq', 200);
}

export function markFolderRead(path: string) {
  void cy.intercept({ method: 'PUT', pathname: `**/messages/folder/${path}/read` }).as('markFolderRead');

  void cy.get('[data-testid="mark-all-read-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.wait('@markFolderRead').its('response.statusCode').should('eq', 200);
}

export function emptyFolder(path: string) {
  cy.on('window:confirm', () => true);

  void cy.intercept({ method: 'DELETE', pathname: `**/messages/folder/${path}` }).as('emptyFolder');

  void cy.get('[data-testid="empty-folder-button"]')
    .should('be.visible')
    .and('not.be.disabled')
    .click();

  void cy.wait('@emptyFolder').its('response.statusCode').should('eq', 200);

  void cy.get('[data-testid="empty-message-state"]', { timeout: 15000 })
    .should('be.visible');
}

export function moveToTrashFromList(subject: string) {
  void cy.intercept({ method: 'PUT', pathname: '**/messages/*/trash' }).as('moveToTrash');

  void cy.contains('[data-testid="message-subject"]', subject, { timeout: 15000 })
    .closest('[data-testid="message-list-item"]')
    .should('be.visible')
    .find('[data-testid="move-to-trash-button"]')
    .click({ force: true });

  void cy.wait('@moveToTrash').its('response.statusCode').should('eq', 200);
}

export function assertGoneFromFolder(subject: string) {
  void cy.get('[data-testid="folder-title"]', { timeout: 15000 })
    .should('be.visible');

  void cy.contains('[data-testid="message-subject"]', subject)
    .should('not.exist');
}
