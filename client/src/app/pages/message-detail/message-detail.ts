import { Component, ElementRef, HostListener, OnInit, SecurityContext, ViewChild, computed, inject, signal } from '@angular/core';
import { DomSanitizer } from '@angular/platform-browser';
import { ActivatedRoute, Router } from '@angular/router';

import { MessageService } from '../../services/message';
import { MessageDetailResponse, MessageFolder, MessageTranslationResponse, ReportType } from '../../shared/model/message.model';
import { LabelService, labelColorClass } from '../../services/label';
import { MailLabel } from '../../shared/model/label.model';
import { formatFullMailDate } from '../../shared/utils/date-utils';
import { Icon } from '../../shared/icons/icon/icon';
import { ComposeRequest } from '../../shared/model/compose.model';
import { Compose } from '../compose/compose';
import { SOURCE_NAMES, TRANSLATION_LANGUAGES } from '../../shared/constants/message-detail.constants';
import { MessageSource, RecipientMenu } from '../../shared/model/message-detail.model';

@Component({
  selector: 'app-message-detail',
  imports: [Icon, Compose],
  host: { class: 'flex min-h-full flex-col' },
  templateUrl: './message-detail.html',
})
export class MessageDetail implements OnInit {
  private readonly domSanitizer = inject(DomSanitizer);

  showRemoteImages = signal(false);
  threadMessages = signal<MessageDetailResponse[]>([]);
  imagePreviews = signal<Record<string, string>>({});
  conversation = computed(() => this.threadMessages().filter((item) => item.id !== this.message()?.id));
  renderedHtml = computed(() => this.prepareHtmlBody(this.message()?.body_html ?? '', this.showRemoteImages()));
  hasHtmlBody = computed(() => Boolean((this.message()?.body_html ?? '').trim()));
  blockedImageCount = computed(() => this.renderedHtml().blocked);
  message = signal<MessageDetailResponse | null>(null);
  loading = signal(false);
  errorMessage = signal('');
  labelErrorMessage = signal('');
  labelMenuOpen = signal(false);
  moveMenuOpen = signal(false);
  moreMenuOpen = signal(false);
  savingLabels = signal(false);
  actionLoading = signal(false);
  actionNotice = signal('');
  sourceDialogOpen = signal(false);
  sourceLoading = signal(false);
  messageSource = signal('');
  sourceCopied = signal(false);
  translationDialogOpen = signal(false);
  translationLoading = signal(false);
  translationTarget = signal('en');
  translationResult = signal<MessageTranslationResponse | null>(null);
  translationError = signal('');
  mailboxAddress = signal('');
  recipientMenuOpen = signal<RecipientMenu | null>(null);
  readonly translationLanguages = TRANSLATION_LANGUAGES;
  draftLabelIds = signal<string[]>([]);
  formatFullMailDate = formatFullMailDate;
  readonly labelColorClass = labelColorClass;
  source = signal<MessageSource>('inbox');
  fromLabelId = signal<string | null>(null);
  fromSearchQuery = signal('');
  fromSearchScope = signal('all');
  replyRequest = signal<ComposeRequest | null>(null);
  canReply = computed(() => {
    const currentMessage = this.message();
    return currentMessage !== null && currentMessage.folder !== 'drafts' && !this.isRemovedFolder(currentMessage.folder);
  });
  appliedLabels = computed(() => {
    const ids = new Set(this.message()?.label_ids ?? []);
    return this.labelService.labels().filter((label) => ids.has(label.id));
  });
  toRecipients = computed(() => {
    const currentMessage = this.message();
    if (!currentMessage) {
      return [];
    }
    const addresses = currentMessage.to_addresses?.length ? currentMessage.to_addresses : [currentMessage.receiver_address];
    return [...new Set(addresses.filter(Boolean))];
  });
  ccRecipients = computed(() => [...new Set((this.message()?.cc_addresses ?? []).filter(Boolean))]);
  @ViewChild('labelPicker') labelPicker?: ElementRef<HTMLElement>;
  @ViewChild('movePicker') movePicker?: ElementRef<HTMLElement>;
  @ViewChild('moreMenu') moreMenu?: ElementRef<HTMLElement>;

