import { Injectable, signal } from '@angular/core';

import { SYSTEM_SEARCH_SCOPES } from '../shared/constants/search.constants';
import { SearchScope, SystemSearchScope } from '../shared/model/search.model';

export function normalizeSearchScope(value: string | null | undefined): SearchScope {
  if (value?.startsWith('label:') && value.length > 'label:'.length) {
    return value as SearchScope;
  }
  return SYSTEM_SEARCH_SCOPES.has(value as SystemSearchScope) ? value as SystemSearchScope : 'all';
}

export function searchScopeParameters(scope: SearchScope): { scope: SystemSearchScope | 'label'; labelId?: string } {
  if (scope.startsWith('label:')) {
    return { scope: 'label', labelId: scope.slice('label:'.length) };
  }
  return { scope: scope as SystemSearchScope };
}

@Injectable({
  providedIn: 'root',
})
export class SearchService {
  readonly searchTerm = signal('');
  readonly searchScope = signal<SearchScope>('all');
}
