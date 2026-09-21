import { HttpClient } from '@angular/common/http';
import { Injectable, effect, inject, signal, untracked } from '@angular/core';
import type { PrivateKey, PublicKey } from 'openpgp';
import { Observable, OperatorFunction, firstValueFrom, from, switchMap } from 'rxjs';

import { environment } from '../../environments/environment';
import { E2E_FAILED_TEXT, E2E_KEY_CACHE_MS, E2E_LOCKED_TEXT, E2E_MAX_SEALED_ATTACHMENT_BYTES, E2E_MIN_PASSPHRASE_LENGTH, E2E_NO_CHAT_KEY_TEXT, E2E_OWN_KEY_STORAGE, E2E_PIN_STORAGE, E2E_STORED_KEY_STORAGE, E2E_SUBJECT, E2E_TEST_OPT_IN_STORAGE } from '../shared/constants/e2e.constants';
import { E2eAttachmentEntry, E2eDerivedSecrets, E2eKeyChange, E2eKeyState, E2eKeyUpload, E2eMessageInfo, E2eOpenedCache, E2ePayload, E2ePrompt, E2ePublicKeyRecord, E2eResolvedKey, E2eSendPlan, E2eStatus, E2eUnlockResponse } from '../shared/model/e2e.model';
import { Attachment, DraftMessageRequest, MessageBase, MessengerConversation, MessengerMessage, MessengerUser, SendMessageRequest } from '../shared/model/message.model';
import { E2eError, deriveSecrets, generatePrivateKey, generateRecoveryCode, isE2eBody, lockPrivateKey, newSalt, normalizeRecoveryCode, openBytes, openEnvelope, publicKeyFingerprint, readPublicKey, sealBytes, sealEnvelope, sha256Hex, splitE2eBody, unlockPrivateKey } from '../shared/utils/e2e-crypto';

