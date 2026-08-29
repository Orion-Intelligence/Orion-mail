import { AfterViewInit, Component, ElementRef, HostListener, OnDestroy, ViewChild, computed, effect, input, output, signal, untracked } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Subscription, catchError, debounceTime, distinctUntilChanged, finalize, map, of, switchMap } from 'rxjs';

import { Icon } from '../../shared/icons/icon/icon';
import { IconName } from '../../shared/model/icon.model';
import { AddressBookService } from '../../services/address-book';
import { AddressHint } from '../../shared/model/address-book.model';
import { ComposeService } from '../../services/compose';
import { ComposeRequest } from '../../shared/model/compose.model';
import { MessageService } from '../../services/message';
import { Attachment, DraftMessageRequest } from '../../shared/model/message.model';
import { UNDO_SEND_SECONDS } from '../../shared/constants/compose.constants';
import { RecipientHintField, RichTextCommandRunner } from '../../shared/model/compose.model';

@Component({
  selector: 'app-compose',
  imports: [ReactiveFormsModule, Icon],
  host: { class: 'block' },
  templateUrl: './compose.html',
})
export class Compose implements AfterViewInit, OnDestroy {
  private readonly maxTotalFileSize = 1 * 1024 * 1024;
  private readonly maxFileSizeLabel = '1 MB';
  private readonly maxAttachmentCount = 10;
  private readonly autosave: Subscription;
  private readonly hintSubscriptions = new Subscription();
  private generation = 0;
  private lastSavedDraft = '';
  private savingDraft = false;
  private draftChangedWhileSaving = false;
  private pendingDiscard = false;
  private undoTimer?: ReturnType<typeof setTimeout>;
  private undoInterval?: ReturnType<typeof setInterval>;

  request = input<ComposeRequest | null>(null);
  inline = input(false);
  closed = output();
  sent = output<string>();
  loading = signal(false);
  errorMessage = signal('');
  selectedFiles = signal<File[]>([]);
  forwardedAttachments = signal<Attachment[]>([]);
  fileError = signal('');
  dragActive = signal(false);
  richText = signal(true);
  pendingSend = signal(false);
  undoSeconds = signal(0);
  ccError = signal('');
  receiverHints = signal<AddressHint[]>([]);
  ccHints = signal<AddressHint[]>([]);
  activeHintField = signal<RecipientHintField | null>(null);
  activeHintIndex = signal(-1);
  composeTitle = signal('New Message');
  modeIcon = signal<IconName>('edit');
  draftId = signal<string | null>(null);
  draftStatus = signal('');
  uid = computed(() => this.inline() ? 'inline' : 'window');
  inReplyToMessageId?: string;
  forwardMessageId?: string;
  form;
  @ViewChild('bodyArea') bodyArea?: ElementRef<HTMLTextAreaElement>;
  @ViewChild('richEditor') richEditor?: ElementRef<HTMLDivElement>;
  @ViewChild('receiverInput') receiverInput?: ElementRef<HTMLInputElement>;

  constructor( private readonly formBuilder: FormBuilder, private readonly messageService: MessageService, private readonly composeService: ComposeService, private readonly addressBookService: AddressBookService, ) {
    this.form = this.formBuilder.nonNullable.group({
      receiver_address: ['', [Validators.required, Validators.email]],
      cc_addresses: [''],
      bcc_addresses: [''],
      subject: ['', Validators.required],
      body: ['', Validators.required],
      body_html: [''],
    });
    this.autosave = this.form.valueChanges.pipe(debounceTime(1500)).subscribe(() => {
      this.saveDraft();
    });
    this.bindRecipientHints();
    effect(() => {
      const request = this.request();
      untracked(() => {
        this.applyRequest(request);
      });
    });
  }

  ngAfterViewInit(): void {
    this.focusComposer();
  }

  ngOnDestroy(): void {
    clearTimeout(this.undoTimer);
    clearInterval(this.undoInterval);
    this.autosave.unsubscribe();
    this.hintSubscriptions.unsubscribe();
    this.saveDraft();
  }

