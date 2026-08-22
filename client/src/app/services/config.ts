import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import { SystemConfig } from '../shared/model/config.model';

@Injectable({
  providedIn: 'root',
})
export class ConfigService {
  private readonly baseUrl = `${environment.apiBaseUrl}/system-config`;

  constructor(private readonly http: HttpClient) {}

  getSystemConfig(): Observable<SystemConfig> {
    return this.http.get<SystemConfig>(this.baseUrl);
  }

  updateSystemConfig(config: SystemConfig): Observable<SystemConfig> {
    return this.http.put<SystemConfig>(this.baseUrl, config);
  }
}
