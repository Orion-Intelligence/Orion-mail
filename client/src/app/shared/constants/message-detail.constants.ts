import { MessageSource } from '../model/message-detail.model';

export const TRANSLATION_LANGUAGES = [
  ['en', 'English'], ['ur', 'Urdu'], ['ar', 'Arabic'], ['zh-CN', 'Chinese (Simplified)'],
  ['fr', 'French'], ['de', 'German'], ['hi', 'Hindi'], ['id', 'Indonesian'], ['it', 'Italian'],
  ['ja', 'Japanese'], ['ko', 'Korean'], ['nl', 'Dutch'], ['fa', 'Persian'], ['pl', 'Polish'],
  ['pt', 'Portuguese'], ['ru', 'Russian'], ['es', 'Spanish'], ['tr', 'Turkish'], ['uk', 'Ukrainian'], ['vi', 'Vietnamese'],
] as const;

export const SOURCE_NAMES: ReadonlyMap<Exclude<MessageSource, 'label'> | string, string> = new Map<Exclude<MessageSource, 'label'> | string, string>([
  ['inbox', 'Inbox'], ['sent', 'Sent'], ['archive', 'Archive'], ['trash', 'Trash'], ['spam', 'Spam'],
  ['starred', 'Starred'], ['important', 'Important'], ['all', 'All Mail'], ['search', 'Search results'],
]);
