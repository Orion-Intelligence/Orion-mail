import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';

import { BrandService } from '../../../services/brand';
import { E2eService } from '../../../services/e2e';
import { ConfirmDialog } from '../../components/confirm-dialog/confirm-dialog';
import { Icon } from '../../icons/icon/icon';
import { E2E_MIN_PASSPHRASE_LENGTH } from '../../constants/e2e.constants';
import { extractErrorMessage } from '../../utils/http-error';

@Component({
  selector: 'app-e2e-settings',
  imports: [Icon, ReactiveFormsModule, ConfirmDialog],
  host: { class: 'block' },
  templateUrl: './e2e-settings.html',
})
export class E2eSettings implements OnInit {
  readonly e2e = inject(E2eService);
  readonly brand = inject(BrandService);
  readonly minLength = E2E_MIN_PASSPHRASE_LENGTH;
  readonly changeForm = new FormGroup({ current: new FormControl('', { nonNullable: true }), next: new FormControl('', { nonNullable: true }) });
  readonly groupedFingerprint = computed(() => this.e2e.fingerprint().match(/.{4}/g)?.join(' ') ?? '');
  working = signal(false);
  errorMessage = signal('');
  statusMessage = signal('');
  removeOpen = signal(false);

  ngOnInit(): void {
    void this.e2e.ensureLoaded();
  }

  private async run(action: () => Promise<void>, success: string, fallback: string): Promise<void> {
    if (this.working()) {
      return;
    }
    this.working.set(true);
    this.errorMessage.set('');
    this.statusMessage.set('');
    try {
      await action();
      this.statusMessage.set(success);
    }
    catch (error) {
      this.errorMessage.set(extractErrorMessage(error, fallback));
    }
    finally {
      this.working.set(false);
    }
  }

  changePassphrase(): void {
    const { current, next } = this.changeForm.getRawValue();
    void this.run(async () => {
      await this.e2e.changePassphrase(current, next);
      this.changeForm.reset();
    }, 'Passphrase changed.', 'The passphrase could not be changed.');
  }

  remove(): void {
    void this.run(async () => {
      await this.e2e.reset();
      this.removeOpen.set(false);
    }, 'Your encryption key was removed.', 'The encryption key could not be removed.');
  }

  trustServerKey(): void {
    void this.run(() => this.e2e.trustServerKey(), 'This browser now trusts the key stored for your mailbox.', 'The key could not be reloaded.');
  }
}
