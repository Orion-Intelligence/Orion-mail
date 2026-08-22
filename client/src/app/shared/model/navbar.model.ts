import { IconName } from './icon.model';
import { SearchScope } from './search.model';

export interface SearchScopeOption {
  value: SearchScope;
  label: string;
  icon: IconName;
}

export interface SearchHintRequest {
  query: string;
  scope: SearchScope;
}
