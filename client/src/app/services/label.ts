import { HttpClient } from '@angular/common/http';
import { Injectable, signal } from '@angular/core';
import { Observable, finalize, tap } from 'rxjs';

import { environment } from '../../environments/environment';
import { LABEL_COLOR_OPTIONS } from '../shared/constants/label.constants';
import { LabelCreateRequest, LabelMessagesResponse, LabelUpdateRequest, MailLabel } from '../shared/model/label.model';

export function labelColorClass(color: string | null | undefined): string {
  return LABEL_COLOR_OPTIONS.find((option) => option.value === color?.toLowerCase())?.className ?? 'bg-label-slate';
}

@Injectable({
  providedIn: 'root',
})
export class LabelService {
  private readonly baseUrl = `${environment.apiBaseUrl}/labels`;

  readonly labels = signal<MailLabel[]>([]);
  readonly loading = signal(false);
  readonly createDialogOpen = signal(false);

  constructor(private readonly http: HttpClient) {}

  openCreateDialog(): void {
    this.createDialogOpen.set(true);
  }

  closeCreateDialog(): void {
    this.createDialogOpen.set(false);
  }

  loadLabels(): Observable<MailLabel[]> {
    this.loading.set(true);
    return this.http.get<MailLabel[]>(this.baseUrl).pipe(tap((labels) => this.labels.set(this.sortLabels(labels))),
      finalize(() => this.loading.set(false)),);
  }

  createLabel(label: LabelCreateRequest): Observable<MailLabel> {
    return this.http.post<MailLabel>(this.baseUrl, label).pipe(tap((createdLabel) => this.labels.update((labels) => this.sortLabels([...labels, createdLabel]))),);
  }

  updateLabel(labelId: string, changes: LabelUpdateRequest): Observable<MailLabel> {
    return this.http.patch<MailLabel>(`${this.baseUrl}/${labelId}`, changes).pipe(tap((updatedLabel) => this.labels.update((labels) => this.sortLabels(labels.map((label) => (label.id === labelId ? { ...updatedLabel, message_count: label.message_count } : label))))),);
  }

  deleteLabel(labelId: string): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.baseUrl}/${labelId}`).pipe(tap(() => this.labels.update((labels) => labels.filter((label) => label.id !== labelId))),);
  }

  getLabelMessages(labelId: string): Observable<LabelMessagesResponse> {
    return this.http.get<LabelMessagesResponse>(`${this.baseUrl}/${labelId}/messages`).pipe(tap((response) => this.labels.update((labels) => labels.map((label) => (label.id === labelId ? response.label : label)))),);
  }

  adjustMessageCount(labelIds: string[], delta: number): void {
    const affected = new Set(labelIds);
    this.labels.update((labels) => labels.map((label) => affected.has(label.id) ? { ...label, message_count: Math.max(0, label.message_count + delta) } : label));
  }

  private sortLabels(labels: MailLabel[]): MailLabel[] {
    return [...labels].sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }));
  }
}
