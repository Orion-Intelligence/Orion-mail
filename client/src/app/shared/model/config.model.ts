export interface SystemConfig {
  outgoing_attachment_max_size_mb: number;
  incoming_attachment_max_size_mb: number;
  attachment_retention_hours: number;
}

export interface SystemConfigField {
  key: keyof SystemConfig;
  label: string;
  description: string;
  unit: string;
  minimum: number;
  maximum: number;
}
