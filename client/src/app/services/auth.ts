import { HttpClient } from '@angular/common/http';
import { Injectable, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';

import { environment } from '../../environments/environment';
import { CurrentUser, LogoutResponse, UserPreferences } from '../shared/model/auth.model';

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private readonly baseUrl = `${environment.apiBaseUrl}/auth`;
  private redirecting = false;

  readonly currentUser = signal<CurrentUser | null>(null);

  constructor(private readonly http: HttpClient) {}

  me(): Observable<CurrentUser> {
    return this.http.get<CurrentUser>(`${this.baseUrl}/me`).pipe(tap((user) => {
      this.currentUser.set(user);
    }));
  }

  startOrionLogin(returnTo?: string): void {
    if (this.redirecting) {
      return;
    }
    this.redirecting = true;
    const destination = returnTo || `${window.location.pathname}${window.location.search}`;
    const params = new URLSearchParams({
      origin: window.location.origin,
      return_to: destination,
    });
    window.location.assign(`${this.baseUrl}/login?${params.toString()}`);
  }

  updatePreferences(preferences: UserPreferences): Observable<UserPreferences> {
    return this.http.put<UserPreferences>(`${this.baseUrl}/me/preferences`, preferences).pipe(tap((saved) => {
      this.currentUser.update((user) => user ? { ...user, preferences: saved } : user);
    }));
  }

  logout(): Observable<LogoutResponse> {
    return this.http.post<LogoutResponse>(`${this.baseUrl}/logout`, {}).pipe(tap(() => {
      this.currentUser.set(null);
    }));
  }
}
