import { MessageBase } from '../model/message.model';

export function filterMessagesByTerm<T extends MessageBase>(messages: T[], rawTerm: string): T[] {
  const term = rawTerm.trim().toLowerCase();
  if (!term) {
    return messages;
  }
  return messages.filter((message) => [message.sender_address, message.receiver_address, message.subject, message.body].some((value) => value.toLowerCase().includes(term)));
}
