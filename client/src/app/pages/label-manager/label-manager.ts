import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { finalize } from 'rxjs';

import { Icon } from '../../shared/icons/icon/icon';
import { LabelService, labelColorClass } from '../../services/label';
import { LABEL_COLOR_OPTIONS } from '../../shared/constants/label.constants';
import { MailLabel } from '../../shared/model/label.model';
import { extractErrorMessage } from '../../shared/utils/http-error';

@Component({
  selector: 'app-label-manager',
  imports: [Icon, ReactiveFormsModule],
  host: { class: 'flex min-h-full flex-col' },
  templateUrl: './label-manager.html',
})
export class LabelManager implements OnInit {
  readonly palette = LABEL_COLOR_OPTIONS;
  readonly labelColorClass = labelColorClass;
  readonly editForm = new FormGroup({ name: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.maxLength(40)] }), color: new FormControl('#287fce', { nonNullable: true, validators: [Validators.required] }), });
  saving = signal(false);
  deleting = signal(false);
  editingId = signal<string | null>(null);
  deleteCandidateId = signal<string | null>(null);
  errorMessage = signal('');
  statusMessage = signal('');

  constructor(public readonly labelService: LabelService, private readonly router: Router) {}

  ngOnInit(): void {
    this.reloadLabels();
  }

  reloadLabels(): void {
    this.errorMessage.set('');
    this.labelService.loadLabels().subscribe({
      error: () => this.errorMessage.set('Could not load your labels.'),
    });
  }

  openCreateDialog(): void {
    this.clearFeedback();
    this.labelService.openCreateDialog();
  }

  startEditing(label: MailLabel): void {
    this.clearFeedback();
    this.deleteCandidateId.set(null);
    this.editingId.set(label.id);
    this.editForm.reset({ name: label.name, color: label.color });
  }

  cancelEditing(): void {
    this.editingId.set(null);
  }

  saveLabel(labelId: string): void {
    if (this.editForm.invalid || this.saving()) {
      this.editForm.markAllAsTouched();
      return;
    }

    this.saving.set(true);
    this.clearFeedback();
    this.labelService.updateLabel(labelId, { name: this.editForm.controls.name.value.trim(), color: this.editForm.controls.color.value })
      .pipe(finalize(() => this.saving.set(false)))
      .subscribe({
        next: (label) => {
          this.editingId.set(null);
          this.statusMessage.set(`Label “${label.name}” updated.`);
        },
        error: (error: HttpErrorResponse) => this.errorMessage.set(this.errorDetail(error, 'Could not update the label.')),
      });
  }

  requestDelete(labelId: string): void {
    this.clearFeedback();
    this.editingId.set(null);
    this.deleteCandidateId.set(labelId);
  }

  cancelDelete(): void {
    this.deleteCandidateId.set(null);
  }

  deleteLabel(label: MailLabel): void {
    if (this.deleting()) {
      return;
    }

    this.deleting.set(true);
    this.clearFeedback();
    this.labelService.deleteLabel(label.id)
      .pipe(finalize(() => this.deleting.set(false)))
      .subscribe({
        next: () => {
          this.deleteCandidateId.set(null);
          this.statusMessage.set(`Label “${label.name}” deleted.`);
        },
        error: (error: HttpErrorResponse) => this.errorMessage.set(this.errorDetail(error, 'Could not delete the label.')),
      });
  }

  selectEditColor(color: string): void {
    this.editForm.controls.color.setValue(color);
  }

  backToInbox(): void {
    void this.router.navigate(['/inbox']);
  }

  private clearFeedback(): void {
    this.errorMessage.set('');
    this.statusMessage.set('');
  }

  private errorDetail(error: HttpErrorResponse, fallback: string): string {
    return extractErrorMessage(error, fallback);
  }
}
