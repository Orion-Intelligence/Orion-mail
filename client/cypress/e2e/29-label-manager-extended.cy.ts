import { createLabel } from './controllers/14-label-mail.controller';

import {
  assertLabelExists,
  openLabelManager,
} from './controllers/15-manage-labels.controller';

import {
  cancelDeletingLabel,
  cancelEditingLabel,
  changeLabelColorFromPalette,
  refreshLabels,
} from './controllers/29-label-manager-extended.controller';

import { loginAsTestUser } from './controllers/test-mail.controller';

describe('Orion Mail - Label Manager Extended', () => {

  beforeEach(() => {
    loginAsTestUser('test1');
    openLabelManager();
  });

  it('changes a label color from the edit palette', () => {
    const name = `Cypress Color ${Date.now()}`;

    createLabel(name);
    assertLabelExists(name);

    changeLabelColorFromPalette(name);
    assertLabelExists(name);
  });

  it('cancels editing a label', () => {
    const name = `Cypress Cancel Edit ${Date.now()}`;

    createLabel(name);
    assertLabelExists(name);

    cancelEditingLabel(name);
    assertLabelExists(name);
  });

  it('cancels deleting a label', () => {
    const name = `Cypress Cancel Delete ${Date.now()}`;

    createLabel(name);
    assertLabelExists(name);

    cancelDeletingLabel(name);
    assertLabelExists(name);
  });

  it('refreshes the label list', () => {
    const name = `Cypress Refresh ${Date.now()}`;

    createLabel(name);
    assertLabelExists(name);

    refreshLabels();
    assertLabelExists(name);
  });

});
