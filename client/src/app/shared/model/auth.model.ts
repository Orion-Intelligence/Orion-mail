import { ColorTheme } from './theme.model';

export interface UserPreferences {
  theme: ColorTheme | null;
}

export interface CurrentUser {
  id: string;
  full_name: string;
  email: string;
  username: string;
  mailbox_configured: boolean;
  mailbox_address: string | null;
  mail_domain: string;
  orion_account_url: string;
  preferences: UserPreferences;
}

export interface LogoutResponse {
  message: string;
  redirect_url: string;
}
