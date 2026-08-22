import { MessageDetailResponse } from './message.model';

export interface MailLabel {
  id: string;
  name: string;
  color: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface LabelCreateRequest {
  name: string;
  color: string;
}

export interface LabelUpdateRequest {
  name?: string;
  color?: string;
}

export interface LabelMessagesResponse {
  label: MailLabel;
  messages: MessageDetailResponse[];
}