  private bindRecipientHints(): void {
    this.hintSubscriptions.add(this.form.controls.receiver_address.valueChanges.pipe(map((value) => value.trim().toLowerCase()),
      debounceTime(180),
      distinctUntilChanged(),
      switchMap((query) => query ? this.addressBookService.getHints(query).pipe(catchError(() => of([]))) : of([])),).subscribe((hints) => {
      this.receiverHints.set(hints);
      if (this.activeHintField() === 'to') {
        this.activeHintIndex.set(-1);
      }
    }));

    this.hintSubscriptions.add(this.form.controls.cc_addresses.valueChanges.pipe(map((value) => this.currentCcQuery(value)),
      debounceTime(180),
      distinctUntilChanged(),
      switchMap((query) => query ? this.addressBookService.getHints(query).pipe(catchError(() => of([]))) : of([])),).subscribe((hints) => {
      const existing = new Set(this.form.controls.cc_addresses.value.split(/[;,]/).slice(0, -1).map((address) => address.trim().toLowerCase()).filter(Boolean));
      this.ccHints.set(hints.filter((hint) => !existing.has(hint.email_address)));
      if (this.activeHintField() === 'cc') {
        this.activeHintIndex.set(-1);
      }
    }));
  }

  private currentCcQuery(value: string): string {
    const separatorIndex = Math.max(value.lastIndexOf(','), value.lastIndexOf(';'));
    return value.slice(separatorIndex + 1).trim().toLowerCase();
  }

  private hintsFor(field: RecipientHintField): AddressHint[] {
    return field === 'to' ? this.receiverHints() : this.ccHints();
  }

  openHints(field: RecipientHintField): void {
    this.activeHintField.set(field);
    this.activeHintIndex.set(-1);
  }

  closeHintsSoon(): void {
    setTimeout(() => {
      this.activeHintField.set(null);
    }, 120);
  }

  selectHint(field: RecipientHintField, emailAddress: string): void {
    if (field === 'to') {
      this.form.controls.receiver_address.setValue(emailAddress);
      this.receiverInput?.nativeElement.focus();
    }
    else {
      const value = this.form.controls.cc_addresses.value;
      const separatorIndex = Math.max(value.lastIndexOf(','), value.lastIndexOf(';'));
      const prefix = separatorIndex >= 0 ? `${value.slice(0, separatorIndex + 1).trimEnd()} ` : '';
      this.form.controls.cc_addresses.setValue(`${prefix}${emailAddress}`);
    }
    this.activeHintField.set(null);
    this.activeHintIndex.set(-1);
  }

  hintOptionId(field: RecipientHintField, index: number): string {
    return `${this.uid()}-${field}-recipient-hint-${index}`;
  }

  activeHintOptionId(field: RecipientHintField): string | null {
    const index = this.activeHintIndex();
    return this.activeHintField() === field && index >= 0 ? this.hintOptionId(field, index) : null;
  }

  activateHint(field: RecipientHintField, index: number): void {
    this.activeHintField.set(field);
    this.activeHintIndex.set(index);
  }

  private scrollHintIntoView(field: RecipientHintField, index: number): void {
    requestAnimationFrame(() => document.getElementById(this.hintOptionId(field, index))?.scrollIntoView({ block: 'nearest' }));
  }

  handleHintKeydown(event: KeyboardEvent, field: RecipientHintField): void {
    const hints = this.hintsFor(field);
    if (event.key === 'Escape' && this.activeHintField() === field) {
      event.preventDefault();
      event.stopPropagation();
      this.activeHintField.set(null);
      this.activeHintIndex.set(-1);
      return;
    }
    if (this.activeHintField() !== field || hints.length === 0) {
      return;
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      const index = this.activeHintIndex();
      const nextIndex = index < 0 ? (event.key === 'ArrowDown' ? 0 : hints.length - 1) : (index + (event.key === 'ArrowDown' ? 1 : -1) + hints.length) % hints.length;
      this.activeHintIndex.set(nextIndex);
      this.scrollHintIntoView(field, nextIndex);
      return;
    }
    if (event.key === 'Enter') {
      const index = this.activeHintIndex();
      const hint = index >= 0 ? hints.at(index) : undefined;
      if (hint) {
        event.preventDefault();
        this.selectHint(field, hint.email_address);
      }
    }
  }

