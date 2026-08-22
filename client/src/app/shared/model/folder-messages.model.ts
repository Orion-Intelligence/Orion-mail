import { IconName } from './icon.model';

export type SystemFolder = 'archive' | 'trash' | 'spam' | 'drafts' | 'starred' | 'important' | 'all' | 'search';

export interface FolderView {
  title: string;
  icon: IconName;
  hint: string;
  emptyText: string;
}
