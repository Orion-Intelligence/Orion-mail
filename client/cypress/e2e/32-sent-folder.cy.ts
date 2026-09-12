import {
  fillSendMail,
  openComposeForSend,
  openSent,
  sendMail,
} from './controllers/08-sent-mail.controller';

import {
  clearFolderSearch,
  openSentRow,
  retrySentLoad,
  searchFolderNoMatch,
  visitSentWithLoadError,
} from './controllers/32-sent-folder.controller';

import { loginAsTestUser } from './controllers/test-mail.controller';

describe('Orion Mail - Sent Folder', () => {

  beforeEach(() => {
    loginAsTestUser('test1');
    cy.visit('/inbox');
    cy.get('[data-testid="inbox-section"]').should('be.visible');
  });

  it('clears a folder search that matches nothing', () => {
    const subject = `Cypress Sent Search ${Date.now()}`;

    openComposeForSend();
    fillSendMail('test2@mail.orionintelligence.org', subject, 'Sent folder search body.');
    sendMail();

    openSent();

    cy.contains('[data-testid="message-subject"]', subject, { timeout: 15000 })
      .should('be.visible');

    searchFolderNoMatch('zzz-no-such-message-zzz');
    clearFolderSearch(subject);
  });

  it('opens a sent message from its row', () => {
    const subject = `Cypress Sent Row ${Date.now()}`;

    openComposeForSend();
    fillSendMail('test2@mail.orionintelligence.org', subject, 'Sent folder row body.');
    sendMail();

    openSent();

    openSentRow(subject);
  });

  it('shows a retry button when the sent folder fails to load and recovers', () => {
    visitSentWithLoadError();
    retrySentLoad();
  });

});
