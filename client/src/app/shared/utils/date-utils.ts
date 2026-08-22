export function parseUtcDate(date: Date | string | null | undefined): Date | null {
  if (!date) {
    return null;
  }

  if (date instanceof Date) {
    return date;
  }

  const hasTimezone = date.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(date);

  return new Date(hasTimezone ? date : `${date}Z`);
}

export function formatMailDate(date: Date | string | null | undefined): string {
  const parsedDate = parseUtcDate(date);

  if (!parsedDate) {
    return '';
  }

  const now = new Date();

  const isToday =
    parsedDate.getFullYear() === now.getFullYear() &&
    parsedDate.getMonth() === now.getMonth() &&
    parsedDate.getDate() === now.getDate();

  if (isToday) {
    return parsedDate.toLocaleTimeString(undefined, {
      hour: 'numeric',
      minute: '2-digit',
    });
  }

  const sameYear = parsedDate.getFullYear() === now.getFullYear();

  if (sameYear) {
    return parsedDate.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
    });
  }

  return parsedDate.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

export function formatFullMailDate(date: Date | string | null | undefined): string {
  const parsedDate = parseUtcDate(date);

  if (!parsedDate) {
    return '';
  }

  return parsedDate.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}
