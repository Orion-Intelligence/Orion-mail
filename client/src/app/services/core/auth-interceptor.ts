import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';

import { AuthService } from '../auth';
import { AUTH_CONTROL_PATHS } from '../../shared/constants/auth.constants';

export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const authService = inject(AuthService);
  const secured = request.clone({
    withCredentials: true,
    setHeaders: { 'X-Requested-With': 'XMLHttpRequest' },
  });

  return next(secured).pipe(catchError((error: HttpErrorResponse) => {
    if ([502, 503, 504].includes(error.status) && request.url.startsWith('/api/auth/')) {
      authService.showMaintenance();
    }
    if (error.status === 401 && !AUTH_CONTROL_PATHS.some((path) => request.url.endsWith(path))) {
      authService.startOrionLogin();
    }
    return throwError(() => error);
  }));
};
