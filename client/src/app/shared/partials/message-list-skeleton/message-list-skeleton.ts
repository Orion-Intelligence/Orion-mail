import { Component, input } from '@angular/core';

export type MessageListSkeletonVariant = 'select' | 'compact';

@Component({
  selector: 'app-message-list-skeleton',
  templateUrl: './message-list-skeleton.html',
})
export class MessageListSkeleton {
  readonly rows = [0, 1, 2, 3, 4, 5, 6, 7];
  variant = input<MessageListSkeletonVariant>('select');
}
