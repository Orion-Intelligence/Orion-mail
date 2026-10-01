import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, firstValueFrom } from 'rxjs';
import { OrionFile, OrionLinkedFile, PublicFileMetadata } from '../shared/model/file.model';
import { encryptFile } from '../shared/utils/file-crypto';


@Injectable({
  providedIn: 'root',
})
export class FileService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = '/api/files';
  private readonly sessionPrefix = 'orion-shared-file-key:';

  private rememberKey( publicId: string, key: string, ): void {
    sessionStorage.setItem(`${this.sessionPrefix}${publicId}`,
      key,);
  }

  getSessionKey(publicId: string,): string | null {
    return sessionStorage.getItem(`${this.sessionPrefix}${publicId}`,);
  }

  buildSecureUrl( publicId: string, key: string, ): string {
    return (
      `${window.location.origin}/file/` +
          `${encodeURIComponent(publicId)}` +
          `#${encodeURIComponent(key)}`
    );
  }

  restoreLinkedFile(file: OrionFile,): OrionLinkedFile | null {
    const key = this.getSessionKey(file.public_id,);

    if (!key) {
      return null;
    }

    return {
      ...file,
      key,
      secure_url: this.buildSecureUrl(file.public_id,
        key,),
    };
  }

  async uploadFile(file: File,): Promise<OrionLinkedFile> {
    const encrypted = await encryptFile(file,);

    const data = new FormData();

    data.append('encrypted_file',
      encrypted.encrypted,
      'encrypted.orion',);

    data.append('original_filename',
      file.name,);

    data.append('original_size',
      String(file.size),);

    data.append('content_type',
      file.type ||
          'application/octet-stream',);

    data.append('iv',
      encrypted.iv,);

    const response = await firstValueFrom(this.http.post<OrionFile>(this.apiUrl,
      data,),);

    this.rememberKey(response.public_id,
      encrypted.key,);

    return {
      ...response,

      key: encrypted.key,

      secure_url: this.buildSecureUrl(response.public_id,
        encrypted.key,),
    };
  }

  getMyFiles(): Observable<OrionFile[]> {
    return this.http.get<OrionFile[]>(this.apiUrl,);
  }

  getPublicFile(publicId: string,): Observable<PublicFileMetadata> {
    return this.http.get<PublicFileMetadata>(`${this.apiUrl}/public/${encodeURIComponent(publicId)}`,);
  }

  deleteFile(id: string,): Observable<{ message: string }> {
    return this.http.delete<{
          message: string;
      }>(`${this.apiUrl}/${encodeURIComponent(id)}`,);
  }

  async fetchEncryptedBytes(metadata: PublicFileMetadata,): Promise<ArrayBuffer> {
    try {
      const response = await fetch(metadata.provider_direct_url,
        {
          method: 'GET',
          credentials: 'omit',
        },);

      const contentType =
              response.headers
                .get('content-type')
                ?.toLowerCase() ?? '';

      if (
        response.ok &&
              !contentType.includes('text/html')
      ) {
        const buffer =
                  await response.arrayBuffer();

        if (
          buffer.byteLength ===
                  metadata.encrypted_size
        ) {
          return buffer;
        }
      }
    }
    catch {
      // Fall back to Orion ciphertext proxy.
    }

    return firstValueFrom(this.http.get(metadata.content_url,
      {
        responseType: 'arraybuffer',
      },),);
  }
}