  @HostListener('document:keydown.escape')
  closeOnEscape(): void {
    if (!this.inline()) {
      this.close();
    }
  }

  close(): void {
    if (this.draftId() && !this.hasContent()) {
      this.discardDraft();
      return;
    }
    this.dismiss();
  }

  saveDraft(): void {
    if (this.loading() || !this.hasContent()) {
      return;
    }

    const snapshot = this.snapshot();
    if (snapshot === this.lastSavedDraft) {
      return;
    }

    if (this.savingDraft) {
      this.draftChangedWhileSaving = true;
      return;
    }

    const generation = this.generation;
    this.savingDraft = true;
    this.draftChangedWhileSaving = false;
    this.draftStatus.set('Saving…');
    this.messageService.saveDraft(this.draftPayload(), this.draftId() ?? undefined).subscribe({
      next: (draft) => {
        this.savingDraft = false;
        if (generation !== this.generation) {
          this.messageService.refreshFolderCounts();
          return;
        }
        if (this.pendingDiscard) {
          this.pendingDiscard = false;
          this.messageService.permanentlyDeleteMessage(draft.id).subscribe({ next: () => {
            this.messageService.refreshFolderCounts();
          }, error: () => undefined });
          return;
        }
        this.draftId.set(draft.id);
        this.lastSavedDraft = snapshot;
        this.draftStatus.set('Draft saved');
        this.messageService.refreshFolderCounts();
        if (this.draftChangedWhileSaving) {
          this.saveDraft();
        }
      },
      error: () => {
        this.savingDraft = false;
        if (generation === this.generation) {
          this.draftStatus.set('Draft not saved');
        }
      },
    });
  }

  discardDraft(): void {
    const draftId = this.draftId();
    this.resetComposer();
    if (this.savingDraft) {
      this.pendingDiscard = true;
    }
    else if (draftId) {
      this.messageService.permanentlyDeleteMessage(draftId).subscribe({ next: () => {
        this.messageService.refreshFolderCounts();
      }, error: () => undefined });
    }
    this.dismiss();
  }

  toggleRichText(): void {
    const enabled = !this.richText();
    this.richText.set(enabled);
    if (enabled) {
      setTimeout(() => {
        this.syncEditorFromForm();
      }, 0);
      return;
    }
    this.form.controls.body_html.setValue('');
  }

  private runRichTextCommand(command: string, value?: string): void {
    const runner = (document as unknown as { execCommand: RichTextCommandRunner }).execCommand;
    runner.call(document, command, false, value);
    this.onRichInput();
  }

  applyFormat(command: string): void {
    this.runRichTextCommand(command);
  }

  insertLink(): void {
    const url = window.prompt('Link address');
    if (!url) {
      return;
    }
    this.runRichTextCommand('createLink', url);
  }

  onRichInput(): void {
    const editor = this.richEditor?.nativeElement;
    if (!editor) {
      return;
    }
    this.form.controls.body.setValue(editor.innerText);
    this.form.controls.body_html.setValue(/*safe*/ editor.innerHTML);
  }

  private syncEditorFromForm(): void {
    const editor = this.richEditor?.nativeElement;
    if (!editor) {
      return;
    }
    const html = this.form.controls.body_html.value || this.plainTextToHtml(this.form.controls.body.value);
    const parsed = new DOMParser().parseFromString(/*safe*/ html, 'text/html');
    editor.replaceChildren(...Array.from(parsed.body.childNodes));
  }

  private plainTextToHtml(text: string): string {
    const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return escaped.replace(/\n/g, /*safe*/ '<br>');
  }

