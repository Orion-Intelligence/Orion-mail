import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, effect, inject, signal } from '@angular/core';
import { Observable, from, map, of, switchMap, tap } from 'rxjs';

import { environment } from '../../environments/environment';
import { EMPTY_FOLDER_COUNTS } from '../shared/constants/message.constants';
import { E2eService } from './e2e';
import { BulkMessageAction, BulkMessageOptions, BulkMessageResponse, DeleteMessageResponse, DraftMessageRequest, FolderCounts, InboxMessage, Mailbox, MessageDetailResponse, MessageFolder, MessageTranslationResponse, ReportType, SavedPgpKey, SendMessageRequest, SendMessageResponse, SenderIdentity, SenderIdentityResponse, SenderReportResponse, SentMessage } from '../shared/model/message.model';

@Injectable({
  providedIn: 'root',
})
export class MessageService {
  private readonly apiBaseUrl = environment.apiBaseUrl;
  private readonly baseUrl = `${this.apiBaseUrl}/messages`;
  private readonly e2e = inject(E2eService);

  readonly folderCounts = signal<FolderCounts>({ ...EMPTY_FOLDER_COUNTS, unread: { ...EMPTY_FOLDER_COUNTS } });
  readonly storageExceeded = signal(false);
  readonly mailboxRevision = signal(0);

  constructor(private readonly http: HttpClient) {
    effect(() => {
      if (this.e2e.revision() > 0) {
        this.notifyMailboxChanged();
      }
    });
  }

  sendMessage(request: SendMessageRequest): Observable<SendMessageResponse> {
    return from(this.e2e.sealOutgoing(request)).pipe(switchMap((data) => this.postMessage(data)), this.e2e.open());
  }

  private postMessage(data: SendMessageRequest): Observable<SendMessageResponse> {
    const formData = new FormData();
    formData.append('receiver_address', data.receiver_address);
    formData.append('subject', data.subject);
    formData.append('body', data.body);

    if (data.body_html) {
      formData.append('body_html', /*safe*/ data.body_html);
    }

    for (const ccAddress of data.cc_addresses) {
      formData.append('cc_addresses', ccAddress);
    }

    for (const bccAddress of data.bcc_addresses ?? []) {
      formData.append('bcc_addresses', bccAddress);
    }

    if (data.in_reply_to_message_id) {
      formData.append('in_reply_to_message_id', data.in_reply_to_message_id);
    }

    if (data.forward_message_id) {
      formData.append('forward_message_id', data.forward_message_id);
    }

    for (const attachmentId of data.forward_attachment_ids) {
      formData.append('forward_attachment_ids', attachmentId);
    }

    for (const file of data.files) {
      formData.append('files', file, file.name);
    }

    if (data.draft_id) {
      formData.append('draft_id', data.draft_id);
    }

    formData.append('sender_identity_type', data.sender_identity_type);

    if (data.disposable_mailbox_id) {
      formData.append('disposable_mailbox_id', data.disposable_mailbox_id);
    }

    return this.http.post<SendMessageResponse>(`${this.baseUrl}/send`, formData);
  }

  saveDraft(draft: DraftMessageRequest, draftId?: string): Observable<MessageDetailResponse> {
    return from(this.e2e.sealDraft(draft)).pipe(switchMap((sealed) => draftId ? this.http.put<MessageDetailResponse>(`${this.baseUrl}/drafts/${draftId}`, sealed) : this.http.post<MessageDetailResponse>(`${this.baseUrl}/drafts`, sealed)), this.e2e.open());
  }

  getDraftMessages(): Observable<MessageDetailResponse[]> {
    return this.http.get<MessageDetailResponse[]>(`${this.baseUrl}/drafts`).pipe(this.e2e.open());
  }

  updateMailboxSettings(signature: string): Observable<{ mailbox_address: string; signature: string }> {
    return this.http.put<{ mailbox_address: string; signature: string }>(`${this.apiBaseUrl}/mailboxes/me/settings`, { signature });
  }

  emptyFolder(folder: string): Observable<{ folder: string; deleted: number }> {
    return this.http.delete<{ folder: string; deleted: number }>(`${this.baseUrl}/folder/${folder}`);
  }

  markFolderRead(folder: string): Observable<{ folder: string; updated: number }> {
    return this.http.put<{ folder: string; updated: number }>(`${this.baseUrl}/folder/${folder}/read`, {});
  }

