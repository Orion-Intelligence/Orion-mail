import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { defer, finalize } from 'rxjs';

import { RequestProgressService, SKIP_REQUEST_PROGRESS } from '../request-progress';

export const requestProgressInterceptor: HttpInterceptorFn = (request, next) => {
  if (request.context.get(SKIP_REQUEST_PROGRESS)) {
    return next(request);
  }

  const progress = inject(RequestProgressService);
  return defer(() => {
    progress.start();
    return next(request);
  }).pipe(finalize(() => progress.finish()));
};
