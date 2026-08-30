import { Injectable, inject, signal } from '@angular/core';

import { ComposeRequest } from '../shared/model/compose.model';
import { SendMessageRequest } from '../shared/model/message.model';
import { extractErrorMessage } from '../shared/utils/http-error';
import { MessageService } from './message';

@Injectable({
  providedIn: 'root',
})
export class ComposeService {
  private readonly messageService = inject(MessageService);
  private noticeTimer?: ReturnType<typeof setTimeout>;

  readonly request = signal<ComposeRequest | null>(null);
  readonly notice = signal('');
  readonly sendFailure = signal('');
  readonly sending = signal(0);

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

  dismissSendFailure(): void {
    this.sendFailure.set('');
  }

  send(data: SendMessageRequest): void {
    this.sending.update((count) => count + 1);
    this.messageService.sendMessage(data).subscribe({
      next: (response) => {
        this.sending.update((count) => Math.max(0, count - 1));
        this.messageService.refreshFolderCounts();
        this.showNotice(response.message);
      },

      error: (error) => {
        this.sending.update((count) => Math.max(0, count - 1));
        this.messageService.refreshFolderCounts();
        this.sendFailure.set(`${extractErrorMessage(error, 'Message could not be sent.')} It is waiting in your inbox.`);
      },
    });
  }
}