  getSpamMessages(): Observable<MessageDetailResponse[]> {
    return this.http.get<MessageDetailResponse[]>(`${this.baseUrl}/spam`).pipe(this.e2e.open());
  }

  getStarredMessages(): Observable<MessageDetailResponse[]> {
    return this.http.get<MessageDetailResponse[]>(`${this.baseUrl}/starred`).pipe(this.e2e.open());
  }

  getImportantMessages(): Observable<MessageDetailResponse[]> {
    return this.http.get<MessageDetailResponse[]>(`${this.baseUrl}/important`).pipe(this.e2e.open());
  }

  getAllMessages(): Observable<MessageDetailResponse[]> {
    return this.http.get<MessageDetailResponse[]>(`${this.baseUrl}/all`).pipe(this.e2e.open());
  }

  searchMessages(query: string, scope = 'all', labelId?: string, limit?: number): Observable<MessageDetailResponse[]> {
    let params = new HttpParams().set('query', query).set('scope', scope);
    if (labelId) {
      params = params.set('label_id', labelId);
    }
    if (limit !== undefined) {
      params = params.set('limit', limit);
    }
    return this.http.get<MessageDetailResponse[]>(`${this.baseUrl}/search`, { params }).pipe(this.e2e.open());
  }

  getSentMessages(): Observable<SentMessage[]> {
    return this.http.get<SentMessage[]>(`${this.baseUrl}/sent`).pipe(this.e2e.open());
  }

  getArchivedMessages(): Observable<MessageDetailResponse[]> {
    return this.http.get<MessageDetailResponse[]>(`${this.baseUrl}/archive`).pipe(this.e2e.open());
  }

  getTrashMessages(): Observable<MessageDetailResponse[]> {
    return this.http.get<MessageDetailResponse[]>(`${this.baseUrl}/trash`).pipe(this.e2e.open());
  }

  loadFolderCounts(): Observable<FolderCounts> {
    return this.http.get<FolderCounts>(`${this.baseUrl}/folder-counts`).pipe(tap((counts) => {
      this.folderCounts.set(counts);
    }));
  }

  refreshFolderCounts(): void {
    this.loadFolderCounts().subscribe({ error: () => undefined });
  }

  notifyMailboxChanged(): void {
    this.mailboxRevision.update((revision) => revision + 1);
  }

  refreshStorageStatus(): void {
    this.http.get<{ storage_exceeded: boolean }>(`${this.baseUrl}/storage-status`).subscribe({
      next: (storage) => {
        this.storageExceeded.set(storage.storage_exceeded);
      },
      error: () => {
        this.storageExceeded.set(false);
      },
    });
  }

  archiveMessage(messageId: string): Observable<MessageDetailResponse> {
    return this.http.put<MessageDetailResponse>(`${this.baseUrl}/${messageId}/archive`, {}).pipe(this.e2e.open());
  }

  moveToTrash(messageId: string): Observable<MessageDetailResponse> {
    return this.http.put<MessageDetailResponse>(`${this.baseUrl}/${messageId}/trash`, {}).pipe(this.e2e.open());
  }

  restoreMessage(messageId: string): Observable<MessageDetailResponse> {
    return this.http.put<MessageDetailResponse>(`${this.baseUrl}/${messageId}/restore`, {}).pipe(this.e2e.open());
  }

  moveMessage(messageId: string, destination: MessageFolder): Observable<MessageDetailResponse> {
    return this.http.put<MessageDetailResponse>(`${this.baseUrl}/${messageId}/move`, { destination }).pipe(this.e2e.open());
  }

  markMessageUnread(messageId: string): Observable<MessageDetailResponse> {
    return this.http.put<MessageDetailResponse>(`${this.baseUrl}/${messageId}/unread`, {}).pipe(this.e2e.open());
  }

  bulkUpdateMessages(messageIds: string[], action: BulkMessageAction, options: BulkMessageOptions = {}): Observable<BulkMessageResponse> {
    return this.http.put<BulkMessageResponse>(`${this.baseUrl}/bulk`, {
      message_ids: messageIds,
      action,
      ...options,
    }).pipe(switchMap((response) => of(response.messages).pipe(this.e2e.open(), map((messages) => ({ ...response, messages })))));
  }

  reportSender(messageId: string, reportType: ReportType): Observable<SenderReportResponse> {
    return this.http.put<SenderReportResponse>(`${this.baseUrl}/${messageId}/report`, { report_type: reportType }).pipe(this.e2e.open());
  }

