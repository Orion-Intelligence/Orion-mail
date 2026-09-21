import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, from, switchMap, tap } from 'rxjs';
import { environment } from '../../environments/environment';
import { MessengerConversation, MessengerMessage, MessengerUser, SendMessengerMessageRequest } from '../shared/model/message.model';
import { E2eService } from './e2e';

@Injectable({
  providedIn: 'root',
})
export class MessengerService {
  private readonly apiBaseUrl = environment.apiBaseUrl;
  private readonly baseUrl = `${this.apiBaseUrl}/messenger-api`;
  private readonly e2e = inject(E2eService);

  constructor(private readonly http: HttpClient) { }

  getUsers(query = '', limit = 100, offset = 0): Observable<MessengerUser[]> {
    let params = new HttpParams()
      .set('limit', limit)
      .set('offset', offset);

    if (query.trim()) {
      params = params.set('query', query.trim());
    }

    return this.http.get<MessengerUser[]>(`${this.baseUrl}/users`, { params }).pipe(tap((users) => {
      this.e2e.rememberChatUsers(users);
    }));
  }

  getConversations(): Observable<MessengerConversation[]> {
    return this.http.get<MessengerConversation[]>(`${this.baseUrl}/conversations`).pipe(switchMap((conversations) => from(this.e2e.openChatPreviews(conversations))));
  }

  getMessages(otherUserId: string): Observable<MessengerMessage[]> {
    return this.http.get<MessengerMessage[]>(`${this.baseUrl}/conversations/${otherUserId}/messages`).pipe(switchMap((messages) => from(this.e2e.openChat(messages, otherUserId))));
  }

  sendMessage(data: SendMessengerMessageRequest): Observable<MessengerMessage> {
    return from(this.e2e.sealChat(data.receiver_user_id, data.body)).pipe(switchMap((body) => this.http.post<MessengerMessage>(`${this.baseUrl}/messages`, { ...data, body })),
      switchMap((message) => from(this.e2e.openChat([message], data.receiver_user_id))),
      switchMap((messages) => messages));
  }
}
