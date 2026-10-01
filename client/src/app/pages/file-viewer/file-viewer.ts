import { Component, OnDestroy, OnInit, inject, signal, } from '@angular/core';
import { ActivatedRoute, } from '@angular/router';
import { DomSanitizer, SafeResourceUrl, } from '@angular/platform-browser';
import { firstValueFrom, } from 'rxjs';
import { FileService, } from '../../services/file';
import { decryptFile, } from '../../shared/utils/file-crypto';
import { PublicFileMetadata, } from '../../shared/model/file.model';


type PreviewKind =
  | 'image'
  | 'pdf'
  | 'text'
  | 'download';


@Component({
  selector: 'app-file-viewer',
  standalone: true,
  templateUrl: './file-viewer.html',
})
export class FileViewer
implements OnInit, OnDestroy {
  private readonly route =
    inject(ActivatedRoute);
  private readonly fileService =
    inject(FileService);
  private readonly sanitizer =
    inject(DomSanitizer);
  private decryptedBlob: Blob | null = null;

  loading = signal(true);
  error = signal('');
  metadata =
    signal<PublicFileMetadata | null>(null,);
  previewKind =
    signal<PreviewKind>('download');
  previewUrl =
    signal<string | null>(null);
  safePdfUrl =
    signal<SafeResourceUrl | null>(null,);
  textPreview = signal('');

  async ngOnInit(): Promise<void> {
    const publicId =
      this.route.snapshot.paramMap.get('publicId',);

    const hash =
      window.location.hash.slice(1);

    const key = hash
      ? decodeURIComponent(hash)
      : '';

    if (!publicId || !key) {
      this.error.set('This secure file link is incomplete.',);

      this.loading.set(false);

      return;
    }

    try {
      const metadata =
        await firstValueFrom(this.fileService.getPublicFile(publicId,),);

      this.metadata.set(metadata);

      const ciphertext =
        await this.fileService
          .fetchEncryptedBytes(metadata);

      const plaintext =
        await decryptFile(ciphertext,
          key,
          metadata.iv,);

      this.decryptedBlob = new Blob([plaintext],
        {
          type:
            metadata.content_type ||
            'application/octet-stream',
        },);

      const url =
        URL.createObjectURL(this.decryptedBlob,);

      this.previewUrl.set(url);

      if (
        metadata.content_type.startsWith('image/',) &&
        metadata.content_type !==
        'image/svg+xml'
      ) {
        this.previewKind.set('image');
      }
      else if (
        metadata.content_type ===
        'application/pdf'
      ) {
        this.previewKind.set('pdf');

        this.safePdfUrl.set(this.sanitizer
          .bypassSecurityTrustResourceUrl(url,),);
      }
      else if (
        metadata.content_type.startsWith('text/',) &&
        metadata.original_size <=
        2 * 1024 * 1024
      ) {
        this.previewKind.set('text');

        this.textPreview.set(await this.decryptedBlob.text(),);
      }
      else {
        this.previewKind.set('download',);
      }
    }
    catch {
      this.error.set('The file could not be decrypted. The link may be invalid or the stored file may no longer exist.',);
    }
    finally {
      this.loading.set(false);
    }
  }

  download(): void {
    const metadata = this.metadata();
    const url = this.previewUrl();

    if (!metadata || !url) {
      return;
    }

    const anchor =
      document.createElement('a');

    anchor.href = url;

    anchor.download =
      metadata.original_filename;

    anchor.click();
  }

  ngOnDestroy(): void {
    const url = this.previewUrl();

    if (url) {
      URL.revokeObjectURL(url);
    }
  }
}