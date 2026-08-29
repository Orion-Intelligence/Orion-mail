import { Component, computed, DestroyRef, ElementRef, HostListener, inject, OnInit, signal, ViewChild, WritableSignal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { Subject, catchError, debounceTime, distinctUntilChanged, filter, finalize, of, switchMap } from 'rxjs';

import { Compose } from '../../../pages/compose/compose';
import { AuthService } from '../../../services/auth';
import { ComposeService } from '../../../services/compose';
import { MailPollService } from '../../../services/mail-poll';
import { LabelService, labelColorClass } from '../../../services/label';
import { MessageService } from '../../../services/message';
import { Mailbox, MessageDetailResponse } from '../../model/message.model';
import { SearchService, normalizeSearchScope, searchScopeParameters } from '../../../services/search';
import { SearchScope } from '../../model/search.model';
import { ThemeService } from '../../../services/theme';
import { Icon } from '../../icons/icon/icon';
import { LabelDialog } from '../label-dialog/label-dialog';
import { GO_TO_ROUTES, MAILBOX_ROUTE_SEGMENTS, MESSAGE_FOLDER_NAMES, MORE_ROUTES, MORE_STORAGE_KEY, SEARCHABLE_ROUTES, SEARCH_SCOPE_OPTIONS } from '../../constants/navbar.constants';
import { SearchHintRequest } from '../../model/navbar.model';

function readMoreState(): boolean {
  try {
    return window.localStorage.getItem(MORE_STORAGE_KEY) === 'open';
  }
  catch {
    return false;
  }
}

function writeMoreState(open: boolean): void {
  try {
    window.localStorage.setItem(MORE_STORAGE_KEY, open ? 'open' : 'closed');
  }
  catch {
    return;
  }
}

@Component({
  selector: 'app-navbar',
  imports: [RouterLink, RouterLinkActive, RouterOutlet, Icon, LabelDialog, Compose],
  host: { class: 'block h-dvh bg-transparent text-ink' },
  templateUrl: './navbar.html',
})
export class Navbar implements OnInit {
  private readonly authService = inject(AuthService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly searchHintRequests = new Subject<SearchHintRequest>();
  private pendingGoTo = false;
  private goToTimer?: ReturnType<typeof setTimeout>;

  mailbox = signal<Mailbox | null>(null);
  profileMenuOpen = signal(false);
  searchSuggestionsOpen = signal(false);
  searchScopeMenuOpen = signal(false);
  searchHintsLoading = signal(false);
  searchHints = signal<MessageDetailResponse[]>([]);
  activeSearchOption = signal(-1);
  sidebarCollapsed = signal(false);
  mobileNavOpen = signal(false);
  moreOpen = signal(readMoreState());
  readonly searchScopeOptions = SEARCH_SCOPE_OPTIONS;
  readonly labelColorClass = labelColorClass;
  user = this.authService.currentUser;
  initial = computed(() => (
    this.user()?.username
    || this.user()?.email
    || this.mailbox()?.mailbox_address
    || 'o'
  ).charAt(0).toUpperCase());
  searchTerm: WritableSignal<string>;
  searchScope: WritableSignal<SearchScope>;
  @ViewChild('searchInput') searchInput?: ElementRef<HTMLInputElement>;
  @ViewChild('searchWrapper') searchWrapper?: ElementRef<HTMLElement>;
  @ViewChild('profileButton') profileButton?: ElementRef<HTMLButtonElement>;
  @ViewChild('profileWrapper') profileWrapper?: ElementRef<HTMLElement>;

  constructor(public readonly messageService: MessageService, private readonly searchService: SearchService, public readonly labelService: LabelService, public readonly themeService: ThemeService, public readonly composeService: ComposeService, public readonly mailPollService: MailPollService, public readonly router: Router) {
    this.searchTerm = this.searchService.searchTerm;
    this.searchScope = this.searchService.searchScope;
  }

  ngOnInit(): void {
    this.initializeSearch();
    this.syncSearchStateFromUrl(this.router.url);
    this.authService.me().subscribe({ error: () => undefined });
    this.messageService.getMyMailbox().subscribe({
      next: (mailbox) => {
        this.mailbox.set(mailbox);
      },

      error: () => {
        this.mailbox.set(null);
      },
    });
    this.labelService.loadLabels().subscribe({ error: () => undefined });
    this.messageService.refreshFolderCounts();
    this.messageService.refreshStorageStatus();
    this.mailPollService.start();
    this.mailPollService.requestNotificationPermission();
    if (MORE_ROUTES.some((route) => this.router.url.startsWith(route))) {
      this.moreOpen.set(true);
    }
  }

  showSearch(): boolean {
    return SEARCHABLE_ROUTES.some((route) => this.router.url.startsWith(route));
  }

  onSearch(event: Event): void {
    const /*safe*/ input = event.target as HTMLInputElement;
    this.searchTerm.set(input.value);
    this.activeSearchOption.set(-1);
    this.searchScopeMenuOpen.set(false);

    if (!input.value.trim()) {
      this.searchHints.set([]);
      this.searchSuggestionsOpen.set(false);
      return;
    }

    this.searchSuggestionsOpen.set(true);
    this.queueSearchHints();
  }

  onSearchFocus(): void {
    this.profileMenuOpen.set(false);
    if (!this.searchTerm().trim()) {
      return;
    }
    this.searchSuggestionsOpen.set(true);
    this.queueSearchHints();
  }

  onSearchKeydown(event: KeyboardEvent): void {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      this.moveSearchSelection(event.key === 'ArrowDown' ? 1 : -1);
      return;
    }

    if (event.key === 'Enter') {
      event.preventDefault();
      const activeOption = this.activeSearchOption();
      if (this.searchSuggestionsOpen() && activeOption > 0) {
        const hint = this.searchHints()[activeOption - 1];
        if (hint) {
          this.openSearchHint(hint);
          return;
        }
      }
      this.submitSearch();
      return;
    }

    if (event.key === 'Escape') {
      event.preventDefault();
      this.closeSearchMenus();
    }
  }

  clearSearch(): void {
    const leaveSearchResults = this.router.url.startsWith('/search');
    this.resetSearchState();
    if (leaveSearchResults) {
      void this.router.navigate(['/inbox']);
      return;
    }
    setTimeout(() => this.searchInput?.nativeElement.focus(), 0);
  }

  submitSearch(): void {
    const query = this.searchTerm().trim();
    if (!query) {
      return;
    }

    this.searchTerm.set(query);
    this.closeSearchMenus();
    void this.router.navigate(['/search'], { queryParams: { q: query, scope: this.searchScope() } });
  }

  toggleSearchScopeMenu(): void {
    this.profileMenuOpen.set(false);
    this.searchSuggestionsOpen.set(false);
    this.activeSearchOption.set(-1);
    this.searchScopeMenuOpen.update((open) => !open);
  }

  selectSearchScope(scope: string): void {
    this.searchScope.set(normalizeSearchScope(scope));
    this.searchScopeMenuOpen.set(false);
    this.activeSearchOption.set(-1);

    if (!this.searchTerm().trim()) {
      this.searchInput?.nativeElement.focus();
      return;
    }

    if (this.router.url.startsWith('/search')) {
      this.submitSearch();
      return;
    }

    this.searchSuggestionsOpen.set(true);
    this.queueSearchHints();
    this.searchInput?.nativeElement.focus();
  }

  searchScopeSelected(scope: string): boolean {
    return this.searchScope() === scope;
  }

  searchScopeLabel(): string {
    const scope = this.searchScope();
    if (scope.startsWith('label:')) {
      const labelId = scope.slice('label:'.length);
      return this.labelService.labels().find((label) => label.id === labelId)?.name ?? 'Label';
    }
    return SEARCH_SCOPE_OPTIONS.find((option) => option.value === scope)?.label ?? 'All mail';
  }

  searchPlaceholder(): string {
    return this.searchScope() === 'all' ? 'Search mail' : `Search in ${this.searchScopeLabel()}`;
  }

  activateSearchOption(index: number): void {
    this.activeSearchOption.set(index);
  }

  searchOptionId(index: number): string {
    return `mail-search-option-${index}`;
  }

  openSearchHint(message: MessageDetailResponse): void {
    this.closeSearchMenus();
    if (message.folder === 'drafts') {
      this.composeService.openDraft(message.id);
      return;
    }
    void this.router.navigate(['/message', message.id], { queryParams: { from: 'search', q: this.searchTerm().trim(), scope: this.searchScope() } });
  }

  searchHintCorrespondent(message: MessageDetailResponse): string {
    const address = message.direction === 'outgoing' ? message.receiver_address : message.sender_address;
    return address.split('@')[0] || address;
  }

  searchHintFolder(message: MessageDetailResponse): string {
    return MESSAGE_FOLDER_NAMES.get(message.folder) ?? message.folder;
  }

  navigationExpanded(): boolean {
    return window.matchMedia('(max-width: 720px)').matches ? this.mobileNavOpen() : !this.sidebarCollapsed();
  }

  toggleNavigation(): void {
    if (window.matchMedia('(max-width: 720px)').matches) {
      this.mobileNavOpen.update((open) => !open);
      return;
    }

    this.sidebarCollapsed.update((collapsed) => !collapsed);
  }

  closeMobileNavigation(): void {
    this.mobileNavOpen.set(false);
  }

  onSidebarNavigation(): void {
    this.resetSearchState();
    this.closeMobileNavigation();
  }

  toggleMore(): void {
    this.moreOpen.update((open) => !open);
    writeMoreState(this.moreOpen());
  }

  toggleProfileMenu(): void {
    this.closeSearchMenus();
    this.profileMenuOpen.update((open) => !open);
  }

  toggleTheme(): void {
    this.themeService.setTheme(this.themeService.theme() === 'dark' ? 'light' : 'dark');
  }

  goToOrionAccount(): void {
    this.profileMenuOpen.set(false);
    const accountUrl = this.user()?.orion_account_url;
    if (accountUrl) {
      window.location.assign(accountUrl);
    }
  }

  goToSettings(): void {
    this.profileMenuOpen.set(false);
    this.closeMobileNavigation();
    void this.router.navigate(['/settings']);
  }

  goToLabelManager(): void {
    this.onSidebarNavigation();
    void this.router.navigate(['/settings/labels']);
  }

  openCompose(): void {
    this.closeMobileNavigation();
    this.composeService.openNew();
  }

  openCreateLabel(): void {
    this.closeMobileNavigation();
    this.labelService.openCreateDialog();
  }

  logout(): void {
    this.profileMenuOpen.set(false);

    this.authService
      .logout()
      .subscribe({
        next: (response) => {
          window.location.assign(response.redirect_url);
        },
        error: () => {
          window.location.assign('/');
        },
      });
  }

  private initializeSearch(): void {
    this.searchHintRequests.pipe(debounceTime(160),
      distinctUntilChanged((previous, current) => previous.query === current.query && previous.scope === current.scope),
      switchMap((request) => {
        const query = request.query.trim();
        if (!query) {
          return of([] as MessageDetailResponse[]);
        }
        const parameters = searchScopeParameters(request.scope);
        this.searchHintsLoading.set(true);
        return this.messageService.searchMessages(query, parameters.scope, parameters.labelId, 6).pipe(catchError(() => of([] as MessageDetailResponse[])),
          finalize(() => {
            this.searchHintsLoading.set(false);
          }),);
      }),
      takeUntilDestroyed(this.destroyRef),).subscribe((hints) => {
      this.searchHints.set(hints.map((message) => ({ ...message, label_ids: message.label_ids })));
      this.activeSearchOption.update((index) => index < 0 ? -1 : Math.min(index, hints.length));
    });

    this.router.events.pipe(filter((event): event is NavigationEnd => event instanceof NavigationEnd),
      takeUntilDestroyed(this.destroyRef),).subscribe((event) => {
      this.syncSearchStateFromUrl(event.urlAfterRedirects);
    });
  }

  private syncSearchStateFromUrl(url: string): void {
    const urlTree = this.router.parseUrl(url);
    const firstSegment = urlTree.root.children['primary']?.segments[0]?.path;
    if (firstSegment !== 'search') {
      if (firstSegment && MAILBOX_ROUTE_SEGMENTS.has(firstSegment)) {
        this.resetSearchState();
      }
      return;
    }

    this.searchTerm.set(String(urlTree.queryParams['q'] ?? ''));
    this.searchScope.set(normalizeSearchScope(String(urlTree.queryParams['scope'] ?? 'all')));
  }

  private queueSearchHints(): void {
    this.searchHintRequests.next({ query: this.searchTerm(), scope: this.searchScope() });
  }

  private resetSearchState(): void {
    this.searchTerm.set('');
    this.searchScope.set('all');
    this.searchHints.set([]);
    this.searchHintsLoading.set(false);
    this.closeSearchMenus();
    this.searchHintRequests.next({ query: '', scope: 'all' });
  }

  private moveSearchSelection(delta: number): void {
    if (!this.searchTerm().trim()) {
      return;
    }
    this.searchScopeMenuOpen.set(false);
    this.searchSuggestionsOpen.set(true);
    const optionCount = this.searchHints().length + 1;
    const current = this.activeSearchOption();
    const next = current < 0 ? (delta > 0 ? 0 : optionCount - 1) : (current + delta + optionCount) % optionCount;
    this.activeSearchOption.set(next);
    setTimeout(() => document.getElementById(this.searchOptionId(next))?.scrollIntoView({ block: 'nearest' }), 0);
  }

  private closeSearchMenus(): void {
    this.searchSuggestionsOpen.set(false);
    this.searchScopeMenuOpen.set(false);
    this.activeSearchOption.set(-1);
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    const target = event.target as Node;
    if ((this.searchSuggestionsOpen() || this.searchScopeMenuOpen()) && !this.searchWrapper?.nativeElement.contains(target)) {
      this.closeSearchMenus();
    }
    if (this.profileMenuOpen() && !this.profileWrapper?.nativeElement.contains(target)) {
      this.profileMenuOpen.set(false);
    }
  }

  clearPendingGoTo(): void {
    this.pendingGoTo = false;
  }

    @HostListener('document:keydown', ['$event'])
  onGlobalKeydown(event: KeyboardEvent): void {
    if (event.metaKey || event.ctrlKey || event.altKey) {
      return;
    }

    const /*safe*/ target = event.target as HTMLElement | null;
    const tagName = target?.tagName.toLowerCase() ?? '';
    if (tagName === 'input' || tagName === 'textarea' || tagName === 'select' || target?.isContentEditable) {
      return;
    }

    if (this.pendingGoTo) {
      clearTimeout(this.goToTimer);
      this.pendingGoTo = false;
      const destination = GO_TO_ROUTES[event.key.toLowerCase()];
      if (destination) {
        event.preventDefault();
        void this.router.navigate([destination]);
      }
      return;
    }

    if (event.key === 'g') {
      this.pendingGoTo = true;
      this.goToTimer = setTimeout(() => {
        this.clearPendingGoTo();
      }, 1500);
      return;
    }

    if (event.key === 'c') {
      event.preventDefault();
      this.openCompose();
      return;
    }

    if (event.key === '/') {
      event.preventDefault();
      this.searchInput?.nativeElement.focus();
    }
  }

  @HostListener('document:keydown.escape')
    closeMenusOnEscape(): void {
      if (this.searchSuggestionsOpen() || this.searchScopeMenuOpen()) {
        this.closeSearchMenus();
      }
      if (this.profileMenuOpen()) {
        this.profileMenuOpen.set(false);
        setTimeout(() => this.profileButton?.nativeElement.focus(), 0);
      }
    }

  @HostListener('document:keydown', ['$event'])
  focusSearchOnShortcut(event: KeyboardEvent): void {
    if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey || !this.showSearch()) {
      return;
    }

    const /*safe*/ target = event.target as HTMLElement | null;
    if (target?.isContentEditable || target?.closest('input, textarea, select, [role="textbox"]')) {
      return;
    }

    event.preventDefault();
    this.searchInput?.nativeElement.focus();
  }
}