  constructor( private readonly route: ActivatedRoute, private readonly router: Router, private readonly messageService: MessageService, public readonly labelService: LabelService, ) {}

  loadImagePreviews(message: MessageDetailResponse): void {
    this.releaseImagePreviews();
    for (const attachment of message.attachments ?? []) {
      if (!attachment.content_type?.startsWith('image/') || attachment.status !== 'available') {
        continue;
      }

      this.messageService.downloadAttachment(attachment.id).subscribe({
        next: (blob) => {
          const objectUrl = URL.createObjectURL(new Blob([blob], { type: attachment.content_type }));
          this.imagePreviews.update((previews) => ({ ...previews, [attachment.id]: objectUrl }));
        },
        error: () => undefined,
      });
    }
  }

  releaseImagePreviews(): void {
    for (const objectUrl of Object.values(this.imagePreviews())) {
      URL.revokeObjectURL(objectUrl);
    }
    this.imagePreviews.set({});
  }

  loadThread(messageId: string): void {
    this.messageService.getThreadMessages(messageId).subscribe({
      next: (messages) => this.threadMessages.set(messages),
      error: () => this.threadMessages.set([]),
    });
  }

  openThreadMessage(messageId: string): void {
    void this.router.navigate(['/message', messageId], { queryParams: { from: this.source() } });
  }

  prepareHtmlBody(rawHtml: string, allowRemoteImages: boolean): { html: string; blocked: number } {
    const trimmed = rawHtml.trim();
    if (!trimmed) {
      return { html: '', blocked: 0 };
    }

    const sanitized = this.domSanitizer.sanitize(SecurityContext.HTML, trimmed) ?? '';
    if (allowRemoteImages) {
      return { html: sanitized, blocked: 0 };
    }

    const parsed = new DOMParser().parseFromString(sanitized, 'text/html');
    let blocked = 0;
    for (const image of Array.from(parsed.querySelectorAll('img'))) {
      const source = image.getAttribute('src') ?? '';
      if (/^https?:/i.test(source)) {
        image.removeAttribute('src');
        image.setAttribute('data-blocked-source', source);
        blocked += 1;
      }
    }
    return { html: parsed.body.innerHTML, blocked };
  }

  displayRemoteImages(): void {
    this.showRemoteImages.set(true);
  }

  ngOnInit(): void {
    const messageId = this.route.snapshot.paramMap.get('id');

    const from = this.route.snapshot.queryParamMap.get('from');
    const fromLabel = this.route.snapshot.queryParamMap.get('fromLabel');

    if (fromLabel) {
      this.source.set('label');
      this.fromLabelId.set(fromLabel);
    }
    else if (from === 'search') {
      this.source.set('search');
      this.fromSearchQuery.set(this.route.snapshot.queryParamMap.get('q') ?? '');
      this.fromSearchScope.set(this.route.snapshot.queryParamMap.get('scope') ?? 'all');
    }
    else if (from && from in SOURCE_NAMES) {
      this.source.set(from as MessageSource);
    }

    if (this.labelService.labels().length === 0) {
      this.labelService.loadLabels().subscribe({ error: () => undefined });
    }
    this.messageService.getMyMailbox().subscribe({
      next: (mailbox) => this.mailboxAddress.set(mailbox.mailbox_address.toLowerCase()),
      error: () => undefined,
    });

    if (!messageId) {
      this.errorMessage.set('Message ID not found.');
      return;
    }

    this.loadMessage(messageId);
  }

  loadMessage(messageId: string): void {
    this.loading.set(true);
    this.errorMessage.set('');
    this.replyRequest.set(null);
    this.showRemoteImages.set(false);
    this.threadMessages.set([]);
    this.loadThread(messageId);

    this.messageService.getMessageById(messageId).subscribe({
      next: (message) => {
        message.label_ids ??= [];
        this.message.set(message);
        this.draftLabelIds.set([...message.label_ids]);
        this.loadImagePreviews(message);
        if (message.direction === 'incoming') {
          this.messageService.refreshFolderCounts();
        }
        this.loading.set(false);
      },

      error: () => {
        this.errorMessage.set('Could not load the message.');
        this.loading.set(false);
      },
    });
  }