  onFilesDropped(event: DragEvent): void {
    event.preventDefault();
    this.dragActive.set(false);
    const dropped = Array.from(event.dataTransfer?.files ?? []);
    if (dropped.length > 0) {
      this.addFiles(dropped);
    }
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.dragActive.set(true);
  }

  onDragLeave(): void {
    this.dragActive.set(false);
  }

  private addFiles(newFiles: File[]): void {
    const previousFiles = this.selectedFiles();
    const oversizedFile = newFiles.find((file) => file.size > this.maxTotalFileSize);
    if (oversizedFile) {
      this.fileError.set(`${oversizedFile.name} is larger than the ${this.maxFileSizeLabel} attachment limit.`);
      return;
    }

    const combinedFiles = [...previousFiles, ...newFiles];
    if (combinedFiles.length + this.forwardedAttachments().length > this.maxAttachmentCount) {
      this.fileError.set(`A message cannot have more than ${this.maxAttachmentCount} attachments.`);
      return;
    }

    this.selectedFiles.set(combinedFiles);
    if (!this.validateAttachmentLimits()) {
      this.selectedFiles.set(previousFiles);
    }
  }

  onFilesSelected(event: Event): void {
    const /*safe*/ input = event.target as HTMLInputElement;

    if (!input.files) {
      return;
    }

    const newFiles = Array.from(input.files);
    const previousFiles = this.selectedFiles();
    const oversizedFile = newFiles.find((file) => file.size > this.maxTotalFileSize);

    if (oversizedFile) {
      this.fileError.set(`${oversizedFile.name} is larger than the ${this.maxFileSizeLabel} attachment limit.`);
      input.value = '';
      return;
    }

    const combinedFiles = [...previousFiles, ...newFiles];

    if (combinedFiles.length + this.forwardedAttachments().length > this.maxAttachmentCount) {
      this.fileError.set(`A message cannot have more than ${this.maxAttachmentCount} attachments.`);
      input.value = '';
      return;
    }

    this.selectedFiles.set(combinedFiles);
    if (!this.validateAttachmentLimits()) {
      this.selectedFiles.set(previousFiles);
    }

    input.value = '';
  }

  removeFile(index: number): void {
    this.selectedFiles.update((files) => files.filter((_, i) => i !== index));

    this.fileError.set('');
    this.validateAttachmentLimits();
  }

  removeForwardedAttachment(attachmentId: string): void {
    this.forwardedAttachments.update((attachments) => attachments.filter((attachment) => attachment.id !== attachmentId));
    this.fileError.set('');
    this.validateAttachmentLimits();
  }

  getTotalFileSize(): string {
    const totalBytes = this.totalAttachmentBytes();

    return (totalBytes / (1024 * 1024)).toFixed(2);
  }

  private applyRequest(request: ComposeRequest | null): void {
    if (!request) {
      return;
    }

    this.saveDraft();
    this.generation += 1;
    this.resetComposer();
    this.errorMessage.set('');
    if (request.mode === 'draft') {
      this.loadDraft(request.draftId ?? '');
      return;
    }

    this.inReplyToMessageId = request.inReplyToMessageId;
    this.forwardMessageId = request.forwardMessageId;
    this.forwardedAttachments.set((request.forwardedAttachments ?? []).filter((attachment) => attachment.status === 'available'));
    this.composeTitle.set(request.mode === 'reply-all' ? 'Reply All' : request.mode === 'reply' ? 'Reply' : request.mode === 'forward' ? 'Forward' : 'New Message');
    this.modeIcon.set(request.mode === 'reply-all' ? 'replyAll' : request.mode === 'reply' ? 'reply' : request.mode === 'forward' ? 'forward' : 'edit');
    this.form.patchValue({ receiver_address: request.to ?? '', cc_addresses: request.cc?.join(', ') ?? '', bcc_addresses: '', subject: request.subject ?? '', body: request.body ?? '' });
    this.form.controls.body_html.setValue('');
    this.applySignature(request.body ?? '');
    setTimeout(() => {
      this.syncEditorFromForm();
    }, 0);
    this.validateAttachmentLimits();
    this.focusComposer();
  }

