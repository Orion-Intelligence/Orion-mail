import { SOURCE_AUTH_METHODS, SOURCE_FAILING_VERDICTS, SOURCE_MAX_DELIVERY_DELAY_SECONDS } from '../constants/message-source.constants';
import { MessageDetailResponse } from '../model/message.model';
import { SourceAuthMethod, SourceSummaryRow, SourceVerdictTone } from '../model/message-source.model';
import { parseUtcDate } from './date-utils';

export function parseSourceHeaders(source: string): Map<string, string[]> {
  const headerEnd = source.search(/\r?\n\r?\n/);
  const headerBlock = (headerEnd === -1 ? source : source.slice(0, headerEnd)).replace(/\r?\n[ \t]+/g, ' ');
  const headers = new Map<string, string[]>();

  for (const line of headerBlock.split(/\r?\n/)) {
    const separator = line.indexOf(':');
    if (separator <= 0) {
      continue;
    }
    const name = line.slice(0, separator).trim().toLowerCase();
    headers.set(name, [...(headers.get(name) ?? []), line.slice(separator + 1).trim()]);
  }

  return headers;
}

function verdictTone(verdict: string): SourceVerdictTone {
  if (verdict === 'pass') {
    return 'pass';
  }
  return SOURCE_FAILING_VERDICTS.has(verdict) ? 'fail' : 'neutral';
}

function authClause(headers: Map<string, string[]>, method: SourceAuthMethod, verdict: string): string {
  const pattern = new RegExp(`(?:^|;)\\s*${method}\\s*=\\s*([a-z]+)([^;]*)`, 'i');
  for (const header of headers.get('authentication-results') ?? []) {
    const match = pattern.exec(header);
    if (match) {
      return (match[1] ?? '').toLowerCase() === verdict ? match[2] ?? '' : '';
    }
  }
  return '';
}

function authDetail(headers: Map<string, string[]>, method: SourceAuthMethod, verdict: string): string {
  const clause = authClause(headers, method, verdict);

  if (method === 'spf') {
    const receivedSpf = headers.get('received-spf')?.[0] ?? '';
    const address = /designates\s+(\S+)\s+as permitted sender/i.exec(clause)?.[1]
      ?? /client-ip=([^\s;]+)/i.exec(clause)?.[1]
      ?? /client-ip=([^\s;]+)/i.exec(receivedSpf)?.[1];
    return address ? `with IP ${address}` : '';
  }

  const domain = (method === 'dkim' ? /header\.d=([^\s;]+)/i : /header\.from=([^\s;]+)/i).exec(clause)?.[1];
  return domain ? `with domain ${domain}` : '';
}

function deliveryDelay(seconds: number): string {
  if (seconds < 60) {
    return `${seconds} ${seconds === 1 ? 'second' : 'seconds'}`;
  }
  if (seconds < 3600) {
    const minutes = Math.round(seconds / 60);
    return `${minutes} ${minutes === 1 ? 'minute' : 'minutes'}`;
  }
  const hours = Math.round(seconds / 3600);
  return `${hours} ${hours === 1 ? 'hour' : 'hours'}`;
}

function createdAt(headers: Map<string, string[]>, message: MessageDetailResponse): string {
  const storedAt = parseUtcDate(message.created_at);
  const headerDate = new Date(headers.get('date')?.[0] ?? '');
  const created = Number.isNaN(headerDate.getTime()) ? storedAt : headerDate;

  if (!created) {
    return '';
  }

  const formatted = created.toLocaleString(undefined, { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
  const seconds = storedAt ? Math.round((storedAt.getTime() - created.getTime()) / 1000) : -1;

  if (message.direction !== 'incoming' || seconds < 0 || seconds > SOURCE_MAX_DELIVERY_DELAY_SECONDS) {
    return formatted;
  }
  return `${formatted} (Delivered after ${deliveryDelay(seconds)})`;
}

function authenticationRows(headers: Map<string, string[]>, message: MessageDetailResponse): SourceSummaryRow[] {
  if (message.direction !== 'incoming') {
    return [];
  }

  const rows = SOURCE_AUTH_METHODS.flatMap(([method, label]): SourceSummaryRow[] => {
    const verdict = (message.authentication?.[method] ?? '').trim().toLowerCase();
    return verdict ? [{ label, verdict: verdict.toUpperCase(), tone: verdictTone(verdict), value: authDetail(headers, method, verdict) }] : [];
  });

  if (rows.length) {
    return rows;
  }
  return [{
    label: 'Authentication',
    value: headers.has('received')
      ? 'Not checked. No SPF, DKIM or DMARC result was recorded for this message.'
      : 'Internal delivery. Sent within Orion Mail without SMTP, so SPF, DKIM and DMARC do not apply.',
  }];
}

export function summarizeMessageSource(source: string, message: MessageDetailResponse | null): SourceSummaryRow[] {
  if (!source || !message) {
    return [];
  }

  const headers = parseSourceHeaders(source);
  const rows: SourceSummaryRow[] = [
    { label: 'Message ID', value: headers.get('message-id')?.[0] ?? '' },
    { label: 'Created at', value: createdAt(headers, message) },
    { label: 'From', value: message.sender_address },
    { label: 'To', value: message.to_addresses.join(', ') },
    { label: 'Cc', value: message.cc_addresses.join(', ') },
    { label: 'Subject', value: message.subject },
  ];

  return [...rows.filter((row) => row.value), ...authenticationRows(headers, message)];
}
