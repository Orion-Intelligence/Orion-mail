import { SystemConfigField } from '../model/config.model';

export const SYSTEM_CONFIG_FIELDS: SystemConfigField[] = [
  { key: 'outgoing_attachment_max_size_mb', label: 'Outgoing attachment limit', description: 'Maximum total attachment size on a message you send.', unit: 'MB', minimum: 1, maximum: 1 },
  { key: 'incoming_attachment_max_size_mb', label: 'Incoming attachment limit', description: 'Maximum total attachment size accepted on inbound mail.', unit: 'MB', minimum: 1, maximum: 5 },
  { key: 'attachment_retention_hours', label: 'Attachment retention', description: 'How long stored attachments are kept before cleanup removes them.', unit: 'hours', minimum: 1, maximum: 48 },
];
