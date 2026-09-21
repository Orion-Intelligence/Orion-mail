import type { PublicKey } from 'openpgp';

export type E2eStatus = 'unknown' | 'unconfigured' | 'locked' | 'unlocked' | 'mismatch';
export type E2eMessageState = 'decrypted' | 'locked' | 'failed';
export type E2eSendMode = 'plain' | 'e2e' | 'locked' | 'key-changed';

export type E2ePrompt = 'none' | 'setup' | 'unlock' | 'mismatch' | 'key-changed';

export interface E2eKeyState {
  configured: boolean;
  mailbox_address: string;
  fingerprint?: string;
  public_key?: string;
  kdf_salt?: string;
  created_at?: string;
  updated_at?: string;
}

export interface E2eUnlockResponse extends E2eKeyState {
  kind: 'passphrase' | 'recovery';
  private_key: string;
}

export interface E2eKeyUpload {
  fingerprint: string;
  public_key: string;
  locked_private_key: string;
  kdf_salt: string;
  verifier: string;
  recovery_private_key?: string;
  recovery_verifier?: string;
  proof?: string;
}

export interface E2ePublicKeyRecord {
  address: string;
  fingerprint: string;
  public_key: string;
}

export interface E2eAttachmentEntry {
  file: string;
  name: string;
  type: string;
  size: number;
  sha256: string;
}

export interface E2ePayload {
  v: 1;
  from: string;
  to: string[];
  subject: string;
  body: string;
  body_html: string;
  attachments: E2eAttachmentEntry[];
}

export interface E2eMessageInfo {
  state: E2eMessageState;
  verified: boolean;
  warning?: string;
}

export interface E2eKeyChange {
  address: string;
  pinned: string;
  current: string | null;
}

export interface E2eSendPlan {
  mode: E2eSendMode;
  changes: E2eKeyChange[];
}

export type E2eDialogView = 'setup' | 'recovery-code' | 'unlock' | 'forgot' | 'reset' | 'mismatch' | 'key-changed';

export interface E2eResolvedKey {
  fingerprint: string;
  key: PublicKey;
}

export interface E2eOpenedEnvelope {
  payload: E2ePayload;
  signed: boolean;
}

export interface E2eOpenedCache extends E2eOpenedEnvelope {
  armored: string;
}

export interface E2eDerivedSecrets {
  keySecret: string;
  verifier: string;
}
