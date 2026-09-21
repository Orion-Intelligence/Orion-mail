export type SourceVerdictTone = 'pass' | 'fail' | 'neutral';

export interface SourceSummaryRow {
  label: string;
  value: string;
  verdict?: string;
  tone?: SourceVerdictTone;
}
