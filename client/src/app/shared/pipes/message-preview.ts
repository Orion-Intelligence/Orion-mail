import { Pipe, PipeTransform } from '@angular/core';

import { messagePreview } from '../utils/message-presentation';

@Pipe({ name: 'messagePreview' })
export class MessagePreview implements PipeTransform {
  transform(body: string): string {
    return messagePreview(body);
  }
}
