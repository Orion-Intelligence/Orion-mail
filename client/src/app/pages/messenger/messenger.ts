import { Component, OnDestroy, OnInit, computed, signal } from '@angular/core';
import { Subscription, finalize } from 'rxjs';
import { MessengerService } from '../../services/messenger';
import { Icon } from '../../shared/icons/icon/icon';
import { MessengerConversation, MessengerMessage, MessengerUser } from '../../shared/model/message.model';
import { extractErrorMessage } from '../../shared/utils/http-error';

type MessengerTab = 'chats' | 'users';

@Component({
  selector: 'app-messenger',
  imports: [Icon],
  host: { class: 'flex h-full min-h-0 w-full flex-1 flex-col overflow-hidden' },
  templateUrl: './messenger.html',
  styleUrls: ['./messenger.css'],
})
export class Messenger implements OnInit, OnDestroy {
  private messageRequest?: Subscription;
  private readonly messageCache = new Map<string, MessengerMessage[]>();
  private readonly drafts = new Map<string, string>();

  activeTab = signal<MessengerTab>('chats');
  users = signal<MessengerUser[]>([]);
  conversations = signal<MessengerConversation[]>([]);
  messages = signal<MessengerMessage[]>([]);
  selectedUser = signal<MessengerUser | null>(null);
  searchTerm = signal('');
  draftMessage = signal('');
  usersLoading = signal(false);
  conversationsLoading = signal(false);
  messagesLoading = signal(false);
  sending = signal(false);
  errorMessage = signal('');
  filteredUsers = computed(() => {
    const query = this.searchTerm().trim().toLowerCase();
    if (!query) {
      return this.users();
    }

    return this.users().filter((user) =>
      [user.full_name, user.username, user.mailbox_address]
        .some((value) => (value ?? '').toLowerCase().includes(query)),);
  });
  filteredConversations = computed(() => {
    const query = this.searchTerm().trim().toLowerCase();

    if (!query) {
      return this.conversations();
    }

    return this.conversations().filter((conversation) => {
      const user = conversation.other_user;

      return [
        user.full_name,
        user.username,
        user.mailbox_address,
        conversation.last_message,
      ].some((value) => (value ?? '').toLowerCase().includes(query));
    });
  });
  showingSearchResults = computed(() => this.searchTerm().trim().length > 0);

  constructor(private readonly messengerService: MessengerService) { }

  ngOnInit(): void {
    this.loadConversations();
    this.loadUsers();
  }

  loadConversations(background = false): void {
    if (!background) {
      this.conversationsLoading.set(true);
      this.errorMessage.set('');
    }

    this.messengerService.getConversations()
      .pipe(finalize(() => this.conversationsLoading.set(false)))
      .subscribe({
        next: (conversations) => {
          this.conversations.set(conversations);
        },
        error: (error) => {
          if (!background) {
            this.errorMessage.set(extractErrorMessage(error, 'Could not load chats.'));
          }
        },
      });
  }

  loadUsers(): void {
    this.usersLoading.set(true);
    this.errorMessage.set('');

    this.messengerService.getUsers('', 200, 0)
      .pipe(finalize(() => this.usersLoading.set(false)))
      .subscribe({
        next: (users) => {
          this.users.set(users);
        },
        error: (error) => {
          this.errorMessage.set(extractErrorMessage(error, 'Could not load Orion users.'));
        },
      });
  }

  refreshUsersFromSearch(): void {
    const query = this.searchTerm().trim();

    this.usersLoading.set(true);

    this.messengerService.getUsers(query, 200, 0)
      .pipe(finalize(() => this.usersLoading.set(false)))
      .subscribe({
        next: (users) => {
          this.users.set(users);
        },
        error: () => undefined,
      });
  }

  selectConversation(conversation: MessengerConversation): void {
    this.selectUser(conversation.other_user);
  }

  selectUser(user: MessengerUser): void {
    if (this.selectedUser()?.id === user.id) {
      return;
    }
    this.saveDraft();
    this.selectedUser.set(user);
    this.draftMessage.set(this.drafts.get(user.id) ?? '');
    this.loadMessages(user.id);
  }

  closeChat(): void {
    this.saveDraft();
    this.messageRequest?.unsubscribe();
    this.selectedUser.set(null);
    this.messages.set([]);
  }

  ngOnDestroy(): void {
    this.messageRequest?.unsubscribe();
  }

  private saveDraft(): void {
    const user = this.selectedUser();
    if (user) {
      this.drafts.set(user.id, this.draftMessage());
    }
  }

  loadMessages(otherUserId: string): void {
    this.messageRequest?.unsubscribe();
    this.messages.set(this.messageCache.get(otherUserId) ?? []);
    this.messagesLoading.set(!this.messageCache.has(otherUserId));
    this.errorMessage.set('');

    this.messageRequest = this.messengerService.getMessages(otherUserId)
      .pipe(finalize(() => this.messagesLoading.set(false)))
      .subscribe({
        next: (messages) => {
          this.messageCache.set(otherUserId, messages);
          this.messages.set(messages);
          this.loadConversations(true);
        },
        error: (error) => {
          this.errorMessage.set(extractErrorMessage(error, 'Could not load chat messages.'));
        },
      });
  }

  sendMessage(): void {
    const user = this.selectedUser();
    const body = this.draftMessage().trim();

    if (!user || !body || this.sending()) {
      return;
    }

    this.sending.set(true);
    this.errorMessage.set('');

    this.messengerService.sendMessage({
      receiver_user_id: user.id,
      body,
    })
      .pipe(finalize(() => this.sending.set(false)))
      .subscribe({
        next: (message) => {
          const updated = [...(this.messageCache.get(user.id) ?? []), message];
          this.messageCache.set(user.id, updated);
          if (this.selectedUser()?.id === user.id) {
            this.messages.set(updated);
            if (this.draftMessage().trim() === body) {
              this.draftMessage.set('');
              this.drafts.delete(user.id);
            }
          }
          else if (this.drafts.get(user.id)?.trim() === body) {
            this.drafts.delete(user.id);
          }
          this.loadConversations(true);
        },
        error: (error) => {
          this.errorMessage.set(extractErrorMessage(error, 'Could not send message.'));
        },
      });
  }

  userInitial(user: MessengerUser): string {
    return (user.full_name || user.username || user.mailbox_address || 'u')
      .charAt(0)
      .toUpperCase();
  }

  formatTime(value: string | null | undefined): string {
    if (!value) {
      return '';
    }

    return new Date(value).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    });
  }
}
