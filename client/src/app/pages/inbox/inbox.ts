import { Component, ElementRef, HostListener, OnInit, ViewChild, computed, signal } from '@angular/core';
import { Router } from '@angular/router';

import { Icon } from '../../shared/icons/icon/icon';
import { LabelService, labelColorClass } from '../../services/label';
import { MailLabel } from '../../shared/model/label.model';
import { MessageService } from '../../services/message';
import { SplashService } from '../../services/splash';
import { BulkMessageAction, BulkMessageOptions, BulkMessageResponse, InboxMessage } from '../../shared/model/message.model';
import { SearchService } from '../../services/search';
import { formatMailDate } from '../../shared/utils/date-utils';
import { extractErrorMessage } from '../../shared/utils/http-error';
import { MailPollService } from '../../services/mail-poll';
import { SelectionMode, SortOrder, ToolbarMenu } from '../../shared/model/inbox.model';
import { MessageListSkeleton } from '../../shared/partials/message-list-skeleton/message-list-skeleton';

@Component({
  selector: 'app-inbox',
  imports: [Icon, MessageListSkeleton],
  host: { class: 'flex min-h-full flex-col' },
  templateUrl: './inbox.html',
})
export class Inbox implements OnInit {
  readonly pageSize = 50;
  readonly labelColorClass = labelColorClass;
  readonly formatMailDate = formatMailDate;
  messages = signal<InboxMessage[]>([]);
  loading = signal(false);
  actionLoading = signal(false);
  errorMessage = signal('');
  actionNotice = signal('');
  selectedIds = signal<Set<string>>(new Set());
  activeMenu = signal<ToolbarMenu>(null);
  draftLabelIds = signal<string[]>([]);
  pageIndex = signal(0);
  sortOrder = signal<SortOrder>('newest');
  searchTerm;
  totalMessages = computed(() => this.messageService.folderCounts().inbox);
  filteredMessages = computed(() => {
    const term = this.searchTerm().trim().toLowerCase();
    const filtered = term
      ? this.messages().filter((message) => [message.sender_address, message.subject, message.body].some((value) => value.toLowerCase().includes(term)))
      : this.messages();
    const direction = this.sortOrder() === 'newest' ? -1 : 1;
    return [...filtered].sort((first, second) => direction * (new Date(first.created_at).getTime() - new Date(second.created_at).getTime()));
  });
  pageCount = computed(() => Math.max(1, Math.ceil(this.totalMessages() / this.pageSize)));
  currentPage = computed(() => Math.min(this.pageIndex(), this.pageCount() - 1));
  pageMessages = computed(() => this.filteredMessages());
  pageStart = computed(() => this.filteredMessages().length === 0 ? 0 : this.currentPage() * this.pageSize + 1);
  pageEndCount = computed(() => this.currentPage() * this.pageSize + this.filteredMessages().length);
  pageEnd = computed(() => this.pageEndCount());
  selectedMessages = computed(() => {
    const ids = this.selectedIds();
    return this.messages().filter((message) => ids.has(message.id));
  });
  selectedCount = computed(() => this.selectedIds().size);
  allPageSelected = computed(() => this.pageMessages().length > 0 && this.pageMessages().every((message) => this.selectedIds().has(message.id)));
  somePageSelected = computed(() => this.pageMessages().some((message) => this.selectedIds().has(message.id)));
  selectedContainUnread = computed(() => this.selectedMessages().some((message) => !message.is_read));
  selectedContainUnstarred = computed(() => this.selectedMessages().some((message) => !message.is_starred));
  selectedContainNotImportant = computed(() => this.selectedMessages().some((message) => !message.is_important));
  @ViewChild('toolbarArea') toolbarArea?: ElementRef<HTMLElement>;

  constructor(public readonly mailPollService: MailPollService, private readonly messageService: MessageService, private readonly router: Router, private readonly searchService: SearchService, public readonly labelService: LabelService, private readonly splashService: SplashService) {
    this.searchTerm = this.searchService.searchTerm;
  }

  ngOnInit(): void {
    if (this.labelService.labels().length === 0) {
      this.labelService.loadLabels().subscribe({ error: () => undefined });
    }
    this.loadInboxMessages();
  }

  loadNewMail(): void {
    this.mailPollService.acknowledge();
    this.loadInboxMessages();
  }

