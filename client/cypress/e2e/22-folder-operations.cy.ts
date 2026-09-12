import {
  archiveSelected,
  assertGoneFromFolder,
  assertInFolder,
  emptyFolder,
  markFolderRead,
  moveToTrashFromList,
  openFolder,
  refreshFolder,
  selectInboxMessage,
  trashSelected,
} from './controllers/22-folder-operations.controller';

import {
  createTestMail,
  loginAsTestUser,
} from './controllers/test-mail.controller';

describe('Orion Mail - Folder Operations', () => {

  let subject: string;

  beforeEach(() => {
    subject = `Cypress Folder Ops ${Date.now()}`;

    createTestMail(
      'test1@mail.orionintelligence.org',
      subject,
      'Automated Cypress folder-operations test.'
    );

    loginAsTestUser('test1');

    cy.visit('/inbox');

    cy.contains('[data-testid="message-subject"]', subject, { timeout: 15000 })
      .should('be.visible');
  });

  it('loads the All mail view and refreshes it', () => {
    openFolder('all', 'All Mail');

    assertInFolder(subject);

    refreshFolder('all');

    assertInFolder(subject);
  });

  it('marks every message in Archive as read', () => {
    selectInboxMessage(subject);
    archiveSelected();

    openFolder('archive', 'Archive');
    assertInFolder(subject);

    markFolderRead('archive');
  });

  it('empties the Trash folder', () => {
    selectInboxMessage(subject);
    trashSelected();

    openFolder('trash', 'Trash');
    assertInFolder(subject);

    emptyFolder('trash');
  });

  it('moves a message to Trash from the Archive list', () => {
    selectInboxMessage(subject);
    archiveSelected();

    openFolder('archive', 'Archive');
    assertInFolder(subject);

    moveToTrashFromList(subject);

    assertGoneFromFolder(subject);
  });

});
