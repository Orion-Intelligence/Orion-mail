import { SearchScopeOption } from '../model/navbar.model';

export const GO_TO_ROUTES: Record<string, string> = { i: '/inbox', s: '/sent', d: '/drafts', t: '/trash', a: '/all', l: '/settings/labels' };

export const MORE_STORAGE_KEY = 'orion-mail-sidebar-more';
export const SEARCHABLE_ROUTES = ['/inbox', '/sent', '/drafts', '/archive', '/spam', '/trash', '/starred', '/important', '/all', '/label/', '/search'];
export const MORE_ROUTES = ['/starred', '/important', '/archive', '/all', '/trash'];
export const MAILBOX_ROUTE_SEGMENTS = new Set(['inbox', 'sent', 'drafts', 'archive', 'spam', 'trash', 'starred', 'important', 'all', 'label']);

export const SEARCH_SCOPE_OPTIONS: SearchScopeOption[] = [
  { value: 'all', label: 'All mail', icon: 'allMail' },
  { value: 'inbox', label: 'Inbox', icon: 'inbox' },
  { value: 'sent', label: 'Sent', icon: 'send' },
  { value: 'archive', label: 'Archive', icon: 'archive' },
  { value: 'drafts', label: 'Drafts', icon: 'drafts' },
  { value: 'spam', label: 'Spam', icon: 'spam' },
  { value: 'trash', label: 'Trash', icon: 'delete' },
  { value: 'starred', label: 'Starred', icon: 'star' },
  { value: 'important', label: 'Important', icon: 'labelImportant' },
];

export const MESSAGE_FOLDER_NAMES: Record<string, string> = {
  inbox: 'Inbox',
  sent: 'Sent',
  archive: 'Archive',
  drafts: 'Drafts',
  spam: 'Spam',
  trash: 'Trash',
};
