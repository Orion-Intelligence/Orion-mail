import {
  createLabel,
} from './controllers/14-label-mail.controller';
import {
  loginAsTestUser,
} from './controllers/test-mail.controller';
import {
  assertLabelExists,
  assertLabelRemoved,
  deleteLabel,
  openLabelManager,
  renameLabel,
} from './controllers/15-manage-labels.controller';

describe('Orion Mail - Manage Labels', () => {
  beforeEach(() => {
    loginAsTestUser('test1');

    openLabelManager();
  });

  it('renames an existing label', () => {
    const timestamp = Date.now();
    const original = `Cypress Original ${timestamp}`;
    const renamed = `Cypress Renamed ${timestamp}`;

    createLabel(original);
    assertLabelExists(original);

    renameLabel(original, renamed);

    assertLabelExists(renamed);
    assertLabelRemoved(original);
  });

  it('deletes a label', () => {
    const name = `Cypress Delete ${Date.now()}`;

    createLabel(name);
    assertLabelExists(name);

    deleteLabel(name);
    assertLabelRemoved(name);
  });
});
