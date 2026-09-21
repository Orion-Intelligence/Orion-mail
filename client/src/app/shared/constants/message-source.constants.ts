import { SourceAuthMethod } from '../model/message-source.model';

export const SOURCE_AUTH_METHODS: [SourceAuthMethod, string][] = [['spf', 'SPF'], ['dkim', 'DKIM'], ['dmarc', 'DMARC']];
export const SOURCE_FAILING_VERDICTS = new Set(['fail', 'softfail', 'permerror', 'reject']);
export const SOURCE_MAX_DELIVERY_DELAY_SECONDS = 30 * 24 * 60 * 60;
