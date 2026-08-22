import { Component, computed, input } from '@angular/core';

import { ICON_PATHS } from '../../constants/icon.constants';
import { IconName } from '../../model/icon.model';

@Component({
  selector: 'app-icon',
  host: { class: 'inline-flex shrink-0' },
  templateUrl: './icon.html',
})
export class Icon {
  name = input.required<IconName>();
  path = computed(() => ICON_PATHS[this.name()]);
}
