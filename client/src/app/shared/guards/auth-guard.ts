import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, map, of } from 'rxjs';

import { AuthService } from '../../services/auth';

function redirectToOrion(authService: AuthService, returnTo: string): false {
  authService.startOrionLogin(returnTo);
  return false;
}

export const authGuard: CanActivateFn = (_route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  return authService.me().pipe(map((user) => user.mailbox_configured
    ? true
    : router.createUrlTree(['/configure-email'])), catchError(() => of(redirectToOrion(authService, state.url))));
};

export const mailboxSetupGuard: CanActivateFn = (_route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  return authService.me().pipe(map((user) => user.mailbox_configured
    ? router.createUrlTree(['/inbox'])
    : true), catchError(() => of(redirectToOrion(authService, state.url))));
};
