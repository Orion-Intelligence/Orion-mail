export type SystemSearchScope = 'all' | 'inbox' | 'sent' | 'drafts' | 'archive' | 'spam' | 'trash' | 'starred' | 'important';
export type SearchScope = SystemSearchScope | `label:${string}`;
