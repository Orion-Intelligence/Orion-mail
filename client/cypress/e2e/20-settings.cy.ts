import {
  assertMailboxAddress,
  openSettings,
  resetSignature,
  saveAttachmentRetention,
  saveSignature,
} from './controllers/20-settings.controller';

import { loginAsTestUser } from './controllers/test-mail.controller';

describe('Orion Mail - Settings', () => {

  beforeEach(() => {
    loginAsTestUser('test1');
    openSettings();
  });

  it('shows the mailbox address', () => {
    assertMailboxAddress('test1@mail.orionintelligence.org');
  });

  it('saves a custom signature', () => {
    saveSignature(`Cypress Signature ${Date.now()}`);
  });

  it('updates the attachment retention limit', () => {
    saveAttachmentRetention(24);
  });

  it('resets the main signature to the username', () => {
    saveSignature(`Cypress Signature ${Date.now()}`);

    resetSignature();
  });

});
