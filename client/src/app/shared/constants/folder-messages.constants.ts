import { FolderView, SystemFolder } from '../model/folder-messages.model';

export const FOLDER_VIEWS: Record<SystemFolder, FolderView> = {
  archive: { title: 'Archive', icon: 'archive', hint: '', emptyText: 'No archived messages' },
  trash: { title: 'Trash', icon: 'delete', hint: 'Messages remain here until you permanently delete them.', emptyText: 'No conversations in Trash' },
  spam: { title: 'Spam', icon: 'spam', hint: 'Messages from reported or blocked senders land here.', emptyText: 'Hooray, no spam here!' },
  drafts: { title: 'Drafts', icon: 'drafts', hint: '', emptyText: "You don't have any saved drafts" },
  starred: { title: 'Starred', icon: 'star', hint: '', emptyText: 'No starred messages' },
  important: { title: 'Important', icon: 'labelImportant', hint: '', emptyText: 'Nothing in Important' },
  all: { title: 'All Mail', icon: 'allMail', hint: '', emptyText: 'No conversations' },
  search: { title: 'Search results', icon: 'search', hint: '', emptyText: 'No messages match your search' },
};