  goBack(): void {
    if (this.source() === 'label') {
      void this.router.navigate(this.fromLabelId() ? ['/label', this.fromLabelId()] : ['/inbox']);
      return;
    }
    if (this.source() === 'search') {
      void this.router.navigate(['/search'], { queryParams: { q: this.fromSearchQuery(), scope: this.fromSearchScope() } });
      return;
    }

    void this.router.navigate(['/', this.source()]);
  }

  toggleLabelMenu(): void {
    if (!this.message()) {
      return;
    }
    this.moveMenuOpen.set(false);
    this.moreMenuOpen.set(false);
    this.labelErrorMessage.set('');
    this.draftLabelIds.set([...(this.message()?.label_ids ?? [])]);
    this.labelMenuOpen.update((open) => !open);
  }

  toggleDraftLabel(labelId: string): void {
    this.draftLabelIds.update((ids) => ids.includes(labelId) ? ids.filter((id) => id !== labelId) : [...ids, labelId]);
  }

  applyLabels(): void {
    const currentMessage = this.message();
    if (!currentMessage || this.savingLabels()) {
      return;
    }

    const previousIds = currentMessage.label_ids ?? [];
    const nextIds = this.draftLabelIds();
    this.savingLabels.set(true);
    this.labelErrorMessage.set('');
    this.messageService.setMessageLabels(currentMessage.id, nextIds).subscribe({
      next: (updatedMessage) => {
        updatedMessage.label_ids ??= [];
        if (!this.isRemovedFolder(currentMessage.folder)) {
          const previous = new Set(previousIds);
          const next = new Set(updatedMessage.label_ids);
          this.labelService.adjustMessageCount(updatedMessage.label_ids.filter((id) => !previous.has(id)), 1);
          this.labelService.adjustMessageCount(previousIds.filter((id) => !next.has(id)), -1);
        }
        this.message.set(updatedMessage);
        this.draftLabelIds.set([...updatedMessage.label_ids]);
        this.labelMenuOpen.set(false);
        this.savingLabels.set(false);
      },
      error: () => {
        this.labelErrorMessage.set('Could not update labels.');
        this.savingLabels.set(false);
      },
    });
  }

  manageLabels(): void {
    this.labelMenuOpen.set(false);
    void this.router.navigate(['/settings/labels']);
  }

  labelIsSelected(label: MailLabel): boolean {
    return this.draftLabelIds().includes(label.id);
  }

  sourceName(): string {
    const source = this.source();
    if (source === 'label') {
      return this.labelService.labels().find((label) => label.id === this.fromLabelId())?.name ?? 'Label';
    }
    return SOURCE_NAMES[source];
  }

  isRemovedFolder(folder: string | undefined): boolean {
    return folder === 'trash' || folder === 'spam';
  }

  backTitle(): string {
    return `Back to ${this.sourceName()}`;
  }

  toggleMoveMenu(): void {
    this.labelMenuOpen.set(false);
    this.moreMenuOpen.set(false);
    this.moveMenuOpen.update((open) => !open);
  }

  toggleMoreMenu(): void {
    this.labelMenuOpen.set(false);
    this.moveMenuOpen.set(false);
    this.moreMenuOpen.update((open) => !open);
  }

  toggleRecipientMenu(menu: RecipientMenu): void {
    this.recipientMenuOpen.update((open) => open === menu ? null : menu);
  }

  closeActionMenus(): void {
    this.labelMenuOpen.set(false);
    this.moveMenuOpen.set(false);
    this.moreMenuOpen.set(false);
  }

  toggleStar(): void {
    const currentMessage = this.message();
    if (!currentMessage || this.actionLoading()) {
      return;
    }

    const action = currentMessage.is_starred ? 'unstar' : 'star';
    this.actionLoading.set(true);
    this.errorMessage.set('');
    this.closeActionMenus();
    this.messageService.bulkUpdateMessages([currentMessage.id], action).subscribe({
      next: (response) => {
        const updatedMessage = response.messages[0];
        if (updatedMessage) {
          this.message.set(updatedMessage);
        }
        this.actionNotice.set(action === 'star' ? 'Message starred.' : 'Star removed.');
        this.actionLoading.set(false);
      },
      error: () => {
        this.errorMessage.set('Could not update the message star.');
        this.actionLoading.set(false);
      },
    });
  }

