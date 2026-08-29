import { Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { AuthService } from '../../services/auth';
import { MessageService } from '../../services/message';
import { extractErrorMessage } from '../../shared/utils/http-error';

@Component({
  selector: 'app-configure-email',
  host: { class: 'block min-h-dvh' },
  templateUrl: './configure-email.html',
})
export class ConfigureEmail {
  private readonly authService = inject(AuthService);

  loading = signal(false);
  errorMessage = signal('');
  user = this.authService.currentUser;
  mailDomain = computed(() => this.user()?.mail_domain || 'mail.orionintelligence.org');
  mailboxUsername = computed(() => this.user()?.username.trim().toLowerCase() || '');
  mailboxAddress = computed(() => this.mailboxUsername() ? `${this.mailboxUsername()}@${this.mailDomain()}` : '');
  accountName = computed(() => this.user()?.full_name.trim() || this.user()?.username.trim() || 'Orion Intelligence account');
  accountDetail = computed(() => {
    const user = this.user();
    const email = user?.email.trim();
    const name = user?.full_name.trim();

    if (email && email.toLowerCase() !== name?.toLowerCase()) {
      return email;
    }
    return user?.username.trim() ? `@${user.username.trim()}` : '';
  });
  accountInitial = computed(() => this.accountName().charAt(0).toUpperCase() || 'O');

  constructor(private readonly messageService: MessageService, private readonly router: Router) {}

  submit(): void {
    if (!this.mailboxUsername() || this.loading()) {
      return;
    }

    this.loading.set(true);
    this.errorMessage.set('');
    this.messageService.configureMailbox().subscribe({
      next: () => void this.router.navigate(['/inbox']),
      error: (error) => {
        this.errorMessage.set(extractErrorMessage(error, 'Email address could not be configured.'));
        this.loading.set(false);
      },
    });
  }
}
