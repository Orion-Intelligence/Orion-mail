import { Injectable } from '@angular/core';

const FADE_OUT_MS = 260;

@Injectable({
  providedIn: 'root',
})
export class SplashService {
  private dismissed = false;

  hide(): void {
    if (this.dismissed) {
      return;
    }

    this.dismissed = true;
    const splash = document.getElementById('app-splash');

    if (!splash) {
      return;
    }

    splash.classList.add('is-hidden');
    setTimeout(() => splash.remove(), FADE_OUT_MS);
  }
}
