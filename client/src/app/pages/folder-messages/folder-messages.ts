import { Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { Observable, of } from 'rxjs';

import { Icon } from '../../shared/icons/icon/icon';
import { ComposeService } from '../../services/compose';
import { LabelService, labelColorClass } from '../../services/label';
import { MailLabel } from '../../shared/model/label.model';
import { MessageService } from '../../services/message';
import { BulkMessageAction, MessageDetailResponse } from '../../shared/model/message.model';
import { SearchService, normalizeSearchScope, searchScopeParameters } from '../../services/search';
import { SearchScope } from '../../shared/model/search.model';
import { formatMailDate } from '../../shared/utils/date-utils';
import { extractErrorMessage } from '../../shared/utils/http-error';
import { FOLDER_VIEWS } from '../../shared/constants/folder-messages.constants';
import { SystemFolder } from '../../shared/model/folder-messages.model';

@Component({
  selector: 'app-folder-messages',
  imports: [Icon],
  host: { class: 'flex min-h-full flex-col' },
  templateUrl: './folder-messages.html',
})
export class FolderMessages implements OnInit {
  private readonly destroyRef = inject(DestroyRef);

  folder = signal<SystemFolder>('archive');
  messages = signal<MessageDetailResponse[]>([]);
  loading = signal(false);
  actionLoading = signal(false);
  errorMessage = signal('');
  searchQuery = signal('');
  submittedSearchScope = signal<SearchScope>('all');
  searchTerm;
  formatMailDate = formatMailDate;
  readonly labelColorClass = labelColorClass;
  view = computed(() => FOLDER_VIEWS[this.folder()]);
  canEmptyFolder = computed(() => this.folder() === 'trash' || this.folder() === 'spam' || this.folder() === 'drafts');
  canMarkFolderRead = computed(() => this.folder() === 'spam' || this.folder() === 'archive' || this.folder() === 'trash');
  title = computed(() => this.view().title);
  folderIcon = computed(() => this.view().icon);
  filteredMessages = computed(() => {
    if (this.folder() === 'search') {
      return this.messages();
    }
    const term = this.searchTerm().trim().toLowerCase();
    if (!term) {
      return this.messages();
    }
    return this.messages().filter((message) => [message.sender_address, message.receiver_address, message.subject, message.body].some((value) => value.toLowerCase().includes(term)));
  });

  constructor(private readonly route: ActivatedRoute, private readonly router: Router, private readonly messageService: MessageService, private readonly labelService: LabelService, private readonly searchService: SearchService, private readonly composeService: ComposeService) {
    this.searchTerm = this.searchService.searchTerm;
  }

  ngOnInit(): void {
    this.route.data.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((data) => {
      const folder = String(data['folder']);
      this.folder.set(folder in FOLDER_VIEWS ? folder as SystemFolder : 'archive');
      if (this.folder() !== 'search') {
        this.loadMessages();
      }
    });
    this.route.queryParamMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((parameters) => {
      if (this.folder() !== 'search') {
        return;
      }
      const query = (parameters.get('q') ?? '').trim();
      const scope = normalizeSearchScope(parameters.get('scope'));
      this.searchQuery.set(query);
      this.submittedSearchScope.set(scope);
      this.searchTerm.set(query);
      this.searchService.searchScope.set(scope);
      this.loadMessages();
    });
  }

  emptyCurrentFolder(): void {
    if (this.actionLoading() || !window.confirm(`Permanently delete every message in ${this.title()}? This cannot be undone.`)) {
      return;
    }

    this.actionLoading.set(true);
    this.errorMessage.set('');
    this.messageService.emptyFolder(this.folder()).subscribe({
      next: () => {
        this.messages.set([]);
        this.actionLoading.set(false);
        this.messageService.refreshFolderCounts();
      },
      error: (error) => {
        this.errorMessage.set(extractErrorMessage(error, `Could not empty ${this.title()}.`));
        this.actionLoading.set(false);
      },
    });
  }

  markCurrentFolderRead(): void {
    if (this.actionLoading()) {
      return;
    }

    this.actionLoading.set(true);
    this.errorMessage.set('');
    this.messageService.markFolderRead(this.folder()).subscribe({
      next: () => {
        this.messages.update((messages) => messages.map((message) => ({ ...message, is_read: true })));
        this.actionLoading.set(false);
        this.messageService.refreshFolderCounts();
      },
      error: (error) => {
        this.errorMessage.set(extractErrorMessage(error, `Could not mark ${this.title()} as read.`));
        this.actionLoading.set(false);
      },
    });
  }

  loadMessages(): void {
    if (this.folder() === 'search' && !this.searchQuery()) {
      this.messages.set([]);
      this.errorMessage.set('');
      this.loading.set(false);
      return;
    }
    this.loading.set(true);
    this.errorMessage.set('');
    this.folderRequest().subscribe({
      next: (messages) => {
        this.messages.set(messages.map((message) => ({ ...message, label_ids: message.label_ids })));
        this.loading.set(false);
        this.messageService.refreshFolderCounts();
      },
      error: () => {
        this.errorMessage.set(`Could not load ${this.title()}.`);
        this.loading.set(false);
      },
    });
  }

  openMessage(message: MessageDetailResponse): void {
    if (message.folder === 'drafts') {
      this.composeService.openDraft(message.id);
      return;
    }
    const queryParams = this.folder() === 'search'
      ? { from: 'search', q: this.searchQuery(), scope: this.submittedSearchScope() }
      : { from: this.folder() };
    void this.router.navigate(['/message', message.id], { queryParams });
  }

  restoreMessage(message: MessageDetailResponse): void {
    this.errorMessage.set('');
    this.messageService.restoreMessage(message.id).subscribe({
      next: (restored) => {
        if (message.folder === 'trash' || message.folder === 'spam') {
          this.labelService.adjustMessageCount(message.label_ids, 1);
        }
        this.replaceOrRemove(message.id, restored);
        this.messageService.refreshFolderCounts();
      },
      error: () => {
        this.errorMessage.set('Could not restore the email.');
      },
    });
  }

  archiveMessage(message: MessageDetailResponse): void {
    this.errorMessage.set('');
    this.messageService.archiveMessage(message.id).subscribe({
      next: (archived) => {
        this.replaceOrRemove(message.id, archived);
        this.messageService.refreshFolderCounts();
      },
      error: () => {
        this.errorMessage.set('Could not archive the email.');
      },
    });
  }

  moveToTrash(message: MessageDetailResponse): void {
    this.errorMessage.set('');
    this.messageService.moveToTrash(message.id).subscribe({
      next: () => {
        this.messages.update((messages) => messages.filter((item) => item.id !== message.id));
        this.labelService.adjustMessageCount(message.label_ids, -1);
        this.messageService.refreshFolderCounts();
      },
      error: () => {
        this.errorMessage.set('Could not move the email to Trash.');
      },
    });
  }

  permanentlyDelete(message: MessageDetailResponse): void {
    const prompt = message.folder === 'drafts' ? 'Discard this draft? This cannot be undone.' : 'Permanently delete this message? This cannot be undone.';
    if (!window.confirm(prompt)) {
      return;
    }

    this.errorMessage.set('');
    this.messageService.permanentlyDeleteMessage(message.id).subscribe({
      next: () => {
        this.messages.update((messages) => messages.filter((item) => item.id !== message.id));
        this.messageService.refreshFolderCounts();
      },
      error: () => {
        this.errorMessage.set(message.folder === 'drafts' ? 'Could not discard the draft.' : 'Could not permanently delete the email.');
      },
    });
  }

  toggleStar(message: MessageDetailResponse): void {
    this.runFlagAction(message, message.is_starred ? 'unstar' : 'star', 'Could not update the message star.');
  }

  toggleImportant(message: MessageDetailResponse): void {
    this.runFlagAction(message, message.is_important ? 'mark_not_important' : 'mark_important', 'Could not update the importance marker.');
  }

  correspondent(message: MessageDetailResponse): string {
    if (message.folder === 'drafts') {
      return 'Draft';
    }
    return message.direction === 'outgoing' ? `To: ${message.receiver_address.split('@')[0] || '(no recipient)'}` : message.sender_address.split('@')[0] ?? message.sender_address;
  }

  messageLabels(labelIds: string[]): MailLabel[] {
    const ids = new Set(labelIds);
    return this.labelService.labels().filter((label) => ids.has(label.id));
  }

  messageFolderName(message: MessageDetailResponse): string {
    const names = new Map([['inbox', 'Inbox'], ['sent', 'Sent'], ['archive', 'Archive'], ['drafts', 'Drafts'], ['spam', 'Spam'], ['trash', 'Trash']]);
    return names.get(message.folder) ?? message.folder;
  }

  viewHint(): string {
    if (this.folder() !== 'search' || !this.searchQuery()) {
      return this.view().hint;
    }
    return `“${this.searchQuery()}” in ${this.searchScopeLabel()}`;
  }

  searchScopeLabel(): string {
    const scope = this.submittedSearchScope();
    if (scope.startsWith('label:')) {
      const labelId = scope.slice('label:'.length);
      return this.labelService.labels().find((label) => label.id === labelId)?.name ?? 'Label';
    }
    const names = new Map([['all', 'All mail'], ['inbox', 'Inbox'], ['sent', 'Sent'], ['archive', 'Archive'], ['drafts', 'Drafts'], ['spam', 'Spam'], ['trash', 'Trash'], ['starred', 'Starred'], ['important', 'Important']]);
    return names.get(scope) ?? 'All mail';
  }

  private folderRequest(): Observable<MessageDetailResponse[]> {
    const requests = new Map<SystemFolder, () => Observable<MessageDetailResponse[]>>([
      ['archive', () => this.messageService.getArchivedMessages()],
      ['trash', () => this.messageService.getTrashMessages()],
      ['spam', () => this.messageService.getSpamMessages()],
      ['drafts', () => this.messageService.getDraftMessages()],
      ['starred', () => this.messageService.getStarredMessages()],
      ['important', () => this.messageService.getImportantMessages()],
      ['all', () => this.messageService.getAllMessages()],
      ['search', () => {
        const parameters = searchScopeParameters(this.submittedSearchScope());
        return this.searchQuery() ? this.messageService.searchMessages(this.searchQuery(), parameters.scope, parameters.labelId) : of([]);
      }],
    ]);
    const request = requests.get(this.folder());
    return request ? request() : of([]);
  }

  private runFlagAction(message: MessageDetailResponse, action: BulkMessageAction, failureText: string): void {
    if (this.actionLoading()) {
      return;
    }
    this.actionLoading.set(true);
    this.errorMessage.set('');
    this.messageService.bulkUpdateMessages([message.id], action).subscribe({
      next: (response) => {
        const updated = response.messages.at(0);
        if (updated) {
          this.replaceOrRemove(message.id, updated);
        }
        this.actionLoading.set(false);
      },
      error: () => {
        this.errorMessage.set(failureText);
        this.actionLoading.set(false);
      },
    });
  }

  private replaceOrRemove(messageId: string, updated: MessageDetailResponse): void {
    const normalized = { ...updated, label_ids: updated.label_ids };
    this.messages.update((messages) => this.belongsToView(normalized) ? messages.map((item) => item.id === messageId ? normalized : item) : messages.filter((item) => item.id !== messageId));
  }

  private belongsToView(message: MessageDetailResponse): boolean {
    const folder = this.folder();
    if (folder === 'search') {
      return this.matchesSubmittedSearch(message);
    }
    if (folder === 'starred') {
      return message.is_starred && message.folder !== 'trash' && message.folder !== 'spam';
    }
    if (folder === 'important') {
      return message.is_important && message.folder !== 'trash' && message.folder !== 'spam';
    }
    if (folder === 'all') {
      return message.folder !== 'trash' && message.folder !== 'spam' && message.folder !== 'drafts';
    }
    return message.folder === folder;
  }

  private matchesSubmittedSearch(message: MessageDetailResponse): boolean {
    const scope = this.submittedSearchScope();
    if (scope.startsWith('label:') && !message.label_ids.includes(scope.slice('label:'.length))) {
      return false;
    }
    if (scope === 'starred' && !message.is_starred) {
      return false;
    }
    if (scope === 'important' && !message.is_important) {
      return false;
    }
    if (['inbox', 'sent', 'archive', 'drafts', 'spam', 'trash'].includes(scope) && message.folder !== scope) {
      return false;
    }

    const searchableText = [message.sender_address, message.receiver_address, ...message.to_addresses, ...message.cc_addresses, message.subject, message.body].join(' ').toLowerCase();
    return this.searchQuery().toLowerCase().split(/\s+/).every((term) => searchableText.includes(term));
  }
}