  blockSender(messageId: string): Observable<MessageDetailResponse> {
    return this.http.put<MessageDetailResponse>(`${this.baseUrl}/${messageId}/block-sender`, {}).pipe(this.e2e.open());
  }

  unblockSender(messageId: string): Observable<MessageDetailResponse> {
    return this.http.delete<MessageDetailResponse>(`${this.baseUrl}/${messageId}/block-sender`).pipe(this.e2e.open());
  }

  permanentlyDeleteMessage(messageId: string): Observable<DeleteMessageResponse> {
    return this.http.delete<DeleteMessageResponse>(`${this.baseUrl}/${messageId}/permanent`);
  }

  getMyMailbox(): Observable<Mailbox> {
    return this.http.get<Mailbox>(`${this.apiBaseUrl}/mailboxes/me`);
  }

  configureMailbox(): Observable<Mailbox> {
    return this.http.post<Mailbox>(`${this.apiBaseUrl}/mailboxes`, {});
  }

  getInboxMessages(limit?: number, offset?: number, oldestFirst = false): Observable<InboxMessage[]> {
    let params = new HttpParams();
    if (limit !== undefined) {
      params = params.set('limit', limit);
    }
    if (offset !== undefined) {
      params = params.set('offset', offset);
    }
    if (oldestFirst) {
      params = params.set('oldest_first', true);
    }
    return this.http.get<InboxMessage[]>(`${this.baseUrl}/inbox`, { params }).pipe(this.e2e.open());
  }

  getThreadMessages(messageId: string): Observable<MessageDetailResponse[]> {
    return this.http.get<MessageDetailResponse[]>(`${this.baseUrl}/${messageId}/thread`).pipe(this.e2e.open());
  }

  getMessageById(messageId: string): Observable<MessageDetailResponse> {
    return this.http.get<MessageDetailResponse>(`${this.baseUrl}/${messageId}`).pipe(this.e2e.open());
  }

  setMessageLabels(messageId: string, labelIds: string[]): Observable<MessageDetailResponse> {
    return this.http.put<MessageDetailResponse>(`${this.baseUrl}/${messageId}/labels`, {
      label_ids: labelIds,
    }).pipe(this.e2e.open());
  }

  downloadAttachment(attachmentId: string): Observable<Blob> {
    return this.http.get(`${this.apiBaseUrl}/attachments/${attachmentId}/download`, {
      responseType: 'blob',
    }).pipe(switchMap((blob) => from(this.e2e.openAttachment(attachmentId, blob))));
  }

  downloadMessage(messageId: string): Observable<Blob> {
    return this.http.get(`${this.baseUrl}/${messageId}/download`, { responseType: 'blob' });
  }

  getMessageSource(messageId: string): Observable<string> {
    return this.http.get(`${this.baseUrl}/${messageId}/source`, { responseType: 'text' });
  }

  translateMessage(messageId: string, targetLanguage: string): Observable<MessageTranslationResponse> {
    return this.http.post<MessageTranslationResponse>(`${this.baseUrl}/${messageId}/translate`, { target_language: targetLanguage });
  }

  getSenderIdentities(): Observable<SenderIdentityResponse> {
    return this.http.get<SenderIdentityResponse>(`${this.apiBaseUrl}/sender-identities`);
  }

  generateDisposableMailbox(identitySignature: string, pgpKeyId?: string): Observable<SenderIdentity> {
    return this.http.post<SenderIdentity>(`${this.apiBaseUrl}/sender-identities/disposable`, {
      identity_signature: identitySignature,
      pgp_key_id: pgpKeyId ?? null,
    });
  }

  deleteDisposableMailbox(disposableId: string, keepPgp: boolean): Observable<{ message: string }> {
    return this.http.request<{ message: string }>('delete', `${this.apiBaseUrl}/sender-identities/disposable/${disposableId}`, {
      body: { keep_pgp: keepPgp },
    });
  }

  getSavedPgpKeys(): Observable<SavedPgpKey[]> {
    return this.http.get<SavedPgpKey[]>(`${this.apiBaseUrl}/sender-identities/saved-pgp`);
  }

  deleteSavedPgpKey(pgpKeyId: string): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.apiBaseUrl}/sender-identities/saved-pgp/${pgpKeyId}`);
  }
}
