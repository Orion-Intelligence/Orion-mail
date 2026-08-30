import { Component, DestroyRef, inject, signal } from '@angular/core';
import { NavigationEnd, Router, RouterOutlet } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { filter } from 'rxjs';

import { Navbar } from './shared/partials/navbar/navbar';
import { SplashService } from './services/splash';
import { ThemeService } from './services/theme';

const SPLASH_FALLBACK_MS = 6000;

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, Navbar],
  host: {
    class:
      'orion-mail-shell block h-dvh bg-page bg-cover bg-center bg-no-repeat',
  },
  templateUrl: './app.html',
})
export class App {
  private readonly destroyRef = inject(DestroyRef);

  readonly configureEmailRoute = signal(window.location.pathname.startsWith('/configure-email'));

  constructor(public readonly router: Router, themeService: ThemeService, splashService: SplashService) {
    themeService.initialize();
    setTimeout(() => splashService.hide(), SPLASH_FALLBACK_MS);
    this.router.events.pipe(filter((event): event is NavigationEnd => event instanceof NavigationEnd), takeUntilDestroyed(this.destroyRef))
      .subscribe((event) => {
        this.configureEmailRoute.set(event.urlAfterRedirects.startsWith('/configure-email'));
      });
  }
}
