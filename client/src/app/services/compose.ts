import { Injectable, signal } from '@angular/core';

import { ComposeRequest } from '../shared/model/compose.model';

@Injectable({
  providedIn: 'root',
})
export class ComposeService {
  private noticeTimer?: ReturnType<typeof setTimeout>;

  readonly request = signal<ComposeRequest | null>(null);
  readonly notice = signal('');

  openNew(): void {
    this.request.set({ mode: 'new' });
  }

  openDraft(draftId: string): void {
    this.request.set({ mode: 'draft', draftId });
  }

  close(): void {
    this.request.set(null);
  }

  showNotice(text: string): void {
    clearTimeout(this.noticeTimer);
    this.notice.set(text);
    this.noticeTimer = setTimeout(() => {
      this.notice.set('');
    }, 4000);
  }
}
