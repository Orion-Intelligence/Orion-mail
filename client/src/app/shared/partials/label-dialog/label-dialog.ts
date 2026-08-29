import { HttpErrorResponse } from '@angular/common/http';
import { AfterViewInit, Component, ElementRef, HostListener, ViewChild, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { finalize } from 'rxjs';

import { LabelService } from '../../../services/label';
import { LABEL_COLOR_OPTIONS } from '../../constants/label.constants';
import { extractErrorMessage } from '../../utils/http-error';
import { Icon } from '../../icons/icon/icon';

@Component({
  selector: 'app-label-dialog',
  imports: [Icon, ReactiveFormsModule],
  templateUrl: './label-dialog.html',
})
export class LabelDialog implements AfterViewInit {
  readonly palette = LABEL_COLOR_OPTIONS;
  readonly form = new FormGroup({ name: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.maxLength(40)] }), color: new FormControl('#287fce', { nonNullable: true, validators: [Validators.required] }), });
  saving = signal(false);
  errorMessage = signal('');
  @ViewChild('nameInput') nameInput?: ElementRef<HTMLInputElement>;

  constructor(private readonly labelService: LabelService) {}

  ngAfterViewInit(): void {
    this.nameInput?.nativeElement.focus();
  }

  selectColor(color: string): void {
    this.form.controls.color.setValue(color);
  }

  close(): void {
    this.labelService.closeCreateDialog();
  }

  submit(): void {
    if (this.form.invalid || this.saving()) {
      this.form.markAllAsTouched();
      return;
    }

    this.saving.set(true);
    this.errorMessage.set('');
    this.labelService.createLabel({ name: this.form.controls.name.value.trim(), color: this.form.controls.color.value })
      .pipe(finalize(() => {
        this.saving.set(false);
      }))
      .subscribe({
        next: () => {
          this.close();
        },
        error: (error: HttpErrorResponse) => {
          this.errorMessage.set(extractErrorMessage(error, 'Could not create the label.'));
        },
      });
  }

  @HostListener('document:keydown.escape')
  closeOnEscape(): void {
    this.close();
  }
}
