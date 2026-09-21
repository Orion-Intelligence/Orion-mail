import type { PrivateKey, PublicKey } from 'openpgp';

import { E2E_ARMORED_MESSAGE_PATTERN, E2E_ARMORED_MESSAGE_PREFIX, E2E_COMMENT, E2E_KDF_ITERATIONS, E2E_KEY_LABEL, E2E_RECOVERY_ALPHABET, E2E_RECOVERY_LENGTH, E2E_VERIFIER_LABEL } from '../constants/e2e.constants';
import { E2eDerivedSecrets, E2eOpenedEnvelope, E2ePayload } from '../model/e2e.model';

export class E2eError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'E2eError';
  }
}

function loadOpenpgp(): Promise<typeof import('openpgp')> {
  return import('openpgp');
}

function toBase64(bytes: Uint8Array): string {
  let binary = '';
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary);
}

function fromBase64(value: string): Uint8Array<ArrayBuffer> {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

export function isE2eBody(body: string | null | undefined): boolean {
  const text = (body ?? '').trimStart();
  return text.startsWith(E2E_ARMORED_MESSAGE_PREFIX) && text.includes(`Comment: ${E2E_COMMENT}`) && E2E_ARMORED_MESSAGE_PATTERN.test(text);
}

export function splitE2eBody(body: string): { armored: string; trailer: string } {
  const match = E2E_ARMORED_MESSAGE_PATTERN.exec(body);
  if (!match) {
    throw new E2eError('Encrypted content is missing.');
  }
  return { armored: match[0], trailer: body.slice(match.index + match[0].length).trim() };
}

export function generateRecoveryCode(): string {
  const limit = 256 - (256 % E2E_RECOVERY_ALPHABET.length);
  let code = '';
  while (code.length < E2E_RECOVERY_LENGTH) {
    for (const byte of crypto.getRandomValues(new Uint8Array(E2E_RECOVERY_LENGTH))) {
      if (byte < limit && code.length < E2E_RECOVERY_LENGTH) {
        code += E2E_RECOVERY_ALPHABET[byte % E2E_RECOVERY_ALPHABET.length];
      }
    }
  }
  return code.match(/.{4}/g)?.join('-') ?? code;
}

export function normalizeRecoveryCode(code: string): string {
  return code.toUpperCase().replace(/[^A-Z0-9]/g, '');
}

async function labelled(master: CryptoKey, label: string): Promise<string> {
  return toBase64(new Uint8Array(await crypto.subtle.sign('HMAC', master, new TextEncoder().encode(label))));
}

export async function deriveSecrets(secret: string, saltBase64: string): Promise<E2eDerivedSecrets> {
  const material = await crypto.subtle.importKey('raw', new TextEncoder().encode(secret.normalize('NFKC')), 'PBKDF2', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits({ name: 'PBKDF2', hash: 'SHA-256', salt: fromBase64(saltBase64), iterations: E2E_KDF_ITERATIONS }, material, 256);
  const master = await crypto.subtle.importKey('raw', bits, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return { keySecret: await labelled(master, E2E_KEY_LABEL), verifier: await labelled(master, E2E_VERIFIER_LABEL) };
}

export async function sha256Hex(bytes: Uint8Array<ArrayBuffer>): Promise<string> {
  const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
  return Array.from(digest, (byte) => byte.toString(16).padStart(2, '0')).join('');
}

export function newSalt(): string {
  return toBase64(crypto.getRandomValues(new Uint8Array(16)));
}

export async function lockPrivateKey(privateKey: PrivateKey, keySecret: string): Promise<string> {
  const openpgp = await loadOpenpgp();
  const locked = await openpgp.encryptKey({ privateKey, passphrase: keySecret });
  return locked.armor();
}

export async function unlockPrivateKey(lockedArmored: string, keySecret: string): Promise<PrivateKey> {
  const openpgp = await loadOpenpgp();
  const locked = await openpgp.readPrivateKey({ armoredKey: lockedArmored });
  try {
    return await openpgp.decryptKey({ privateKey: locked, passphrase: keySecret });
  }
  catch {
    throw new E2eError('That passphrase or recovery code is not correct.');
  }
}

export async function generatePrivateKey(address: string): Promise<PrivateKey> {
  const openpgp = await loadOpenpgp();
  const { privateKey } = await openpgp.generateKey({ type: 'ecc', curve: 'curve25519Legacy', userIDs: [{ email: address }], format: 'object' });
  return privateKey;
}

export async function readPublicKey(armoredKey: string): Promise<PublicKey> {
  const openpgp = await loadOpenpgp();
  return openpgp.readKey({ armoredKey });
}

export async function publicKeyFingerprint(armoredKey: string): Promise<string> {
  return (await readPublicKey(armoredKey)).getFingerprint().toUpperCase();
}

export async function sealEnvelope(payload: E2ePayload, recipientKeys: PublicKey[], signingKey: PrivateKey | null): Promise<string> {
  const openpgp = await loadOpenpgp();
  const message = await openpgp.createMessage({ text: JSON.stringify(payload) });
  return openpgp.encrypt({ message, encryptionKeys: recipientKeys, signingKeys: signingKey ?? undefined, wildcard: true, format: 'armored', config: { showComment: true, commentString: E2E_COMMENT } });
}

export async function openEnvelope(armored: string, privateKey: PrivateKey, senderKey: PublicKey | null): Promise<E2eOpenedEnvelope> {
  const openpgp = await loadOpenpgp();
  const message = await openpgp.readMessage({ armoredMessage: armored });
  const { data, signatures } = await openpgp.decrypt({ message, decryptionKeys: privateKey, verificationKeys: senderKey ?? undefined, format: 'utf8' });
  let signed = false;

  if (senderKey && signatures.length > 0) {
    try {
      await Promise.all(signatures.map((signature) => signature.verified));
      signed = true;
    }
    catch {
      signed = false;
    }
  }

  const payload = JSON.parse(data) as E2ePayload;
  if (payload?.v !== 1 || typeof payload.body !== 'string') {
    throw new E2eError('Encrypted content has an unknown format.');
  }
  return { payload, signed };
}

export async function sealBytes(bytes: Uint8Array<ArrayBuffer>, recipientKeys: PublicKey[]): Promise<Uint8Array<ArrayBuffer>> {
  const openpgp = await loadOpenpgp();
  const message = await openpgp.createMessage({ binary: bytes });
  const sealed = await openpgp.encrypt({ message, encryptionKeys: recipientKeys, wildcard: true, format: 'binary' });
  return new Uint8Array(sealed as Uint8Array);
}

export async function openBytes(bytes: Uint8Array<ArrayBuffer>, privateKey: PrivateKey): Promise<Uint8Array<ArrayBuffer>> {
  const openpgp = await loadOpenpgp();
  const message = await openpgp.readMessage({ binaryMessage: bytes });
  const { data } = await openpgp.decrypt({ message, decryptionKeys: privateKey, format: 'binary' });
  return new Uint8Array(data as Uint8Array);
}