  private applySignature(existingBody: string): void {
    const generation = this.generation;
    this.messageService.getMyMailbox().subscribe({
      next: (mailbox) => {
        const signature = (mailbox.signature ?? '').trim();
        if (!signature || generation !== this.generation || this.form.controls.body.value !== existingBody) {
          return;
        }
        this.form.controls.body.setValue(`${existingBody}\n\n--\n${signature}`);
        this.lastSavedDraft = this.snapshot();
      },
      error: () => undefined,
    });
  }

  private loadDraft(draftId: string): void {
    const generation = this.generation;
    this.messageService.getMessageById(draftId).subscribe({
      next: (draft) => {
        if (generation !== this.generation) {
          return;
        }
        if (draft.folder !== 'drafts') {
          this.errorMessage.set('This message is no longer a draft.');
          return;
        }
        this.form.patchValue({ receiver_address: draft.receiver_address, cc_addresses: draft.cc_addresses.join(', '), bcc_addresses: (draft.bcc_addresses ?? []).join(', '), subject: draft.subject, body: draft.body });
        this.draftId.set(draft.id);
        this.lastSavedDraft = this.snapshot();
        this.form.controls.body_html.setValue(/*safe*/ draft.body_html ?? '');
        setTimeout(() => {
          this.syncEditorFromForm();
        }, 0);
        this.composeTitle.set(draft.subject || 'Draft');
        this.draftStatus.set('Draft saved');
        this.focusBody();
      },
      error: () => {
        this.errorMessage.set('Could not load the draft.');
      },
    });
  }

  private focusBody(): void {
    setTimeout(() => {
      const area = this.bodyArea?.nativeElement;
      if (!area) {
        return;
      }
      area.focus();
      area.setSelectionRange(0, 0);
      area.scrollIntoView({ block: 'nearest' });
    }, 0);
  }

  private focusComposer(): void {
    const mode = this.request()?.mode;
    if (this.inline() || (mode && mode !== 'new')) {
      this.focusBody();
      return;
    }

    setTimeout(() => this.receiverInput?.nativeElement.focus(), 0);
  }

  private dismiss(): void {
    if (this.inline()) {
      this.closed.emit();
      return;
    }
    this.composeService.close();
  }

  private snapshot(): string {
    const value = this.form.getRawValue();
    return JSON.stringify([value.receiver_address.trim(), value.cc_addresses.trim(), value.bcc_addresses.trim(), value.subject.trim(), value.body]);
  }

  private hasContent(): boolean {
    const value = this.form.getRawValue();
    return Boolean(value.receiver_address.trim() || value.cc_addresses.trim() || value.bcc_addresses.trim() || value.subject.trim() || value.body.trim());
  }

  private draftPayload(): DraftMessageRequest {
    const value = this.form.getRawValue();
    return { receiver_address: value.receiver_address.trim(), cc_addresses: value.cc_addresses.split(/[;,]/).map((address) => address.trim()).filter(Boolean), bcc_addresses: value.bcc_addresses.split(/[;,]/).map((address) => address.trim()).filter(Boolean), subject: value.subject.trim(), body: value.body, body_html: this.richText() ? value.body_html : '' };
  }

  private resetComposer(): void {
    this.form.reset();
    this.selectedFiles.set([]);
    this.forwardedAttachments.set([]);
    this.inReplyToMessageId = undefined;
    this.forwardMessageId = undefined;
    this.fileError.set('');
    this.ccError.set('');
    this.receiverHints.set([]);
    this.ccHints.set([]);
    this.activeHintField.set(null);
    this.activeHintIndex.set(0);
    this.draftId.set(null);
    this.lastSavedDraft = '';
    this.draftStatus.set('');
  }

  private totalAttachmentBytes(): number {
    return this.selectedFiles().reduce((total, file) => total + file.size, 0)
      + this.forwardedAttachments().reduce((total, attachment) => total + attachment.size, 0);
  }

