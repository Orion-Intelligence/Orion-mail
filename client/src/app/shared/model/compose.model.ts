import { Attachment } from './message.model';

export type ComposeMode = 'new' | 'draft' | 'reply' | 'reply-all' | 'forward';

export interface ComposeRequest {
  mode: ComposeMode;
  draftId?: string;
  to?: string;
  cc?: string[];
  subject?: string;
  body?: string;
  inReplyToMessageId?: string;
  forwardMessageId?: string;
  forwardedAttachments?: Attachment[];
}

export type RecipientHintField = 'to' | 'cc';

export type RichTextCommandRunner = (commandId: string, showUI?: boolean, value?: string) => boolean;