  toggleImportant(): void {
    const currentMessage = this.message();
    if (!currentMessage || this.actionLoading()) {
      return;
    }

    const action = currentMessage.is_important ? 'mark_not_important' : 'mark_important';
    this.actionLoading.set(true);
    this.errorMessage.set('');
    this.closeActionMenus();
    this.messageService.bulkUpdateMessages([currentMessage.id], action).subscribe({
      next: (response) => {
        const updatedMessage = response.messages[0];
        if (updatedMessage) {
          this.message.set(updatedMessage);
        }
        this.actionNotice.set(action === 'mark_important' ? 'Marked as important.' : 'Importance marker removed.');
        this.actionLoading.set(false);
      },
      error: () => {
        this.errorMessage.set('Could not update the importance marker.');
        this.actionLoading.set(false);
      },
    });
  }

  moveMessage(destination: MessageFolder): void {
    const currentMessage = this.message();
    if (!currentMessage || this.actionLoading() || currentMessage.folder === destination) {
      this.closeActionMenus();
      return;
    }

    this.actionLoading.set(true);
    this.errorMessage.set('');
    this.closeActionMenus();
    this.messageService.moveMessage(currentMessage.id, destination).subscribe({
      next: () => {
        if (this.isRemovedFolder(currentMessage.folder) && !this.isRemovedFolder(destination)) {
          this.labelService.adjustMessageCount(currentMessage.label_ids ?? [], 1);
        }
        else if (!this.isRemovedFolder(currentMessage.folder) && this.isRemovedFolder(destination)) {
          this.labelService.adjustMessageCount(currentMessage.label_ids ?? [], -1);
        }
        this.messageService.refreshFolderCounts();
        this.actionLoading.set(false);
        this.goBack();
      },
      error: () => {
        this.errorMessage.set('Could not move the email.');
        this.actionLoading.set(false);
      },
    });
  }

  archiveMessage(): void {
    const currentMessage = this.message();
    if (!currentMessage || this.actionLoading()) {
      return;
    }
    this.actionLoading.set(true);
    this.errorMessage.set('');
    this.messageService.archiveMessage(currentMessage.id).subscribe({
      next: () => {
        this.messageService.refreshFolderCounts();
        this.actionLoading.set(false);
        this.goBack();
      },
      error: () => {
        this.errorMessage.set('Could not archive the email.');
        this.actionLoading.set(false);
      },
    });
  }

  moveToTrash(): void {
    const currentMessage = this.message();
    if (!currentMessage || this.actionLoading()) {
      return;
    }
    this.actionLoading.set(true);
    this.errorMessage.set('');
    this.messageService.moveToTrash(currentMessage.id).subscribe({
      next: () => {
        this.labelService.adjustMessageCount(currentMessage.label_ids ?? [], -1);
        this.messageService.refreshFolderCounts();
        this.actionLoading.set(false);
        this.goBack();
      },
      error: () => {
        this.errorMessage.set('Could not move the email to Trash.');
        this.actionLoading.set(false);
      },
    });
  }

  restoreMessage(): void {
    const currentMessage = this.message();
    if (!currentMessage || this.actionLoading()) {
      return;
    }
    this.actionLoading.set(true);
    this.errorMessage.set('');
    this.messageService.restoreMessage(currentMessage.id).subscribe({
      next: () => {
        if (this.isRemovedFolder(currentMessage.folder)) {
          this.labelService.adjustMessageCount(currentMessage.label_ids ?? [], 1);
        }
        this.messageService.refreshFolderCounts();
        this.actionLoading.set(false);
        this.goBack();
      },
      error: () => {
        this.errorMessage.set('Could not restore the email.');
        this.actionLoading.set(false);
      },
    });
  }

