import { DOCUMENT } from '@angular/common';
import { Injectable, effect, inject, signal } from '@angular/core';

import { THEME_STORAGE_KEY } from '../shared/constants/theme.constants';
import { ColorTheme } from '../shared/model/theme.model';
import { AuthService } from './auth';

@Injectable({
  providedIn: 'root',
})
export class ThemeService {
  private readonly document = inject(DOCUMENT);
  private readonly authService = inject(AuthService);

  readonly theme = signal<ColorTheme>(this.readInitialTheme());

  constructor() {
    effect(() => {
      const savedTheme = this.authService.currentUser()?.preferences.theme;
      if (savedTheme && savedTheme !== this.theme()) {
        this.storeTheme(savedTheme);
        this.theme.set(savedTheme);
        this.applyTheme(savedTheme);
      }
    });
  }

  initialize(): void {
    this.applyTheme(this.theme());
  }

  setTheme(theme: ColorTheme): void {
    if (this.theme() === theme) {
      return;
    }

    this.theme.set(theme);
    this.applyTheme(theme);
    this.storeTheme(theme);

    if (this.authService.currentUser()) {
      this.authService.updatePreferences({ theme }).subscribe({ error: () => undefined });
    }
  }

  private storeTheme(theme: ColorTheme): void {
    try {
      this.document.defaultView?.localStorage.setItem(THEME_STORAGE_KEY, theme);
    }
    catch {
      return;
    }
  }

  private readInitialTheme(): ColorTheme {
    const browserWindow = this.document.defaultView;
    const systemTheme: ColorTheme = browserWindow?.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';

    try {
      const storedTheme = browserWindow?.localStorage.getItem(THEME_STORAGE_KEY);
      return storedTheme === 'light' || storedTheme === 'dark' ? storedTheme : systemTheme;
    }
    catch {
      return systemTheme;
    }
  }

  private applyTheme(theme: ColorTheme): void {
    const isDark = theme === 'dark';
    const themeColor = isDark ? '#090b0f' : '#edf4fb';
    const roots = [this.document.documentElement, this.document.body];

    for (const root of roots) {
      root.classList.toggle('dark-theme', isDark);
      root.classList.toggle('light-theme', !isDark);
    }

    this.document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')?.setAttribute('content', themeColor);
  }
}
