import { Component, computed, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';

import { MessageService } from '../../services/message';
import { SentMessage } from '../../shared/model/message.model';
import { LabelService, labelColorClass } from '../../services/label';
import { MailLabel } from '../../shared/model/label.model';
import { SearchService } from '../../services/search';
import { formatMailDate } from '../../shared/utils/date-utils';
import { Icon } from '../../shared/icons/icon/icon';
import { MessageListSkeleton } from '../../shared/partials/message-list-skeleton/message-list-skeleton';

@Component({
  selector: 'app-sent',
  imports: [Icon, MessageListSkeleton],
  host: { class: 'flex min-h-full flex-col' },
  templateUrl: './sent.html',
})
export class Sent implements OnInit {
  messages = signal<SentMessage[]>([]);
  loading = signal(false);
  errorMessage = signal('');
  searchTerm;
  formatMailDate = formatMailDate;
  readonly labelColorClass = labelColorClass;
  filteredMessages = computed(() => {
    const term = this.searchTerm().trim().toLowerCase();

    if (!term) {
      return this.messages();
    }

    return this.messages().filter((message) => {
      return (
        message.receiver_address.toLowerCase().includes(term) ||
        message.subject.toLowerCase().includes(term) ||
        message.body.toLowerCase().includes(term)
      );
    });
  });

  constructor( private readonly messageService: MessageService, private readonly router: Router, private readonly searchService: SearchService, private readonly labelService: LabelService, ) {
    this.searchTerm = this.searchService.searchTerm;
  }

  ngOnInit(): void {
    this.loadSentMessages();
  }

  loadSentMessages(): void {
    this.loading.set(true);
    this.errorMessage.set('');

    this.messageService.getSentMessages().subscribe({
      next: (messages) => {
        this.messages.set(messages.map((message) => ({ ...message, label_ids: message.label_ids })));
        this.loading.set(false);
        this.messageService.refreshFolderCounts();
      },

      error: () => {
        this.errorMessage.set('Could not load sent emails.');
        this.loading.set(false);
      },
    });
  }

  openMessage(messageId: string): void {
    void this.router.navigate(['/message', messageId], {
      queryParams: {
        from: 'sent',
      },
    });
  }

  moveToTrash(messageId: string): void {
    this.errorMessage.set('');
    const message = this.messages().find((item) => item.id === messageId);

    this.messageService.moveToTrash(messageId).subscribe({
      next: () => {
        this.messages.update((messages) => messages.filter((message) => message.id !== messageId));
        this.labelService.adjustMessageCount(message?.label_ids ?? [], -1);
        this.messageService.refreshFolderCounts();
      },

      error: () => {
        this.errorMessage.set('Could not move the email to Trash.');
      },
    });
  }

  messageLabels(labelIds: string[]): MailLabel[] {
    const ids = new Set(labelIds);
    return this.labelService.labels().filter((label) => ids.has(label.id));
  }
}
