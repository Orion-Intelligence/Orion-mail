import {
  generateDisposable,
  openSettings,
} from './controllers/20-settings.controller';

import {
  backToInboxFromSettings,
  deleteDisposableKeepPgp,
} from './controllers/28-settings-extended.controller';

import { loginAsTestUser } from './controllers/test-mail.controller';

describe('Orion Mail - Settings Extended', () => {

  beforeEach(() => {
    loginAsTestUser('test1');
    openSettings();
  });

  it('deletes a disposable email while keeping its PGP key', () => {
    const signature = `Cypress Keep PGP ${Date.now()}`;

    generateDisposable(signature);

    deleteDisposableKeepPgp(signature);
  });

  it('returns to the inbox from the settings back button', () => {
    backToInboxFromSettings();
  });

});