  permanentlyDelete(): void {
    const currentMessage = this.message();
    if (!currentMessage || this.actionLoading() || !window.confirm('Permanently delete this message? This cannot be undone.')) {
      return;
    }
    this.actionLoading.set(true);
    this.errorMessage.set('');
    this.messageService.permanentlyDeleteMessage(currentMessage.id).subscribe({
      next: () => {
        this.messageService.refreshFolderCounts();
        this.actionLoading.set(false);
        this.goBack();
      },
      error: () => {
        this.errorMessage.set('Could not permanently delete the email.');
        this.actionLoading.set(false);
      },
    });
  }

  @HostListener('document:click', ['$event'])
  closeMenusOnOutsideClick(event: MouseEvent): void {
    const target = event.target as Node;
    if (this.labelMenuOpen() && !this.labelPicker?.nativeElement.contains(target)) {
      this.labelMenuOpen.set(false);
    }
    if (this.moveMenuOpen() && !this.movePicker?.nativeElement.contains(target)) {
      this.moveMenuOpen.set(false);
    }
    if (this.moreMenuOpen() && !this.moreMenu?.nativeElement.contains(target)) {
      this.moreMenuOpen.set(false);
    }
    this.recipientMenuOpen.set(null);
  }

  @HostListener('document:keydown.escape')
  closeOverlaysOnEscape(): void {
    if (this.sourceDialogOpen()) {
      this.closeSourceDialog();
      return;
    }
    if (this.translationDialogOpen()) {
      this.closeTranslationDialog();
      return;
    }
    if (this.recipientMenuOpen()) {
      this.recipientMenuOpen.set(null);
      return;
    }

    this.closeActionMenus();
  }

  reply(): void {
    const currentMessage = this.message();
    if (!currentMessage) {
      return;
    }

    this.closeActionMenus();
    this.replyRequest.set({ mode: 'reply', to: this.replyTarget(currentMessage), subject: this.replySubject(currentMessage), body: this.quotedReplyBody(currentMessage), inReplyToMessageId: currentMessage.id });
  }

  replyAll(): void {
    const currentMessage = this.message();
    if (!currentMessage) {
      return;
    }

    const replyTarget = this.replyTarget(currentMessage);
    const localAddress = currentMessage.direction === 'incoming' ? currentMessage.receiver_address : currentMessage.sender_address;
    const excluded = new Set([replyTarget.toLowerCase(), this.mailboxAddress(), localAddress.toLowerCase()].filter(Boolean));
    const ccAddresses = [...new Set([...(currentMessage.to_addresses ?? []), ...(currentMessage.cc_addresses ?? [])]
      .map((address) => address.toLowerCase())
      .filter((address) => address && !excluded.has(address)))];
    this.closeActionMenus();
    this.replyRequest.set({ mode: 'reply-all', to: replyTarget, cc: ccAddresses, subject: this.replySubject(currentMessage), body: this.quotedReplyBody(currentMessage), inReplyToMessageId: currentMessage.id });
  }

  forward(): void {
    const currentMessage = this.message();
    if (!currentMessage) {
      return;
    }

    this.closeActionMenus();
    const forwardedBody = [
      '',
      '',
      '---------- Forwarded message ---------',
      `From: ${currentMessage.sender_address}`,
      `Date: ${formatFullMailDate(currentMessage.created_at)}`,
      `Subject: ${currentMessage.subject}`,
      `To: ${(currentMessage.to_addresses?.length ? currentMessage.to_addresses : [currentMessage.receiver_address]).join(', ')}`,
      ...(currentMessage.cc_addresses?.length ? [`Cc: ${currentMessage.cc_addresses.join(', ')}`] : []),
      '',
      currentMessage.body,
    ].join('\n');
    this.replyRequest.set({ mode: 'forward', subject: /^fwd:/i.test(currentMessage.subject) ? currentMessage.subject : `Fwd: ${currentMessage.subject}`, body: forwardedBody, forwardMessageId: currentMessage.id, forwardedAttachments: currentMessage.attachments.filter((attachment) => attachment.status === 'available') });
  }

  onReplySent(text: string): void {
    this.replyRequest.set(null);
    this.actionNotice.set(text);
  }

