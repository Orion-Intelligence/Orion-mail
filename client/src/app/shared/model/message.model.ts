export interface SendMessageRequest {
  receiver_address: string;
  cc_addresses: string[];
  bcc_addresses?: string[];
  body_html?: string;
  subject: string;
  body: string;
  files: File[];
  in_reply_to_message_id?: string;
  forward_message_id?: string;
  forward_attachment_ids: string[];
  draft_id?: string;
}

export interface Mailbox {
  id: string;
  mailbox_address: string;
  is_active: boolean;
  signature?: string;
}

export interface InboxMessage {
  id: string;
  sender_address: string;
  receiver_address: string;
  to_addresses: string[];
  cc_addresses: string[];
  reply_to_address?: string | null;
  subject: string;
  body: string;
  attachments: Attachment[];
  label_ids: string[];
  is_read: boolean;
  is_starred: boolean;
  is_important: boolean;
  direction: string;
  folder: string;
  thread_id: string;
  has_original_source: boolean;
  body_html?: string | null;
  bcc_addresses?: string[];
  failed_recipients?: string[];
  bounce_status?: string | null;
  bounce_recipient?: string | null;
  authentication?: { spf: string | null; dkim: string | null; dmarc: string | null };
  created_at: string;
}

export interface SentMessage {
  id: string;
  sender_address: string;
  receiver_address: string;
  to_addresses: string[];
  cc_addresses: string[];
  reply_to_address?: string | null;
  subject: string;
  body: string;
  attachments: Attachment[];
  label_ids: string[];
  direction: string;
  folder: string;
  is_starred: boolean;
  is_important: boolean;
  thread_id: string;
  has_original_source: boolean;
  body_html?: string | null;
  bcc_addresses?: string[];
  failed_recipients?: string[];
  bounce_status?: string | null;
  bounce_recipient?: string | null;
  authentication?: { spf: string | null; dkim: string | null; dmarc: string | null };
  delivery_status: string;
  created_at: string;
}

export interface Attachment {
  id: string;
  original_filename: string;
  stored_filename: string;
  size: number;
  content_type: string;
  storage_type: string;
  expires_at: string;
  status: string;
}

export interface MessageDetailResponse {
  id: string;
  sender_address: string;
  receiver_address: string;
  to_addresses: string[];
  cc_addresses: string[];
  reply_to_address?: string | null;
  subject: string;
  body: string;
  attachments: Attachment[];
  label_ids: string[];
  direction: string;
  folder: string;
  is_read?: boolean;
  delivery_status?: string;
  is_starred: boolean;
  is_important: boolean;
  thread_id: string;
  has_original_source: boolean;
  body_html?: string | null;
  bcc_addresses?: string[];
  failed_recipients?: string[];
  bounce_status?: string | null;
  bounce_recipient?: string | null;
  authentication?: { spf: string | null; dkim: string | null; dmarc: string | null };
  safety?: MessageSafetyState;
  created_at: string;
}

export type ReportType = 'spam' | 'phishing';
export type MessageFolder = 'inbox' | 'sent' | 'drafts' | 'archive' | 'spam' | 'trash';
export type BulkMessageAction = 'archive' | 'trash' | 'restore' | 'permanent_delete' | 'mark_read' | 'mark_unread' | 'star' | 'unstar' | 'mark_important' | 'mark_not_important' | 'move' | 'add_labels' | 'report_spam' | 'report_phishing';
export type FolderCountMap = Record<MessageFolder, number>;

export interface DraftMessageRequest {
  receiver_address: string;
  cc_addresses: string[];
  bcc_addresses: string[];
  subject: string;
  body: string;
  body_html: string;
}

export interface BulkMessageOptions {
  destination?: MessageFolder;
  label_ids?: string[];
}

export interface MessageTranslationResponse {
  message_id: string;
  translated_subject: string;
  translated_body: string;
  source_language: string | null;
  target_language: string;
  target_language_name: string;
}

export interface BulkMessageResponse {
  action: BulkMessageAction;
  processed_ids: string[];
  deleted_ids: string[];
  messages: MessageDetailResponse[];
}

export interface MessageSafetyState {
  sender_domain: string;
  reported_as: ReportType | null;
  sender_blocked: boolean;
  globally_blocked: boolean;
  spam_reports: number;
  phishing_reports: number;
  total_reports: number;
  user_block_count: number;
}

export interface SenderReportResult {
  sender_domain: string;
  report_type: ReportType;
  new_report: boolean;
  changed_report_type: boolean;
  spam_reports: number;
  phishing_reports: number;
  total_reports: number;
  user_block_count: number;
}

export interface SenderReportResponse extends MessageDetailResponse {
  report: SenderReportResult;
}

export interface SendMessageResponse extends SentMessage {
  message: string;
}

export interface DeleteMessageResponse {
  message: string;
}

export interface FolderCounts extends FolderCountMap {
  unread: FolderCountMap;
}
