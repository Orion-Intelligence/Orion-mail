import { Injectable, computed, effect, inject } from '@angular/core';

import { AuthService } from './auth';

@Injectable({
  providedIn: 'root',
})
export class BrandService {
  private readonly authService = inject(AuthService);

  readonly name = computed(() => this.authService.currentUser()?.brand?.name?.trim() || 'Orion Mail');
  readonly logoLight = computed(() => this.authService.currentUser()?.brand?.logo_light?.trim() || 'assets/images/logo-wide.svg');
  readonly logoDark = computed(() => this.authService.currentUser()?.brand?.logo_dark?.trim() || 'assets/images/logo-wide-dark.svg');

  constructor() {
    effect(() => {
      document.title = this.name();
    });
  }
}
