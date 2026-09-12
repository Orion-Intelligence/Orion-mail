import {
  archiveFromDetail,
  assertMessageGone,
  blockSenderFromDetail,
  markImportantFromDetail,
  markUnreadFromDetail,
  moveToTrashFromDetail,
  openMessage,
  replyAllFromDetail,
  reportSpamFromDetail,
  starFromDetail,
  viewOriginalSource,
} from './controllers/18-message-actions.controller';

import {
  createTestMail,
  loginAsTestUser,
} from './controllers/test-mail.controller';

describe('Orion Mail - Message Detail Actions', () => {

  let subject: string;

  beforeEach(() => {
    subject = `Cypress Detail Action ${Date.now()}`;

    createTestMail(
      'test1@mail.orionintelligence.org',
      subject,
      'Automated Cypress message-detail action test.'
    );

    loginAsTestUser('test1');

    cy.visit('/inbox');

    cy.contains('[data-testid="message-subject"]', subject, { timeout: 15000 })
      .should('be.visible');
  });

  it('archives a message from the detail view', () => {
    openMessage(subject);

    archiveFromDetail();

    assertMessageGone(subject);
  });

  it('marks a message as unread from the detail view', () => {
    openMessage(subject);

    markUnreadFromDetail();
  });

  it('views the original source of a message', () => {
    openMessage(subject);

    viewOriginalSource();
  });

  it('stars a message from the detail view', () => {
    openMessage(subject);

    starFromDetail();
  });

  it('marks a message important from the detail view', () => {
    openMessage(subject);

    markImportantFromDetail();
  });

  it('replies to all from the detail view', () => {
    openMessage(subject);

    replyAllFromDetail();
  });

  it('reports a message as spam from the detail view', () => {
    openMessage(subject);

    reportSpamFromDetail();

    assertMessageGone(subject);
  });

  it('moves a message to trash from the detail view', () => {
    openMessage(subject);

    moveToTrashFromDetail();

    assertMessageGone(subject);
  });

  it('blocks the sender from the detail view', () => {
    openMessage(subject);

    blockSenderFromDetail(subject);
  });

});
