import { Component, computed, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';

import { E2eService } from '../../../services/e2e';
import { Icon } from '../../icons/icon/icon';
import { E2E_MIN_PASSPHRASE_LENGTH } from '../../constants/e2e.constants';
import { E2eDialogView } from '../../model/e2e.model';
import { extractErrorMessage } from '../../utils/http-error';

@Component({
  selector: 'app-e2e-unlock-dialog',
  imports: [ReactiveFormsModule, Icon],
  templateUrl: './e2e-unlock-dialog.html',
})
export class E2eUnlockDialog {
  private readonly override = signal<E2eDialogView | null>(null);

  readonly e2e = inject(E2eService);
  readonly minLength = E2E_MIN_PASSPHRASE_LENGTH;
  readonly form = new FormGroup({ passphrase: new FormControl('', { nonNullable: true }), confirm: new FormControl('', { nonNullable: true }), recoveryCode: new FormControl('', { nonNullable: true }) });
  readonly view = computed<E2eDialogView>(() => this.override() ?? (this.recoveryCode() ? 'recovery-code' : this.e2e.prompt() === 'setup' ? 'setup' : this.e2e.prompt() === 'mismatch' ? 'mismatch' : this.e2e.prompt() === 'key-changed' ? 'key-changed' : 'unlock'));
  working = signal(false);
  errorMessage = signal('');
  recoveryCode = signal('');
  recoverySaved = signal(false);

  show(view: E2eDialogView | null): void {
    this.override.set(view);
    this.errorMessage.set('');
    this.form.reset();
  }

  private async run(action: () => Promise<void>, fallback: string): Promise<void> {
    if (this.working()) {
      return;
    }
    this.working.set(true);
    this.errorMessage.set('');
    try {
      await action();
      this.form.reset();
    }
    catch (error) {
      this.errorMessage.set(extractErrorMessage(error, fallback));
    }
    finally {
      this.working.set(false);
    }
  }

  private passphrasesMatch(): boolean {
    const { passphrase, confirm } = this.form.getRawValue();
    if (passphrase !== confirm) {
      this.errorMessage.set('The two passphrases do not match.');
    }
    return passphrase === confirm;
  }

  submit(): void {
    const { passphrase, recoveryCode } = this.form.getRawValue();
    const view = this.view();

    if (view === 'setup' && this.passphrasesMatch()) {
      void this.run(async () => {
        this.recoveryCode.set(await this.e2e.setup(passphrase));
        this.recoverySaved.set(false);
      }, 'Your encryption key could not be created.');
    }
    else if (view === 'unlock') {
      void this.run(() => this.e2e.unlock(passphrase), 'Your encryption key could not be unlocked.');
    }
    else if (view === 'forgot' && this.passphrasesMatch()) {
      void this.run(async () => {
        await this.e2e.recover(recoveryCode, passphrase);
        this.override.set(null);
      }, 'Your encryption key could not be recovered.');
    }
  }

  downloadRecoveryCode(): void {
    const text = `Orion Mail recovery code\nMailbox: ${this.e2e.mailboxAddress()}\nKey fingerprint: ${this.e2e.fingerprint()}\n\n${this.recoveryCode()}\n\nKeep this file somewhere safe and offline. Anyone with this code can read your encrypted mail. Orion Mail cannot recover it for you.\n`;
    const url = URL.createObjectURL(new Blob([text], { type: 'text/plain' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'orion-mail-recovery-code.txt';
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => {
      URL.revokeObjectURL(url);
    }, 0);
    this.recoverySaved.set(true);
  }

  finishSetup(): void {
    this.recoveryCode.set('');
    this.e2e.dismissPrompt();
  }

  reset(): void {
    void this.run(async () => {
      await this.e2e.reset();
      this.override.set(null);
    }, 'Your encryption key could not be reset.');
  }

  trustServerKey(): void {
    void this.run(() => this.e2e.trustServerKey(), 'The key could not be reloaded.');
  }

  trustChangedKeys(): void {
    this.e2e.acceptKeyChanges(this.e2e.keyChanges());
  }

  keepOldKeys(): void {
    this.e2e.keyChanges.set([]);
    this.e2e.dismissPrompt();
  }
}
