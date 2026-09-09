import { Component, EventEmitter, Input, Output } from '@angular/core';

@Component({
  selector: 'app-confirm-dialog',
  imports: [],
  host: { class: 'contents' },
  templateUrl: './confirm-dialog.html',
})
export class ConfirmDialog {
  @Input() open = false;
  @Input() title = 'Confirm action';
  @Input() message = '';
  @Input() confirmText = 'Confirm';
  @Input() cancelText = 'Cancel';
  @Input() destructive = false;
  @Input() busy = false;
  @Input() defaultActions = true;

  @Output() confirmed = new EventEmitter<void>();
  @Output() cancelled = new EventEmitter<void>();

  close(): void {
    if (!this.busy) {
      this.cancelled.emit();
    }
  }

  confirm(): void {
    if (!this.busy) {
      this.confirmed.emit();
    }
  }
}