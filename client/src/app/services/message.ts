import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';

import { environment } from '../../environments/environment';
import { EMPTY_FOLDER_COUNTS } from '../shared/constants/message.constants';
import { BulkMessageAction, BulkMessageOptions, BulkMessageResponse, DeleteMessageResponse, DraftMessageRequest, FolderCounts, InboxMessage, Mailbox, MessageDetailResponse, MessageFolder, MessageTranslationResponse, ReportType, SendMessageRequest, SendMessageResponse, SenderReportResponse, SentMessage } from '../shared/model/message.model';

@Injectable({
  providedIn: 'root',
})
export class MessageService {
  private readonly apiBaseUrl = environment.apiBaseUrl;
  private readonly baseUrl = `${this.apiBaseUrl}/messages`;

  readonly folderCounts = signal<FolderCounts>({ ...EMPTY_FOLDER_COUNTS, unread: { ...EMPTY_FOLDER_COUNTS } });

  constructor(private readonly http: HttpClient) {}

  sendMessage(data: SendMessageRequest): Observable<SendMessageResponse> {
    const formData = new FormData();
    formData.append('receiver_address', data.receiver_address);
    formData.append('subject', data.subject);
    formData.append('body', data.body);

    if (data.body_html) {
      formData.append('body_html', data.body_html);
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

    return this.http.post<SendMessageResponse>(`${this.baseUrl}/send`, formData);
  }

  saveDraft(draft: DraftMessageRequest, draftId?: string): Observable<MessageDetailResponse> {
    return draftId ? this.http.put<MessageDetailResponse>(`${this.baseUrl}/drafts/${draftId}`, draft) : this.http.post<MessageDetailResponse>(`${this.baseUrl}/drafts`, draft);
  }

  getDraftMessages(): Observable<MessageDetailResponse[]> {
    return this.http.get<MessageDetailResponse[]>(`${this.baseUrl}/drafts`);
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
    return this.http.get<MessageDetailResponse[]>(`${this.baseUrl}/spam`);
  }

  getStarredMessages(): Observable<MessageDetailResponse[]> {
    return this.http.get<MessageDetailResponse[]>(`${this.baseUrl}/starred`);
  }

  getImportantMessages(): Observable<MessageDetailResponse[]> {
    return this.http.get<MessageDetailResponse[]>(`${this.baseUrl}/important`);
  }

  getAllMessages(): Observable<MessageDetailResponse[]> {
    return this.http.get<MessageDetailResponse[]>(`${this.baseUrl}/all`);
  }

  searchMessages(query: string, scope = 'all', labelId?: string, limit?: number): Observable<MessageDetailResponse[]> {
    let params = new HttpParams().set('query', query).set('scope', scope);
    if (labelId) {
      params = params.set('label_id', labelId);
    }
    if (limit !== undefined) {
      params = params.set('limit', limit);
    }
    return this.http.get<MessageDetailResponse[]>(`${this.baseUrl}/search`, { params });
  }

  getSentMessages(): Observable<SentMessage[]> {
    return this.http.get<SentMessage[]>(`${this.baseUrl}/sent`);
  }

  getArchivedMessages(): Observable<MessageDetailResponse[]> {
    return this.http.get<MessageDetailResponse[]>(`${this.baseUrl}/archive`);
  }

  getTrashMessages(): Observable<MessageDetailResponse[]> {
    return this.http.get<MessageDetailResponse[]>(`${this.baseUrl}/trash`);
  }

  loadFolderCounts(): Observable<FolderCounts> {
    return this.http.get<FolderCounts>(`${this.baseUrl}/folder-counts`).pipe(tap((counts) => this.folderCounts.set(counts)));
  }

  refreshFolderCounts(): void {
    this.loadFolderCounts().subscribe({ error: () => undefined });
  }

  archiveMessage(messageId: string): Observable<MessageDetailResponse> {
    return this.http.put<MessageDetailResponse>(`${this.baseUrl}/${messageId}/archive`, {});
  }

  moveToTrash(messageId: string): Observable<MessageDetailResponse> {
    return this.http.put<MessageDetailResponse>(`${this.baseUrl}/${messageId}/trash`, {});
  }

  restoreMessage(messageId: string): Observable<MessageDetailResponse> {
    return this.http.put<MessageDetailResponse>(`${this.baseUrl}/${messageId}/restore`, {});
  }

  moveMessage(messageId: string, destination: MessageFolder): Observable<MessageDetailResponse> {
    return this.http.put<MessageDetailResponse>(`${this.baseUrl}/${messageId}/move`, { destination });
  }

  markMessageUnread(messageId: string): Observable<MessageDetailResponse> {
    return this.http.put<MessageDetailResponse>(`${this.baseUrl}/${messageId}/unread`, {});
  }

  bulkUpdateMessages(messageIds: string[], action: BulkMessageAction, options: BulkMessageOptions = {}): Observable<BulkMessageResponse> {
    return this.http.put<BulkMessageResponse>(`${this.baseUrl}/bulk`, {
      message_ids: messageIds,
      action,
      ...options,
    });
  }

  reportSender(messageId: string, reportType: ReportType): Observable<SenderReportResponse> {
    return this.http.put<SenderReportResponse>(`${this.baseUrl}/${messageId}/report`, { report_type: reportType });
  }

  blockSender(messageId: string): Observable<MessageDetailResponse> {
    return this.http.put<MessageDetailResponse>(`${this.baseUrl}/${messageId}/block-sender`, {});
  }

  unblockSender(messageId: string): Observable<MessageDetailResponse> {
    return this.http.delete<MessageDetailResponse>(`${this.baseUrl}/${messageId}/block-sender`);
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
    return this.http.get<InboxMessage[]>(`${this.baseUrl}/inbox`, { params });
  }

  getThreadMessages(messageId: string): Observable<MessageDetailResponse[]> {
    return this.http.get<MessageDetailResponse[]>(`${this.baseUrl}/${messageId}/thread`);
  }

  getMessageById(messageId: string): Observable<MessageDetailResponse> {
    return this.http.get<MessageDetailResponse>(`${this.baseUrl}/${messageId}`);
  }

  setMessageLabels(messageId: string, labelIds: string[]): Observable<MessageDetailResponse> {
    return this.http.put<MessageDetailResponse>(`${this.baseUrl}/${messageId}/labels`, {
      label_ids: labelIds,
    });
  }

  downloadAttachment(attachmentId: string): Observable<Blob> {
    return this.http.get(`${this.apiBaseUrl}/attachments/${attachmentId}/download`, {
      responseType: 'blob',
    });
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
}
