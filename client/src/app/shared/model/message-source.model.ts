export type SourceVerdictTone = 'pass' | 'fail' | 'neutral';
export type SourceAuthMethod = 'spf' | 'dkim' | 'dmarc';

export interface SourceSummaryRow {
  label: string;
  value: string;
  verdict?: string;
  tone?: SourceVerdictTone;
}
