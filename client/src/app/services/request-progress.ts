import { HttpContextToken } from '@angular/common/http';
import { Injectable, signal } from '@angular/core';

export const SKIP_REQUEST_PROGRESS = new HttpContextToken<boolean>(() => false);

@Injectable({ providedIn: 'root' })
export class RequestProgressService {
  private pending = 0;
  private hideTimer?: ReturnType<typeof setTimeout>;

  readonly active = signal(false);

  start(): void {
    clearTimeout(this.hideTimer);
    this.pending += 1;
    this.active.set(true);
  }

  finish(): void {
    this.pending -= 1;
    if (this.pending === 0) {
      // Bridge consecutive requests without delaying the start of the bar.
      this.hideTimer = setTimeout(() => this.active.set(false), 120);
    }
  }
}
