import {
  applyLabelFromDetail,
  closeTranslationDialogWithEscape,
  moveToTrashFromDetail,
  openMessage,
  openTrash,
  permanentlyDeleteFromDetail,
  restoreFromDetail,
  selectInboxMessage,
  translateFromDetail,
  trashSelected,
} from './controllers/24-message-detail-more.controller';

import { createLabel } from './controllers/14-label-mail.controller';

import {
  createTestMail,
  loginAsTestUser,
} from './controllers/test-mail.controller';

describe('Orion Mail - Message Detail More Actions', () => {

  let subject: string;

  beforeEach(() => {
    subject = `Cypress Detail More ${Date.now()}`;

    createTestMail(
      'test1@mail.orionintelligence.org',
      subject,
      'Automated Cypress message-detail extra-actions test.'
    );

    loginAsTestUser('test1');

    cy.visit('/inbox');

    cy.contains('[data-testid="message-subject"]', subject, { timeout: 15000 })
      .should('be.visible');
  });

  it('moves a message to Trash from the detail header', () => {
    openMessage(subject);

    moveToTrashFromDetail();
  });

  it('restores a message from the Trash detail view', () => {
    selectInboxMessage(subject);
    trashSelected();

    openTrash();
    openMessage(subject);

    restoreFromDetail();
  });

  it('permanently deletes a message from the Trash detail view', () => {
    selectInboxMessage(subject);
    trashSelected();

    openTrash();
    openMessage(subject);

    permanentlyDeleteFromDetail();
  });

  it('opens the translation dialog and requests a translation', () => {
    openMessage(subject);

    translateFromDetail('es');

    closeTranslationDialogWithEscape();
  });

  it('applies a label from the detail view', () => {
    createLabel(`Detail Label ${Date.now()}`);

    openMessage(subject);

    applyLabelFromDetail('');
  });

});
