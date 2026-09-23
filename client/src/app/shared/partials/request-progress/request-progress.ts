import { Component, inject } from '@angular/core';

import { RequestProgressService } from '../../../services/request-progress';

@Component({
  selector: 'app-request-progress',
  host: { class: 'contents' },
  templateUrl: './request-progress.html',
})
export class RequestProgress {
  readonly progress = inject(RequestProgressService);
}
