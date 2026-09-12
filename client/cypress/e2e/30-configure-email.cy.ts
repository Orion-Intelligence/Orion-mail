import {
  assertSetupScreen,
  loginAsUnconfiguredUser,
  submitConfiguration,
  visitConfigureEmail,
} from './controllers/30-configure-email.controller';

describe('Orion Mail - Configure Email', () => {

  beforeEach(() => {
    loginAsUnconfiguredUser();
  });

  it('shows the mailbox setup screen for an unconfigured account', () => {
    visitConfigureEmail();

    assertSetupScreen();
  });

  it('creates the mailbox and enters the inbox', () => {
    visitConfigureEmail();

    submitConfiguration();
  });

});
