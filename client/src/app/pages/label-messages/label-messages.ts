import { Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';

import { Icon } from '../../shared/icons/icon/icon';
import { LabelService, labelColorClass } from '../../services/label';
import { MailLabel } from '../../shared/model/label.model';
import { MessageService } from '../../services/message';
import { MessageDetailResponse } from '../../shared/model/message.model';
import { SearchService } from '../../services/search';
import { formatMailDate } from '../../shared/utils/date-utils';

@Component({
  selector: 'app-label-messages',
  imports: [Icon],
  host: { class: 'flex min-h-full flex-col' },
  templateUrl: './label-messages.html',
})
export class LabelMessages implements OnInit {
  private readonly destroyRef = inject(DestroyRef);

  label = signal<MailLabel | null>(null);
  messages = signal<MessageDetailResponse[]>([]);
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
    return this.messages().filter((message) => [message.sender_address, message.receiver_address, message.subject, message.body].some((value) => value.toLowerCase().includes(term)));
  });

  constructor(private readonly route: ActivatedRoute, private readonly router: Router, private readonly labelService: LabelService, private readonly messageService: MessageService, private readonly searchService: SearchService) {
    this.searchTerm = this.searchService.searchTerm;
  }

  ngOnInit(): void {
    this.route.paramMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((params) => {
      const labelId = params.get('id');
      if (!labelId) {
        this.errorMessage.set('Label ID not found.');
        return;
      }
      this.loadMessages(labelId);
    });
  }

  loadMessages(labelId = this.label()?.id): void {
    if (!labelId) {
      return;
    }
    this.loading.set(true);
    this.errorMessage.set('');
    this.labelService.getLabelMessages(labelId).subscribe({
      next: (response) => {
        this.label.set(response.label);
        this.messages.set(response.messages);
        this.loading.set(false);
      },
      error: () => {
        this.errorMessage.set('Could not load messages for this label.');
        this.loading.set(false);
      },
    });
  }

  openMessage(message: MessageDetailResponse): void {
    void this.router.navigate(['/message', message.id], { queryParams: { fromLabel: this.label()?.id } });
  }

  moveToTrash(message: MessageDetailResponse): void {
    this.errorMessage.set('');
    this.messageService.moveToTrash(message.id).subscribe({
      next: () => {
        this.messages.update((messages) => messages.filter((item) => item.id !== message.id));
        this.labelService.adjustMessageCount(message.label_ids ?? [], -1);
        this.label.update((label) => label ? { ...label, message_count: Math.max(0, label.message_count - 1) } : label);
        this.messageService.refreshFolderCounts();
      },
      error: () => this.errorMessage.set('Could not move the email to Trash.'),
    });
  }

  correspondent(message: MessageDetailResponse): string {
    return message.direction === 'outgoing' ? `To: ${message.receiver_address.split('@')[0]}` : message.sender_address.split('@')[0];
  }

  manageLabels(): void {
    void this.router.navigate(['/settings/labels']);
  }
}