  replySubject(currentMessage: MessageDetailResponse): string {
    return /^re:/i.test(currentMessage.subject) ? currentMessage.subject : `Re: ${currentMessage.subject}`;
  }

  replyTarget(currentMessage: MessageDetailResponse): string {
    if (currentMessage.direction === 'incoming') {
      return currentMessage.reply_to_address || currentMessage.sender_address;
    }
    return currentMessage.to_addresses?.[0] || currentMessage.receiver_address;
  }

  quotedReplyBody(currentMessage: MessageDetailResponse): string {
    const quoted = currentMessage.body.split('\n').map((line) => `> ${line}`).join('\n');
    return `\n\nOn ${formatFullMailDate(currentMessage.created_at)}, ${currentMessage.sender_address} wrote:\n${quoted}`;
  }

  markUnread(): void {
    const currentMessage = this.message();
    if (!currentMessage || currentMessage.direction !== 'incoming' || this.actionLoading()) {
      return;
    }

    this.actionLoading.set(true);
    this.errorMessage.set('');
    this.closeActionMenus();
    this.messageService.markMessageUnread(currentMessage.id).subscribe({
      next: () => {
        this.actionLoading.set(false);
        this.goBack();
      },
      error: () => {
        this.errorMessage.set('Could not mark the email as unread.');
        this.actionLoading.set(false);
      },
    });
  }

  reportAs(reportType: ReportType): void {
    const currentMessage = this.message();
    if (!currentMessage || currentMessage.direction !== 'incoming' || this.actionLoading()) {
      return;
    }

    const domain = currentMessage.safety?.sender_domain ?? currentMessage.sender_address.split('@')[1];
    const label = reportType === 'phishing' ? 'phishing' : 'spam';
    if (!window.confirm(`Report ${domain} as ${label}? Your account contributes one domain report, so repeated reports will not increase the counter.`)) {
      return;
    }

    this.actionLoading.set(true);
    this.errorMessage.set('');
    this.closeActionMenus();
    this.messageService.reportSender(currentMessage.id, reportType).subscribe({
      next: () => {
        if (!this.isRemovedFolder(currentMessage.folder)) {
          this.labelService.adjustMessageCount(currentMessage.label_ids ?? [], -1);
        }
        this.messageService.refreshFolderCounts();
        this.actionLoading.set(false);
        this.goBack();
      },
      error: () => {
        this.errorMessage.set(`Could not report the sender as ${label}.`);
        this.actionLoading.set(false);
      },
    });
  }

  toggleBlockSender(): void {
    const currentMessage = this.message();
    if (!currentMessage || currentMessage.direction !== 'incoming' || this.actionLoading()) {
      return;
    }

    const safety = currentMessage.safety;
    const domain = safety?.sender_domain ?? currentMessage.sender_address.split('@')[1];
    if (safety?.globally_blocked) {
      this.actionNotice.set(`${domain} is blocked globally and cannot be unblocked from this mailbox.`);
      this.closeActionMenus();
      return;
    }

    if (safety?.sender_blocked) {
      this.actionLoading.set(true);
      this.closeActionMenus();
      this.messageService.unblockSender(currentMessage.id).subscribe({
        next: (updatedMessage) => {
          this.message.set(updatedMessage);
          this.actionNotice.set(`Future messages from ${domain} are allowed again.`);
          this.actionLoading.set(false);
        },
        error: () => {
          this.errorMessage.set('Could not unblock the sender domain.');
          this.actionLoading.set(false);
        },
      });
      return;
    }

    if (!window.confirm(`Block ${domain}? Future messages from this domain will go directly to Spam.`)) {
      return;
    }

    this.actionLoading.set(true);
    this.closeActionMenus();
    this.messageService.blockSender(currentMessage.id).subscribe({
      next: () => {
        if (!this.isRemovedFolder(currentMessage.folder)) {
          this.labelService.adjustMessageCount(currentMessage.label_ids ?? [], -1);
        }
        this.messageService.refreshFolderCounts();
        this.actionLoading.set(false);
        this.goBack();
      },
      error: () => {
        this.errorMessage.set('Could not block the sender domain.');
        this.actionLoading.set(false);
      },
    });
  }

