import { Injectable, signal } from '@angular/core';

import { MessageService } from './message';
import { POLL_INTERVAL_MS } from '../shared/constants/mail-poll.constants';

@Injectable({
  providedIn: 'root',
})
export class MailPollService {
  private timer?: ReturnType<typeof setInterval>;
  private knownUnread = -1;

  readonly pendingNewMail = signal(0);

  constructor(private readonly messageService: MessageService) {}

  start(): void {
    if (this.timer) {
      return;
    }

    this.knownUnread = this.messageService.folderCounts().unread.inbox;
    this.timer = setInterval(() => this.poll(), POLL_INTERVAL_MS);
    document.addEventListener('visibilitychange', () => this.onVisibilityChange());
  }

  acknowledge(): void {
    this.pendingNewMail.set(0);
    this.knownUnread = this.messageService.folderCounts().unread.inbox;
  }

  requestNotificationPermission(): void {
    if (typeof Notification === 'undefined' || Notification.permission !== 'default') {
      return;
    }

    void Notification.requestPermission().catch(() => undefined);
  }

  private onVisibilityChange(): void {
    if (document.visibilityState === 'visible') {
      this.poll();
    }
  }

  private poll(): void {
    if (document.visibilityState !== 'visible') {
      return;
    }

    this.messageService.loadFolderCounts().subscribe({
      next: (counts) => this.handleCounts(counts.unread.inbox),
      error: () => undefined,
    });
  }

  private handleCounts(unreadInbox: number): void {
    if (this.knownUnread < 0) {
      this.knownUnread = unreadInbox;
      return;
    }

    const arrived = unreadInbox - this.knownUnread;
    this.knownUnread = unreadInbox;
    if (arrived <= 0) {
      return;
    }

    this.pendingNewMail.update((pending) => pending + arrived);
    this.notify(arrived);
  }

  private notify(arrived: number): void {
    if (typeof Notification === 'undefined' || Notification.permission !== 'granted') {
      return;
    }

    try {
      const notification = new Notification('Orion Mail', { body: arrived === 1 ? 'You have 1 new message' : `You have ${arrived} new messages`, tag: 'orion-mail-new' });
      notification.onclick = () => window.focus();
    }
    catch {
      return;
    }
  }
}