  loadInboxMessages(): void {
    this.loading.set(true);
    this.errorMessage.set('');
    this.closeMenus();

    this.messageService.getInboxMessages(this.pageSize, this.currentPage() * this.pageSize, this.sortOrder() === 'oldest').subscribe({
      next: (messages) => {
        this.messages.set(messages.map((message) => this.normalizeInboxMessage(message)));
        this.selectedIds.set(new Set());
        this.loading.set(false);
        this.splashService.hide();
        this.messageService.refreshFolderCounts();
      },
      error: () => {
        this.errorMessage.set('Could not load inbox emails.');
        this.loading.set(false);
        this.splashService.hide();
      },
    });
  }

  openMessage(messageId: string): void {
    void this.router.navigate(['/message', messageId]);
  }

  toggleMenu(menu: Exclude<ToolbarMenu, null>): void {
    if (this.actionLoading()) {
      return;
    }
    const opening = this.activeMenu() !== menu;
    this.activeMenu.set(opening ? menu : null);
    if (opening && menu === 'labels') {
      this.draftLabelIds.set([]);
    }
  }

  closeMenus(): void {
    this.activeMenu.set(null);
  }

  @HostListener('document:click', ['$event'])
  closeMenusOnOutsideClick(event: MouseEvent): void {
    if (this.activeMenu() && !this.toolbarArea?.nativeElement.contains(event.target as Node)) {
      this.closeMenus();
    }
  }

  @HostListener('document:keydown.escape')
  closeMenusOnEscape(): void {
    this.closeMenus();
  }

  toggleCurrentPageSelection(): void {
    const next = new Set(this.selectedIds());
    if (this.allPageSelected()) {
      for (const message of this.pageMessages()) {
        next.delete(message.id);
      }
    }
    else {
      for (const message of this.pageMessages()) {
        next.add(message.id);
      }
    }
    this.selectedIds.set(next);
  }

  selectMode(mode: SelectionMode): void {
    const pageMessages = this.pageMessages();
    let selected: InboxMessage[] = [];
    if (mode === 'all') {
      selected = pageMessages;
    }
    else if (mode === 'read') {
      selected = pageMessages.filter((message) => message.is_read);
    }
    else if (mode === 'unread') {
      selected = pageMessages.filter((message) => !message.is_read);
    }
    else if (mode === 'starred') {
      selected = pageMessages.filter((message) => message.is_starred);
    }
    else if (mode === 'unstarred') {
      selected = pageMessages.filter((message) => !message.is_starred);
    }
    this.selectedIds.set(new Set(selected.map((message) => message.id)));
    this.closeMenus();
  }

  toggleMessageSelection(messageId: string): void {
    const next = new Set(this.selectedIds());
    if (next.has(messageId)) {
      next.delete(messageId);
    }
    else {
      next.add(messageId);
    }
    this.selectedIds.set(next);
  }

  archiveMessage(messageId: string): void {
    this.executeBulk('archive', {}, [messageId], true);
  }

  moveToTrash(messageId: string): void {
    this.executeBulk('trash', {}, [messageId], true);
  }

  toggleStar(message: InboxMessage): void {
    this.executeBulk(message.is_starred ? 'unstar' : 'star', {}, [message.id], true);
  }

  toggleImportant(message: InboxMessage): void {
    this.executeBulk(message.is_important ? 'mark_not_important' : 'mark_important', {}, [message.id], true);
  }

  runSelectedAction(action: BulkMessageAction, options: BulkMessageOptions = {}): void {
    this.executeBulk(action, options, [...this.selectedIds()]);
  }

  runVisibleAction(action: BulkMessageAction): void {
    this.executeBulk(action, {}, this.pageMessages().map((message) => message.id));
  }

  reportSelected(reportType: 'spam' | 'phishing'): void {
    const label = reportType === 'spam' ? 'spam' : 'phishing';
    if (!window.confirm(`Report the selected sender domains as ${label}? Each account contributes at most one report per domain.`)) {
      return;
    }
    this.executeBulk(reportType === 'spam' ? 'report_spam' : 'report_phishing', {}, [...this.selectedIds()], false, true);
  }

  toggleDraftLabel(labelId: string): void {
    this.draftLabelIds.update((ids) => ids.includes(labelId) ? ids.filter((id) => id !== labelId) : [...ids, labelId]);
  }

  applyBulkLabels(): void {
    if (this.draftLabelIds().length === 0) {
      this.errorMessage.set('Choose at least one label.');
      return;
    }
    this.executeBulk('add_labels', { label_ids: this.draftLabelIds() }, [...this.selectedIds()]);
  }

  goToPreviousPage(): void {
    if (this.currentPage() === 0) {
      return;
    }
    this.pageIndex.set(this.currentPage() - 1);
    this.loadInboxMessages();
    this.selectedIds.set(new Set());
    this.closeMenus();
  }