@Injectable({
  providedIn: 'root',
})
export class E2eService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiBaseUrl}/mailboxes`;
  private readonly attachmentIndex = new Map<string, E2eAttachmentEntry>();
  private readonly keyCache = new Map<string, { at: number; resolved: E2eResolvedKey | null }>();
  private readonly openedCache = new Map<string, E2eOpenedCache>();
  private readonly chatAddresses = new Map<string, string>();
  private state: E2eKeyState | null = null;
  private privateKey: PrivateKey | null = null;
  private ownKey: E2eResolvedKey | null = null;
  private loading: Promise<void> | null = null;

  readonly status = signal<E2eStatus>('unknown');
  readonly fingerprint = signal('');
  readonly mailboxAddress = signal('');
  readonly prompt = signal<E2ePrompt>('none');
  readonly keyChanges = signal<E2eKeyChange[]>([]);
  readonly revision = signal(0);

  private readStorage(key: string): string | null {
    try {
      return localStorage.getItem(key);
    }
    catch {
      return null;
    }
  }

  private writeStorage(key: string, value: string | null): void {
    try {
      if (value === null) {
        localStorage.removeItem(key);
      }
      else {
        localStorage.setItem(key, value);
      }
    }
    catch {
      return;
    }
  }

  private pins(): Record<string, string> {
    try {
      return JSON.parse(this.readStorage(`${E2E_PIN_STORAGE}:${this.mailboxAddress()}`) ?? '{}') as Record<string, string>;
    }
    catch {
      return {};
    }
  }

  private savePins(pins: Record<string, string>): void {
    this.writeStorage(`${E2E_PIN_STORAGE}:${this.mailboxAddress()}`, JSON.stringify(pins));
  }

  private pin(address: string, fingerprint: string): void {
    const pins = this.pins();
    if (!pins[address]) {
      this.savePins({ ...pins, [address]: fingerprint });
    }
  }

  reloadOnKeyChange(reload: () => void): void {
    effect(() => {
      if (this.revision() > 0) {
        untracked(reload);
      }
    });
  }

  ensureLoaded(): Promise<void> {
    this.loading ??= this.load();
    return this.loading;
  }

  reload(): Promise<void> {
    this.loading = this.load();
    return this.loading;
  }

  private async load(): Promise<void> {
    let state: E2eKeyState | null = null;
    try {
      state = await firstValueFrom(this.http.get<E2eKeyState>(`${this.baseUrl}/me/e2e-key`));
    }
    catch {
      state = null;
    }

    this.state = state;
    this.ownKey = null;
    this.mailboxAddress.set(state?.mailbox_address ?? this.mailboxAddress());
    const remembered = this.mailboxAddress() ? this.readStorage(`${E2E_OWN_KEY_STORAGE}:${this.mailboxAddress()}`) : null;

    if (!state?.configured || !state.public_key) {
      this.privateKey = null;
      this.fingerprint.set('');
      this.status.set(remembered ? 'mismatch' : state ? 'unconfigured' : 'unknown');
      return;
    }

    const fingerprint = await publicKeyFingerprint(state.public_key);
    if (remembered && remembered !== fingerprint) {
      this.privateKey = null;
      this.fingerprint.set(fingerprint);
      this.status.set('mismatch');
      return;
    }

    this.ownKey = { fingerprint, key: await readPublicKey(state.public_key) };
    this.fingerprint.set(fingerprint);
    if (this.privateKey?.getFingerprint().toUpperCase() !== fingerprint) {
      this.privateKey = await this.restoreFromTab(fingerprint);
    }
    this.status.set(this.privateKey ? 'unlocked' : 'locked');
  }

  private tabStorageKey(): string {
    return `${E2E_STORED_KEY_STORAGE}:${this.mailboxAddress()}`;
  }

  private tabSecret(): Promise<string> {
    return firstValueFrom(this.http.post<{ secret: string }>(`${this.baseUrl}/me/e2e-key/session`, {})).then((response) => response.secret);
  }

  private async rememberForTab(privateKey: PrivateKey): Promise<void> {
    try {
      this.writeStorage(this.tabStorageKey(), await lockPrivateKey(privateKey, await this.tabSecret()));
    }
    catch {
      this.forgetTab();
    }
  }

  private async restoreFromTab(fingerprint: string): Promise<PrivateKey | null> {
    try {
      const stored = this.readStorage(this.tabStorageKey());
      if (!stored) {
        return null;
      }
      const privateKey = await unlockPrivateKey(stored, await this.tabSecret());
      if (privateKey.getFingerprint().toUpperCase() === fingerprint) {
        return privateKey;
      }
    }
    catch {
      this.forgetTab();
      return null;
    }
    this.forgetTab();
    return null;
  }

  private forgetTab(): void {
    this.writeStorage(this.tabStorageKey(), null);
  }

  private automated(): boolean {
    return Boolean((window as unknown as { Cypress?: unknown }).Cypress) && this.readStorage(E2E_TEST_OPT_IN_STORAGE) !== 'on';
  }

  async requirePrompt(): Promise<void> {
    await this.ensureLoaded();
    if (this.automated()) {
      return;
    }
    const status = this.status();
    this.prompt.set(status === 'unconfigured' ? 'setup' : status === 'locked' ? 'unlock' : status === 'mismatch' ? 'mismatch' : 'none');
  }

  private assertPassphrase(passphrase: string): void {
    if (passphrase.length < E2E_MIN_PASSPHRASE_LENGTH) {
      throw new E2eError(`Use a passphrase of at least ${E2E_MIN_PASSPHRASE_LENGTH} characters.`);
    }
  }

  private async adopt(privateKey: PrivateKey, state: E2eKeyState): Promise<void> {
    const fingerprint = privateKey.getFingerprint().toUpperCase();
    if (!state.public_key || await publicKeyFingerprint(state.public_key) !== fingerprint) {
      throw new E2eError('The stored key does not match your private key.');
    }
    this.state = state;
    this.privateKey = privateKey;
    this.ownKey = { fingerprint, key: await readPublicKey(state.public_key) };
    this.mailboxAddress.set(state.mailbox_address);
    this.fingerprint.set(fingerprint);
    this.writeStorage(`${E2E_OWN_KEY_STORAGE}:${state.mailbox_address}`, fingerprint);
    this.status.set('unlocked');
    this.revision.update((revision) => revision + 1);
    await this.rememberForTab(privateKey);
  }

  private upload(upload: E2eKeyUpload): Promise<E2eKeyState> {
    return firstValueFrom(this.http.put<E2eKeyState>(`${this.baseUrl}/me/e2e-key`, upload));
  }

  private async fetchLockedKey(secrets: E2eDerivedSecrets, kind: 'passphrase' | 'recovery'): Promise<{ response: E2eUnlockResponse; privateKey: PrivateKey }> {
    let response: E2eUnlockResponse;
    try {
      response = await firstValueFrom(this.http.post<E2eUnlockResponse>(`${this.baseUrl}/me/e2e-key/unlock`, { verifier: secrets.verifier, kind }));
    }
    catch (error) {
      const status = (error as { status?: number }).status;
      if (status === 403) {
        throw new E2eError(kind === 'recovery' ? 'That recovery code is not correct.' : 'That passphrase is not correct.');
      }
      throw error;
    }
    return { response, privateKey: await unlockPrivateKey(response.private_key, secrets.keySecret) };
  }

  private salt(): string {
    const salt = this.state?.kdf_salt;
    if (!this.state?.configured || !salt) {
      throw new E2eError('End-to-end encryption is not set up for this mailbox.');
    }
    return salt;
  }

  async setup(passphrase: string): Promise<string> {
    this.assertPassphrase(passphrase);
    await this.ensureLoaded();
    if (this.state?.configured) {
      throw new E2eError('End-to-end encryption is already set up for this mailbox.');
    }
    if (!this.mailboxAddress()) {
      throw new E2eError('Your mailbox could not be loaded. Try again.');
    }

    const salt = newSalt();
    const recoveryCode = generateRecoveryCode();
    const privateKey = await generatePrivateKey(this.mailboxAddress());
    const [secrets, recovery] = await Promise.all([deriveSecrets(passphrase, salt), deriveSecrets(normalizeRecoveryCode(recoveryCode), salt)]);
    const upload: E2eKeyUpload = { fingerprint: privateKey.getFingerprint().toUpperCase(), public_key: privateKey.toPublic().armor(), kdf_salt: salt, locked_private_key: await lockPrivateKey(privateKey, secrets.keySecret), verifier: secrets.verifier, recovery_private_key: await lockPrivateKey(privateKey, recovery.keySecret), recovery_verifier: recovery.verifier };
    await this.adopt(privateKey, await this.upload(upload));
    return recoveryCode;
  }

  async unlock(passphrase: string): Promise<void> {
    await this.ensureLoaded();
    const { response, privateKey } = await this.fetchLockedKey(await deriveSecrets(passphrase, this.salt()), 'passphrase');
    await this.adopt(privateKey, response);
    this.prompt.set('none');
  }

  private async relock(current: E2eDerivedSecrets, kind: 'passphrase' | 'recovery', nextPassphrase: string): Promise<void> {
    this.assertPassphrase(nextPassphrase);
    const { response, privateKey } = await this.fetchLockedKey(current, kind);
    if (!response.fingerprint || !response.public_key || !response.kdf_salt) {
      throw new E2eError('The stored key is incomplete.');
    }
    const next = await deriveSecrets(nextPassphrase, response.kdf_salt);
    const upload: E2eKeyUpload = { fingerprint: response.fingerprint, public_key: response.public_key, kdf_salt: response.kdf_salt, locked_private_key: await lockPrivateKey(privateKey, next.keySecret), verifier: next.verifier, proof: current.verifier };
    await this.adopt(privateKey, await this.upload(upload));
    this.prompt.set('none');
  }

  async changePassphrase(currentPassphrase: string, nextPassphrase: string): Promise<void> {
    await this.ensureLoaded();
    await this.relock(await deriveSecrets(currentPassphrase, this.salt()), 'passphrase', nextPassphrase);
  }

  async recover(recoveryCode: string, nextPassphrase: string): Promise<void> {
    await this.ensureLoaded();
    await this.relock(await deriveSecrets(normalizeRecoveryCode(recoveryCode), this.salt()), 'recovery', nextPassphrase);
  }

  forget(signedOut: boolean): void {
    if (signedOut) {
      this.forgetTab();
    }
    this.privateKey = null;
    this.openedCache.clear();
    this.attachmentIndex.clear();
    this.prompt.set('none');
    if (this.status() === 'unlocked') {
      this.status.set('locked');
    }
  }

  async reset(): Promise<void> {
    await firstValueFrom(this.http.delete(`${this.baseUrl}/me/e2e-key`));
    this.writeStorage(`${E2E_OWN_KEY_STORAGE}:${this.mailboxAddress()}`, null);
    this.forgetTab();
    this.privateKey = null;
    this.openedCache.clear();
    await this.reload();
    this.revision.update((revision) => revision + 1);
    this.prompt.set(this.status() === 'unconfigured' ? 'setup' : 'none');
  }

  async trustServerKey(): Promise<void> {
    this.writeStorage(`${E2E_OWN_KEY_STORAGE}:${this.mailboxAddress()}`, null);
    await this.reload();
    this.prompt.set(this.status() === 'locked' ? 'unlock' : 'none');
  }

  requestUnlock(): void {
    const status = this.status();
    if (status === 'locked') {
      this.prompt.set('unlock');
    }
    else if (status === 'unconfigured') {
      this.prompt.set('setup');
    }
  }

  dismissPrompt(): void {
    this.prompt.set('none');
  }

  private async resolveKeys(addresses: string[]): Promise<Map<string, E2eResolvedKey | null>> {
    const now = Date.now();
    const resolved = new Map<string, E2eResolvedKey | null>();
    const missing: string[] = [];

    for (const address of new Set(addresses)) {
      const cached = this.keyCache.get(address);
      if (address === this.mailboxAddress() && this.ownKey) {
        resolved.set(address, this.ownKey);
      }
      else if (cached && now - cached.at < E2E_KEY_CACHE_MS) {
        resolved.set(address, cached.resolved);
      }
      else {
        missing.push(address);
      }
    }

    if (missing.length > 0) {
      const response = await firstValueFrom(this.http.post<{ keys: E2ePublicKeyRecord[] }>(`${this.baseUrl}/e2e-keys/lookup`, { addresses: missing }));
      const records = new Map(response.keys.map((record) => [record.address.toLowerCase(), record]));
      for (const address of missing) {
        const record = records.get(address);
        const key = record ? await readPublicKey(record.public_key) : null;
        const entry = key ? { fingerprint: key.getFingerprint().toUpperCase(), key } : null;
        this.keyCache.set(address, { at: now, resolved: entry });
        resolved.set(address, entry);
      }
    }

    return resolved;
  }

  private recipientsOf(request: { receiver_address: string; cc_addresses: string[]; bcc_addresses?: string[] }): string[] {
    return [...new Set([request.receiver_address, ...request.cc_addresses, ...(request.bcc_addresses ?? [])].map((address) => address.trim().toLowerCase()).filter(Boolean))];
  }

  async planSend(request: { receiver_address: string; cc_addresses: string[]; bcc_addresses?: string[]; sender_identity_type?: string }): Promise<E2eSendPlan> {
    await this.ensureLoaded();
    const status = this.status();
    const recipients = this.recipientsOf(request);

    if (status === 'mismatch') {
      return { mode: 'key-changed', changes: [{ address: this.mailboxAddress(), pinned: this.readStorage(`${E2E_OWN_KEY_STORAGE}:${this.mailboxAddress()}`) ?? '', current: this.fingerprint() || null }] };
    }
    if (request.sender_identity_type === 'disposable' || recipients.length === 0 || (status !== 'locked' && status !== 'unlocked')) {
      return { mode: 'plain', changes: [] };
    }

    const resolved = await this.resolveKeys(recipients);
    const pins = this.pins();
    const changes: E2eKeyChange[] = recipients.filter((address) => pins[address] && pins[address] !== (resolved.get(address)?.fingerprint ?? null)).map((address) => ({ address, pinned: pins[address] ?? '', current: resolved.get(address)?.fingerprint ?? null }));

    if (changes.length > 0) {
      return { mode: 'key-changed', changes };
    }
    if (recipients.every((address) => resolved.get(address))) {
      return { mode: status === 'unlocked' ? 'e2e' : 'locked', changes: [] };
    }
    return { mode: 'plain', changes: [] };
  }

  reviewKeyChanges(changes: E2eKeyChange[]): void {
    this.keyChanges.set(changes);
    this.prompt.set('key-changed');
  }

  acceptKeyChanges(changes: E2eKeyChange[]): void {
    const pins = this.pins();
    for (const change of changes) {
      if (change.current) {
        pins[change.address] = change.current;
      }
      else {
        delete pins[change.address];
      }
    }
    this.savePins(pins);
    this.keyChanges.set([]);
    if (this.prompt() === 'key-changed') {
      this.prompt.set('none');
    }
  }

  private async materializeForwarded(request: SendMessageRequest, all: boolean): Promise<SendMessageRequest> {
    const ids = request.forward_attachment_ids.filter((id) => all || this.attachmentIndex.has(id));
    if (ids.length === 0) {
      return request;
    }

    const files: File[] = [];
    for (const id of ids) {
      const blob = await this.openAttachment(id, await firstValueFrom(this.http.get(`${environment.apiBaseUrl}/attachments/${id}/download`, { responseType: 'blob' })));
      const entry = this.attachmentIndex.get(id);
      files.push(new File([blob], entry?.name ?? `attachment-${files.length + 1}`, { type: entry?.type ?? blob.type }));
    }
    return { ...request, files: [...request.files, ...files], forward_attachment_ids: request.forward_attachment_ids.filter((id) => !ids.includes(id)) };
  }

  async sealOutgoing(request: SendMessageRequest): Promise<SendMessageRequest> {
    const plan = await this.planSend(request);
    if (plan.mode === 'locked') {
      this.requestUnlock();
      throw new E2eError('Unlock your encryption key to send this message end-to-end encrypted. It is saved in Drafts.');
    }
    if (plan.mode === 'key-changed') {
      throw new E2eError(`The encryption key for ${plan.changes.map((change) => change.address).join(', ')} has changed. Review it in the compose window before sending. The message is saved in Drafts.`);
    }

    const prepared = await this.materializeForwarded(request, plan.mode === 'e2e');
    if (plan.mode !== 'e2e' || !this.privateKey || !this.ownKey) {
      return prepared;
    }

    const recipients = this.recipientsOf(prepared);
    const resolved = await this.resolveKeys(recipients);
    const keys = [...recipients.map((address) => resolved.get(address)?.key).filter((key): key is PublicKey => Boolean(key)), this.ownKey.key];
    const attachments: E2eAttachmentEntry[] = [];
    const sealedFiles: File[] = [];
    let sealedBytes = 0;

    for (const [index, file] of prepared.files.entries()) {
      const bytes = new Uint8Array(await file.arrayBuffer());
      const sealed = await sealBytes(bytes, keys);
      const name = `e2e-${index + 1}.bin`;
      sealedBytes += sealed.length;
      attachments.push({ file: name, name: file.name, type: file.type || 'application/octet-stream', size: file.size, sha256: await sha256Hex(bytes) });
      sealedFiles.push(new File([sealed], name, { type: 'application/octet-stream' }));
    }
    if (sealedBytes > E2E_MAX_SEALED_ATTACHMENT_BYTES) {
      throw new E2eError('These attachments are slightly over the 1 MB limit once encrypted. Remove one and send again. The message is saved in Drafts.');
    }

    const payload: E2ePayload = { v: 1, from: this.mailboxAddress(), to: [prepared.receiver_address, ...prepared.cc_addresses].map((address) => address.trim().toLowerCase()), subject: prepared.subject, body: prepared.body, body_html: prepared.body_html ?? '', attachments };
    const armored = await sealEnvelope(payload, keys, this.privateKey);
    for (const address of recipients) {
      const fingerprint = resolved.get(address)?.fingerprint;
      if (fingerprint) {
        this.pin(address, fingerprint);
      }
    }
    return { ...prepared, subject: E2E_SUBJECT, body: armored, body_html: undefined, files: sealedFiles, forward_attachment_ids: [] };
  }

  async sealDraft(draft: DraftMessageRequest): Promise<DraftMessageRequest> {
    await this.ensureLoaded();
    const status = this.status();
    if (status === 'mismatch') {
      throw new E2eError('Your encryption key needs attention before drafts can be saved.');
    }
    if (!this.ownKey || (status !== 'locked' && status !== 'unlocked') || !(draft.subject || draft.body || draft.body_html)) {
      return draft;
    }

    const payload: E2ePayload = { v: 1, from: this.mailboxAddress(), to: [], subject: draft.subject, body: draft.body, body_html: draft.body_html, attachments: [] };
    return { ...draft, subject: E2E_SUBJECT, body: await sealEnvelope(payload, [this.ownKey.key], this.privateKey), body_html: '' };
  }

  async openAttachment(attachmentId: string, blob: Blob): Promise<Blob> {
    const entry = this.attachmentIndex.get(attachmentId);
    if (!entry) {
      return blob;
    }
    if (!this.privateKey) {
      this.requestUnlock();
      throw new E2eError('Unlock your encryption key to open this attachment.');
    }

    const bytes = await openBytes(new Uint8Array(await blob.arrayBuffer()), this.privateKey);
    if (await sha256Hex(bytes) !== entry.sha256) {
      throw new E2eError('This attachment does not match the signed message and was not opened.');
    }
    return new Blob([bytes], { type: entry.type });
  }

  rememberChatUsers(users: MessengerUser[]): void {
    for (const user of users) {
      this.chatAddresses.set(user.id, user.mailbox_address.trim().toLowerCase());
    }
  }

  async sealChat(receiverUserId: string, body: string): Promise<string> {
    const receiver = this.chatAddresses.get(receiverUserId);
    if (!receiver) {
      throw new E2eError('This conversation could not be secured. Reload the page and try again.');
    }

    const plan = await this.planSend({ receiver_address: receiver, cc_addresses: [] });
    if (plan.mode === 'locked') {
      this.requestUnlock();
      throw new E2eError('Unlock your encryption key to send this message.');
    }
    if (plan.mode === 'key-changed') {
      this.reviewKeyChanges(plan.changes);
      throw new E2eError('This person\u2019s encryption key has changed. Review it before sending.');
    }
    if (plan.mode !== 'e2e' || !this.privateKey || !this.ownKey) {
      if (this.status() === 'unlocked' || this.status() === 'locked') {
        throw new E2eError(E2E_NO_CHAT_KEY_TEXT);
      }
      return body;
    }

    const receiverKey = (await this.resolveKeys([receiver])).get(receiver);
    if (!receiverKey) {
      throw new E2eError(E2E_NO_CHAT_KEY_TEXT);
    }
    this.pin(receiver, receiverKey.fingerprint);
    const payload: E2ePayload = { v: 1, from: this.mailboxAddress(), to: [receiver], subject: '', body, body_html: '', attachments: [] };
    return sealEnvelope(payload, [receiverKey.key, this.ownKey.key], this.privateKey);
  }

  private async openChatBody(id: string, body: string, sender: string | null): Promise<{ body: string; e2e?: E2eMessageInfo }> {
    if (!isE2eBody(body)) {
      return { body };
    }
    await this.ensureLoaded();
    if (!this.privateKey) {
      return { body: 'Encrypted message. Unlock your key to read it.', e2e: { state: 'locked', verified: false } };
    }

    try {
      const { armored } = splitE2eBody(body);
      const senderKey = sender ? (await this.resolveKeys([sender])).get(sender) ?? null : null;
      let opened = this.openedCache.get(id);
      if (opened?.armored !== armored) {
        opened = { armored, ...await openEnvelope(armored, this.privateKey, senderKey?.key ?? null) };
        this.openedCache.set(id, opened);
      }
      const pinned = sender ? this.pins()[sender] : undefined;
      const verified = Boolean(sender && senderKey && opened.signed && opened.payload.from === sender && (!pinned || pinned === senderKey.fingerprint));
      if (verified && sender && senderKey) {
        this.pin(sender, senderKey.fingerprint);
      }
      return { body: opened.payload.body, e2e: { state: 'decrypted', verified, warning: verified || !sender ? undefined : 'The sender of this message could not be verified.' } };
    }
    catch {
      return { body: 'Encrypted message that could not be decrypted with your key.', e2e: { state: 'failed', verified: false } };
    }
  }

  async openChat(messages: MessengerMessage[], otherUserId: string): Promise<MessengerMessage[]> {
    const other = this.chatAddresses.get(otherUserId) ?? null;
    const opened: MessengerMessage[] = [];
    for (const message of messages) {
      opened.push({ ...message, ...await this.openChatBody(`chat:${message.id}`, message.body, message.direction === 'sent' ? this.mailboxAddress() || null : other) });
    }
    return opened;
  }

  async openChatPreviews(conversations: MessengerConversation[]): Promise<MessengerConversation[]> {
    this.rememberChatUsers(conversations.map((conversation) => conversation.other_user));
    const opened: MessengerConversation[] = [];
    for (const conversation of conversations) {
      opened.push({ ...conversation, last_message: (await this.openChatBody(`chat-preview:${conversation.id}`, conversation.last_message, null)).body });
    }
    return opened;
  }

  private trailerHtml(trailer: string): string {
    const escaped = trailer.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return trailer ? `<hr><pre>${escaped}</pre>` : '';
  }

  private mapAttachments(attachments: Attachment[], entries: E2eAttachmentEntry[]): Attachment[] {
    const byFile = new Map(entries.map((entry) => [entry.file, entry]));
    return attachments.map((attachment) => {
      const entry = byFile.get(attachment.original_filename);
      if (!entry) {
        return attachment;
      }
      this.attachmentIndex.set(attachment.id, entry);
      return { ...attachment, original_filename: entry.name, content_type: entry.type, size: entry.size };
    });
  }

  private async openOne<M extends MessageBase>(message: M, senders: Map<string, E2eResolvedKey | null>): Promise<M> {
    if (!this.privateKey) {
      return { ...message, body: E2E_LOCKED_TEXT, body_html: null, e2e: { state: 'locked', verified: false } };
    }

    try {
      const { armored, trailer } = splitE2eBody(message.body);
      const sender = message.sender_address.trim().toLowerCase();
      const senderKey = senders.get(sender) ?? null;
      let opened = this.openedCache.get(message.id);
      if (opened?.armored !== armored) {
        opened = { armored, ...await openEnvelope(armored, this.privateKey, senderKey?.key ?? null) };
        this.openedCache.set(message.id, opened);
      }

      const { payload, signed } = opened;
      const pinned = this.pins()[sender];
      const keyChanged = Boolean(senderKey && pinned && pinned !== senderKey.fingerprint);
      const verified = signed && !keyChanged && payload.from === sender;
      if (verified && senderKey) {
        this.pin(sender, senderKey.fingerprint);
      }

      const info: E2eMessageInfo = { state: 'decrypted', verified, warning: verified || message.folder === 'drafts' ? undefined : keyChanged ? 'The sender’s encryption key has changed since you last heard from them.' : 'The sender of this message could not be verified.' };
      return { ...message, subject: payload.subject || message.subject, body: trailer ? `${payload.body}\n\n${trailer}` : payload.body, body_html: payload.body_html ? payload.body_html + this.trailerHtml(trailer) : null, attachments: this.mapAttachments(message.attachments, payload.attachments ?? []), e2e: info };
    }
    catch {
      return { ...message, body: E2E_FAILED_TEXT, body_html: null, e2e: { state: 'failed', verified: false } };
    }
  }

  private isMessage(value: unknown): value is MessageBase {
    return typeof value === 'object' && value !== null && typeof (value as MessageBase).body === 'string' && typeof (value as MessageBase).sender_address === 'string';
  }

  private async openAll<T>(value: T): Promise<T> {
    const candidates = (Array.isArray(value) ? value : [value]).filter((item): item is MessageBase => this.isMessage(item) && isE2eBody(item.body));
    if (candidates.length === 0) {
      return value;
    }

    await this.ensureLoaded();
    let senders = new Map<string, E2eResolvedKey | null>();
    if (this.privateKey) {
      try {
        senders = await this.resolveKeys(candidates.map((message) => message.sender_address.trim().toLowerCase()));
      }
      catch {
        senders = new Map();
      }
    }

    const opened = new Map<MessageBase, MessageBase>();
    for (const message of candidates) {
      opened.set(message, await this.openOne(message, senders));
    }
    return (Array.isArray(value) ? value.map((item) => opened.get(item as MessageBase) ?? item) : opened.get(value as MessageBase) ?? value) as T;
  }

  open<T>(): OperatorFunction<T, T> {
    return (source: Observable<T>) => source.pipe(switchMap((value) => from(this.openAll(value))));
  }
}
