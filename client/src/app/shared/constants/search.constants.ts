import { SystemSearchScope } from '../model/search.model';

export const SYSTEM_SEARCH_SCOPES = new Set<SystemSearchScope>(['all', 'inbox', 'sent', 'drafts', 'archive', 'spam', 'trash', 'starred', 'important']);
