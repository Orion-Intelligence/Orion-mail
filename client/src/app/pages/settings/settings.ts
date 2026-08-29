import { Component, OnInit, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { finalize } from 'rxjs';

import { Icon } from '../../shared/icons/icon/icon';
import { ConfigService } from '../../services/config';
import { MessageService } from '../../services/message';
import { extractErrorMessage } from '../../shared/utils/http-error';
import { SYSTEM_CONFIG_FIELDS } from '../../shared/constants/config.constants';
import { SystemConfig, SystemConfigField } from '../../shared/model/config.model';

@Component({
  selector: 'app-settings',
  imports: [Icon, ReactiveFormsModule],
  host: { class: 'flex min-h-full flex-col' },
  templateUrl: './settings.html',
})
export class Settings implements OnInit {
  readonly form = new FormGroup({ signature: new FormControl('', { nonNullable: true, validators: [Validators.maxLength(10000)] }) });
  readonly configFields = SYSTEM_CONFIG_FIELDS;
  readonly configForm = new FormGroup({ outgoing_attachment_max_size_mb: this.limitControl('outgoing_attachment_max_size_mb'), incoming_attachment_max_size_mb: this.limitControl('incoming_attachment_max_size_mb'), attachment_retention_hours: this.limitControl('attachment_retention_hours') });
  loading = signal(false);
  saving = signal(false);
  configLoading = signal(false);
  configSaving = signal(false);
  errorMessage = signal('');
  statusMessage = signal('');
  configErrorMessage = signal('');
  configStatusMessage = signal('');
  mailboxAddress = signal('');

  constructor(private readonly messageService: MessageService, private readonly configService: ConfigService, private readonly router: Router) {}

  ngOnInit(): void {
    this.loadSettings();
    this.loadSystemConfig();
  }

  loadSettings(): void {
    this.loading.set(true);
    this.errorMessage.set('');
    this.messageService.getMyMailbox().pipe(finalize(() => {
      this.loading.set(false);
    })).subscribe({
      next: (mailbox) => {
        this.mailboxAddress.set(mailbox.mailbox_address);
        this.form.reset({ signature: mailbox.signature ?? '' });
      },
      error: (error) => {
        this.errorMessage.set(extractErrorMessage(error, 'Could not load your settings.'));
      },
    });
  }

  saveSettings(): void {
    if (this.form.invalid || this.saving()) {
      this.form.markAllAsTouched();
      return;
    }

    this.saving.set(true);
    this.errorMessage.set('');
    this.statusMessage.set('');
    this.messageService.updateMailboxSettings(this.form.controls.signature.value).pipe(finalize(() => {
      this.saving.set(false);
    })).subscribe({
      next: () => {
        this.statusMessage.set('Settings saved.');
      },
      error: (error) => {
        this.errorMessage.set(extractErrorMessage(error, 'Could not save your settings.'));
      },
    });
  }

  loadSystemConfig(): void {
    this.configLoading.set(true);
    this.configErrorMessage.set('');
    this.configService.getSystemConfig().pipe(finalize(() => {
      this.configLoading.set(false);
    })).subscribe({
      next: (config) => {
        this.configForm.reset(config);
      },
      error: (error) => {
        this.configErrorMessage.set(extractErrorMessage(error, 'Could not load the attachment limits.'));
      },
    });
  }

  saveSystemConfig(): void {
    if (this.configForm.invalid || this.configSaving()) {
      this.configForm.markAllAsTouched();
      return;
    }

    this.configSaving.set(true);
    this.configErrorMessage.set('');
    this.configStatusMessage.set('');
    this.configService.updateSystemConfig(this.configForm.getRawValue() as SystemConfig).pipe(finalize(() => {
      this.configSaving.set(false);
    })).subscribe({
      next: (config) => {
        this.configForm.reset(config);
        this.configStatusMessage.set('Attachment limits saved.');
      },
      error: (error) => {
        this.configErrorMessage.set(extractErrorMessage(error, 'Could not save the attachment limits.'));
      },
    });
  }

  backToInbox(): void {
    void this.router.navigate(['/inbox']);
  }

  private limitControl(key: SystemConfigField['key']): FormControl<number> {
    const field = SYSTEM_CONFIG_FIELDS.find((option) => option.key === key);
    const minimum = field?.minimum ?? 1;
    const maximum = field?.maximum ?? Number.MAX_SAFE_INTEGER;
    return new FormControl(minimum, { nonNullable: true, validators: [Validators.required, Validators.min(minimum), Validators.max(maximum)] });
  }
}
