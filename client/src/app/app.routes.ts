import { Routes } from '@angular/router';

import { authGuard, mailboxSetupGuard } from './shared/guards/auth-guard';
import { Sent } from './pages/sent/sent';
import { Inbox } from './pages/inbox/inbox';
import { MessageDetail } from './pages/message-detail/message-detail';
import { LabelManager } from './pages/label-manager/label-manager';
import { LabelMessages } from './pages/label-messages/label-messages';
import { FolderMessages } from './pages/folder-messages/folder-messages';
import { ConfigureEmail } from './pages/configure-email/configure-email';
import { Settings } from './pages/settings/settings';

export const routes: Routes = [
  {
    path: '',
    redirectTo: 'inbox',
    pathMatch: 'full',
  },
  {
    path: 'configure-email',
    component: ConfigureEmail,
    canActivate: [mailboxSetupGuard],
  },
  {
    path: 'sent',
    component: Sent,
    canActivate: [authGuard],
  },
  {
    path: 'archive',
    component: FolderMessages,
    canActivate: [authGuard],
    data: { folder: 'archive' },
  },
  {
    path: 'trash',
    component: FolderMessages,
    canActivate: [authGuard],
    data: { folder: 'trash' },
  },
  {
    path: 'drafts',
    component: FolderMessages,
    canActivate: [authGuard],
    data: { folder: 'drafts' },
  },
  {
    path: 'spam',
    component: FolderMessages,
    canActivate: [authGuard],
    data: { folder: 'spam' },
  },
  {
    path: 'starred',
    component: FolderMessages,
    canActivate: [authGuard],
    data: { folder: 'starred' },
  },
  {
    path: 'important',
    component: FolderMessages,
    canActivate: [authGuard],
    data: { folder: 'important' },
  },
  {
    path: 'all',
    component: FolderMessages,
    canActivate: [authGuard],
    data: { folder: 'all' },
  },
  {
    path: 'search',
    component: FolderMessages,
    canActivate: [authGuard],
    data: { folder: 'search' },
  },
  {
    path: 'inbox',
    component: Inbox,
    canActivate: [authGuard],
  },
  {
    path: 'settings',
    component: Settings,
    canActivate: [authGuard],
  },
  {
    path: 'settings/labels',
    component: LabelManager,
    canActivate: [authGuard],
  },
  {
    path: 'label/:id',
    component: LabelMessages,
    canActivate: [authGuard],
  },
  {
    path: 'message/:id',
    component: MessageDetail,
    canActivate: [authGuard],
  },
  {
    path: '**',
    redirectTo: 'inbox',
  },
];
