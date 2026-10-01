import { Component, OnInit, inject, output, signal, } from '@angular/core';
import { FileService, } from '../../../services/file';
import { OrionFile, OrionLinkedFile, } from '../../model/file.model';


@Component({
  selector: 'app-file-picker',
  standalone: true,
  templateUrl: './file-picker.html',
})
export class FilePicker implements OnInit {
  private readonly fileService =
    inject(FileService);

  selected = output<OrionLinkedFile>();
  closed = output<void>();
  files = signal<OrionFile[]>([]);
  uploading = signal(false);
  error = signal('');

  ngOnInit(): void {
    this.loadFiles();
  }

  private loadFiles(): void {
    this.fileService
      .getMyFiles()
      .subscribe({
        next: (files) => {
          this.files.set(files);
        },

        error: () => {
          this.error.set('Could not load your files.',);
        },
      });
  }

  canInsert(file: OrionFile,): boolean {
    return Boolean(this.fileService.getSessionKey(file.public_id,),);
  }

  insertExisting(file: OrionFile,): void {
    const linked =
      this.fileService.restoreLinkedFile(file,);

    if (!linked) {
      this.error.set('The decryption key for this file is not available in this browser session.',);

      return;
    }

    this.selected.emit(linked);
  }

  async uploadSelected(event: Event,): Promise<void> {
    const input =
      event.target as HTMLInputElement;

    const selectedFiles = Array.from(input.files ?? [],);

    input.value = '';

    if (selectedFiles.length === 0) {
      return;
    }

    this.error.set('');
    this.uploading.set(true);

    try {
      for (const file of selectedFiles) {
        const uploaded =
          await this.fileService.uploadFile(file,);

        this.files.update((files) => [
          uploaded,
          ...files.filter((item) =>
            item.id !== uploaded.id,),
        ],);

        this.selected.emit(uploaded);
      }
    }
    catch {
      this.error.set('File could not be encrypted or uploaded.',);
    }
    finally {
      this.uploading.set(false);
    }
  }

  formatSize(size: number,): string {
    if (size < 1024) {
      return `${size} B`;
    }

    if (size < 1024 * 1024) {
      return `${(
        size / 1024
      ).toFixed(0)} KB`;
    }

    return `${(
      size / (1024 * 1024)
    ).toFixed(1)} MB`;
  }

  close(): void {
    this.closed.emit();
  }
}