  private validateAttachmentLimits(): boolean {
    const count = this.selectedFiles().length + this.forwardedAttachments().length;
    if (count > this.maxAttachmentCount) {
      this.fileError.set(`A message cannot have more than ${this.maxAttachmentCount} attachments.`);
      return false;
    }
    if (this.totalAttachmentBytes() > this.maxTotalFileSize) {
      this.fileError.set(`Total attachment size cannot exceed ${this.maxFileSizeLabel}.`);
      return false;
    }
    this.fileError.set('');
    return true;
  }

  private parseCcAddresses(value: string): string[] | null {
    const addresses = [...new Set(value.split(/[;,]/).map((address) => address.trim().toLowerCase()).filter(Boolean))];
    if (addresses.some((address) => !/^[^\s@]+@[^\s@]+$/.test(address))) {
      return null;
    }
    return addresses;
  }

  submit(): void {
    const ccAddresses = this.parseCcAddresses(this.form.controls.cc_addresses.value);
    const bccAddresses = this.parseCcAddresses(this.form.controls.bcc_addresses.value);
    this.ccError.set(ccAddresses === null ? 'Enter valid Cc addresses separated by commas.' : bccAddresses === null ? 'Enter valid Bcc addresses separated by commas.' : '');
    if (this.form.invalid || ccAddresses === null || bccAddresses === null || !this.validateAttachmentLimits() || this.loading() || this.pendingSend()) {
      this.form.markAllAsTouched();
      return;
    }

    this.pendingSend.set(true);
    this.undoSeconds.set(UNDO_SEND_SECONDS);
    this.undoInterval = setInterval(() => {
      this.undoSeconds.update((seconds) => Math.max(0, seconds - 1));
    }, 1000);
    this.undoTimer = setTimeout(() => {
      this.performSend();
    }, UNDO_SEND_SECONDS * 1000);
  }

  cancelSend(): void {
    clearTimeout(this.undoTimer);
    clearInterval(this.undoInterval);
    this.undoTimer = undefined;
    this.undoInterval = undefined;
    this.pendingSend.set(false);
    this.undoSeconds.set(0);
  }

  private performSend(): void {
    clearInterval(this.undoInterval);
    this.undoTimer = undefined;
    this.undoInterval = undefined;
    this.pendingSend.set(false);
    this.undoSeconds.set(0);

    const ccAddresses = this.parseCcAddresses(this.form.controls.cc_addresses.value) ?? [];
    const bccAddresses = this.parseCcAddresses(this.form.controls.bcc_addresses.value) ?? [];
    this.loading.set(true);
    this.errorMessage.set('');

    const formValue = this.form.getRawValue();

    const messageData = {
      receiver_address: formValue.receiver_address,
      cc_addresses: ccAddresses,
      bcc_addresses: bccAddresses,
      subject: formValue.subject,
      body: formValue.body,
      body_html: this.richText() ? formValue.body_html : /*safe*/ undefined,
      files: this.selectedFiles(),
      in_reply_to_message_id: this.inReplyToMessageId,
      forward_message_id: this.forwardMessageId,
      forward_attachment_ids: this.forwardedAttachments().map((attachment) => attachment.id),
      draft_id: this.draftId() ?? undefined,
    };

    this.messageService
      .sendMessage(messageData)
      .pipe(finalize(() => {
        this.loading.set(false);
      }),)
      .subscribe({
        next: (response) => {
          this.resetComposer();
          if (this.savingDraft) {
            this.pendingDiscard = true;
          }
          this.messageService.refreshFolderCounts();
          this.sent.emit(response.message);
          if (!this.inline()) {
            this.composeService.showNotice(response.message);
            this.composeService.close();
          }
        },

        error: (error) => {
          const detail = error?.error?.detail;

          if (Array.isArray(detail)) {
            this.errorMessage.set(detail[0]?.msg || 'Email could not be sent.');
            return;
          }

          if (typeof detail === 'string') {
            this.errorMessage.set(detail);
            return;
          }

          this.errorMessage.set('Email could not be sent. Please try again.');
        },
      });
  }
}
