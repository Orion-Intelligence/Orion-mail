import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import { MessengerConversation, MessengerMessage, MessengerUser, SendMessengerMessageRequest } from '../shared/model/message.model';

@Injectable({
  providedIn: 'root',
})
export class MessengerService {
  private readonly apiBaseUrl = environment.apiBaseUrl;
  private readonly baseUrl = `${this.apiBaseUrl}/messenger-api`;

  constructor(private readonly http: HttpClient) { }

  getUsers(query = '', limit = 100, offset = 0): Observable<MessengerUser[]> {
    let params = new HttpParams()
      .set('limit', limit)
      .set('offset', offset);

    if (query.trim()) {
      params = params.set('query', query.trim());
    }

    return this.http.get<MessengerUser[]>(`${this.baseUrl}/users`, { params });
  }

  getConversations(): Observable<MessengerConversation[]> {
    return this.http.get<MessengerConversation[]>(`${this.baseUrl}/conversations`);
  }

  getMessages(otherUserId: string): Observable<MessengerMessage[]> {
    return this.http.get<MessengerMessage[]>(`${this.baseUrl}/conversations/${otherUserId}/messages`);
  }

  sendMessage(data: SendMessengerMessageRequest): Observable<MessengerMessage> {
    return this.http.post<MessengerMessage>(`${this.baseUrl}/messages`, data);
  }
}