  goToNextPage(): void {
    if (this.currentPage() >= this.pageCount() - 1) {
      return;
    }
    this.pageIndex.set(this.currentPage() + 1);
    this.loadInboxMessages();
    this.selectedIds.set(new Set());
    this.closeMenus();
  }

  setSortOrder(order: SortOrder): void {
    this.sortOrder.set(order);
    this.pageIndex.set(0);
    this.loadInboxMessages();
    this.selectedIds.set(new Set());
    this.closeMenus();
  }

  messageLabels(labelIds: string[]): MailLabel[] {
    const ids = new Set(labelIds);
    return this.labelService.labels().filter((label) => ids.has(label.id));
  }

  private executeBulk(action: BulkMessageAction, options: BulkMessageOptions, targetIds: string[], quiet = false, reportConfirmed = false): void {
    const uniqueIds = [...new Set(targetIds)];
    if (uniqueIds.length === 0 || this.actionLoading()) {
      this.closeMenus();
      return;
    }

    if ((action === 'report_spam' || action === 'report_phishing') && !reportConfirmed) {
      return;
    }

    const before = new Map(this.messages().filter((message) => uniqueIds.includes(message.id)).map((message) => [message.id, message]));
    this.actionLoading.set(true);
    this.errorMessage.set('');
    this.actionNotice.set('');
    this.closeMenus();

    this.messageService.bulkUpdateMessages(uniqueIds, action, options).subscribe({
      next: (response) => {
        this.applyBulkResponse(response, before);
        this.selectedIds.set(new Set([...this.selectedIds()].filter((id) => !uniqueIds.includes(id))));
        this.actionLoading.set(false);
        this.messageService.refreshFolderCounts();
        if (!quiet) {
          this.actionNotice.set(this.bulkActionNotice(action, response.processed_ids.length));
        }
      },
      error: (error) => {
        this.errorMessage.set(extractErrorMessage(error, 'Could not update the selected messages.'));
        this.actionLoading.set(false);
      },
    });
  }

  private applyBulkResponse(response: BulkMessageResponse, before: Map<string, InboxMessage>): void {
    const updates = new Map(response.messages.map((message) => [message.id, this.normalizeInboxMessage(message)]));

    if (response.action === 'trash' || response.action === 'report_spam' || response.action === 'report_phishing') {
      for (const message of before.values()) {
        this.labelService.adjustMessageCount(message.label_ids, -1);
      }
    }
    else if (response.action === 'add_labels') {
      for (const [messageId, previous] of before) {
        const updated = updates.get(messageId);
        if (updated) {
          const previousIds = new Set(previous.label_ids);
          this.labelService.adjustMessageCount(updated.label_ids.filter((labelId) => !previousIds.has(labelId)), 1);
        }
      }
    }

    const deletedIds = new Set(response.deleted_ids);
    this.messages.update((messages) => messages
      .filter((message) => !deletedIds.has(message.id))
      .map((message) => updates.get(message.id) ?? message)
      .filter((message) => message.folder === 'inbox'));
  }

  private normalizeInboxMessage(message: InboxMessage | BulkMessageResponse['messages'][number]): InboxMessage {
    return {
      ...message,
      label_ids: message.label_ids,
      is_read: Boolean(message.is_read),
      is_starred: Boolean(message.is_starred),
      is_important: Boolean(message.is_important),
    };
  }

  private bulkActionNotice(action: BulkMessageAction, count: number): string {
    const subject = `${count} ${count === 1 ? 'message' : 'messages'}`;
    const descriptions = new Map<BulkMessageAction, string>([
      ['archive', `${subject} archived.`],
      ['trash', `${subject} moved to Trash.`],
      ['restore', `${subject} restored.`],
      ['permanent_delete', `${subject} permanently deleted.`],
      ['mark_read', `${subject} marked as read.`],
      ['mark_unread', `${subject} marked as unread.`],
      ['star', `${subject} starred.`],
      ['unstar', `${subject} unstarred.`],
      ['mark_important', `${subject} marked as important.`],
      ['mark_not_important', `${subject} marked as not important.`],
      ['move', `${subject} moved.`],
      ['add_labels', `Labels added to ${subject}.`],
      ['report_spam', `${subject} reported as spam and moved to Spam.`],
      ['report_phishing', `${subject} reported as phishing and moved to Spam.`],
    ]);
    return descriptions.get(action) ?? `${subject} updated.`;
  }
}
