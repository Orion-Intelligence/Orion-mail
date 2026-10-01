export interface EncryptedFileResult {
    encrypted: Blob;
    key: string;
    iv: string;
}

function toBase64Url(bytes: Uint8Array): string {
  let binary = '';

  for (const byte of bytes) {
    binary += String.fromCharCode(byte) 
  }

  return btoa(binary)
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/g, '');
}

function fromBase64Url(value: string): Uint8Array {
  let normalized = value
    .replace(/-/g, '+')
    .replace(/_/g, '/');

  while (normalized.length % 4 !== 0) {
    normalized += '='; 
  }

  const binary = atob(normalized);

  const bytes = new Uint8Array(binary.length);

  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }

  return bytes;
}

function asArrayBuffer(bytes: Uint8Array<ArrayBufferLike>): ArrayBuffer {
  const copy = new Uint8Array(bytes.byteLength);

  copy.set(bytes);

  return copy.buffer;
}

export async function encryptFile(file: File): Promise<EncryptedFileResult> {

  const key = await crypto.subtle.generateKey({
    name: 'AES-GCM',
    length: 256,
  },
  true,
  [
    'encrypt',
    'decrypt',
  ],);

  const iv = crypto.getRandomValues(new Uint8Array(12));

  const plaintext = await file.arrayBuffer();

  const ciphertext = await crypto.subtle.encrypt({
    name: 'AES-GCM',
    iv: asArrayBuffer(iv),
  },
  key,
  plaintext,);

  const exportedKey = new Uint8Array(await crypto.subtle.exportKey('raw', key));

  return {
    encrypted: new Blob([ciphertext],
      {
        type: 'application/octet-stream',
      },),

    key: toBase64Url(exportedKey),

    iv: toBase64Url(iv),
  };
}

export async function decryptFile(encrypted: ArrayBuffer, keyBase64Url: string, ivBase64Url: string): Promise<ArrayBuffer> {

  const keyBytes = fromBase64Url(keyBase64Url);

  const iv = fromBase64Url(ivBase64Url);

  if (keyBytes.length !== 32) {
    throw new Error('Invalid AES-256 key.',);
  }

  if (iv.length !== 12) {
    throw new Error('Invalid AES-GCM IV.',);
  }

  const key = await crypto.subtle.importKey('raw',
    asArrayBuffer(keyBytes),
    {
      name: 'AES-GCM',
    },
    false,
    [
      'decrypt',
    ],);

  return crypto.subtle.decrypt({
    name: 'AES-GCM',
    iv: asArrayBuffer(iv),
  },
  key,
  encrypted,);
}
