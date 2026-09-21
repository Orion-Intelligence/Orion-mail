import { HttpErrorResponse } from '@angular/common/http';

import { ValidationDetailEntry } from '../model/http-error.model';

function firstValidationMessage(detail: ValidationDetailEntry[]): string {
  const message = detail.find((entry) => typeof entry?.msg === 'string')?.msg;
  return message ? message.replace(/^(Value error|Assertion failed),?\s*/i, '') : '';
}

function parseTextBody(body: unknown): { detail?: unknown } | null | undefined {
  if (typeof body !== 'string' || !body.trim().startsWith('{')) {
    return body as { detail?: unknown } | null | undefined;
  }
  try {
    return JSON.parse(body);
  }
  catch {
    return null;
  }
}

export function extractErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof HttpErrorResponse)) {
    return fallback;
  }

  if (error.status === 0) {
    // noinspection HttpUrlsUsage -- local development address
    return 'Could not reach the mail server. Make sure Orion Mail and its backend are running, then open http://mail.localhost:4200.';
  }

  const body = parseTextBody(error.error);
  const detail = body?.detail;

  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail)) {
    const message = firstValidationMessage(detail);
    if (message) {
      return message;
    }
  }

  if (typeof error.error === 'string' && !/^\s*[<{]/.test(error.error)) {
    return error.error;
  }

  if (error.status >= 500) {
    return 'The mail server had a problem. Please try again in a moment.';
  }

  return fallback;
}
