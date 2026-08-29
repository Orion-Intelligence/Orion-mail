import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import { AddressHint } from '../shared/model/address-book.model';

@Injectable({
  providedIn: 'root',
})
export class AddressBookService {
  private readonly baseUrl = `${environment.apiBaseUrl}/address-book`;

  constructor(private readonly http: HttpClient) {}

  getHints(query: string, limit = 8): Observable<AddressHint[]> {
    return this.http.post<AddressHint[]>(`${this.baseUrl}/hints`, { query, limit });
  }
}