  translateMessage(): void {
    const currentMessage = this.message();
    if (!currentMessage) {
      return;
    }

    this.closeActionMenus();
    this.translationResult.set(null);
    this.translationError.set('');
    this.translationDialogOpen.set(true);
  }

  runTranslation(): void {
    const currentMessage = this.message();
    if (!currentMessage || this.translationLoading()) {
      return;
    }

    this.translationLoading.set(true);
    this.translationError.set('');
    this.messageService.translateMessage(currentMessage.id, this.translationTarget()).subscribe({
      next: (translation) => {
        this.translationResult.set(translation);
        this.translationLoading.set(false);
      },
      error: (error) => {
        this.translationError.set(typeof error?.error?.detail === 'string' ? error.error.detail : 'The message could not be translated.');
        this.translationLoading.set(false);
      },
    });
  }

  closeTranslationDialog(): void {
    this.translationDialogOpen.set(false);
    this.translationError.set('');
  }

  printMessage(): void {
    this.closeActionMenus();
    window.setTimeout(() => window.print(), 50);
  }

  downloadMessage(): void {
    const currentMessage = this.message();
    if (!currentMessage || this.actionLoading()) {
      return;
    }
    if (!currentMessage.has_original_source) {
      this.closeActionMenus();
      this.actionNotice.set('Original source is unavailable for messages stored before source retention was enabled.');
      return;
    }

    this.actionLoading.set(true);
    this.errorMessage.set('');
    this.closeActionMenus();
    this.messageService.downloadMessage(currentMessage.id).subscribe({
      next: (blob) => {
        this.triggerBlobDownload(blob, this.messageFileName(currentMessage));
        this.actionLoading.set(false);
      },
      error: () => {
        this.errorMessage.set('Could not download the email.');
        this.actionLoading.set(false);
      },
    });
  }

  showOriginal(): void {
    const currentMessage = this.message();
    if (!currentMessage || this.sourceLoading()) {
      return;
    }
    if (!currentMessage.has_original_source) {
      this.closeActionMenus();
      this.actionNotice.set('Original source is unavailable for messages stored before source retention was enabled.');
      return;
    }

    this.closeActionMenus();
    this.sourceDialogOpen.set(true);
    this.sourceLoading.set(true);
    this.sourceCopied.set(false);
    this.messageService.getMessageSource(currentMessage.id).subscribe({
      next: (source) => {
        this.messageSource.set(source);
        this.sourceLoading.set(false);
      },
      error: (error) => {
        this.messageSource.set(typeof error?.error?.detail === 'string' ? error.error.detail : 'Message source could not be loaded.');
        this.sourceLoading.set(false);
      },
    });
  }

  closeSourceDialog(): void {
    this.sourceDialogOpen.set(false);
    this.sourceCopied.set(false);
  }

  async copySource(): Promise<void> {
    try {
      await navigator.clipboard.writeText(this.messageSource());
      this.sourceCopied.set(true);
    }
    catch {
      this.actionNotice.set('Could not copy the message source.');
    }
  }

  messageFileName(currentMessage: MessageDetailResponse): string {
    const baseName = currentMessage.subject.replace(/[^A-Za-z0-9._-]+/g, '-').replace(/^[-.]+|[-.]+$/g, '').slice(0, 80) || 'message';
    return `${baseName}.eml`;
  }

  triggerBlobDownload(blob: Blob, filename: string): void {
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => window.URL.revokeObjectURL(url), 0);
  }

  downloadAttachment(attachmentId: string, originalFilename: string): void {
    this.errorMessage.set('');

    this.messageService.downloadAttachment(attachmentId).subscribe({
      next: (blob) => {
        this.triggerBlobDownload(blob, originalFilename);
      },

      error: (error) => {
        console.error('Attachment download failed:', error);

        if (error?.status === 410) {
          this.errorMessage.set('This attachment has expired and is no longer available.');
          return;
        }

        this.errorMessage.set('Attachment could not be downloaded.');
      },
    });
  }
}
