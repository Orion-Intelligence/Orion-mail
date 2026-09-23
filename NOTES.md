# Orion Mail — Notes

## Per-tenant white-label (brand from `orion_origin`)

Orion Mail is a single deployment. Each tenant SSOs in from its own Orion Intelligence origin, which the backend already captures and remembers as `orion_origin` (validated by `allowed_orion_origin`, stored in the httponly `orion_mail_orion_origin` cookie, 30 days). The mail UI is "white-labeled" per tenant by pulling that tenant's brand from its Intelligence origin.

- **`GET /api/auth/me` now returns `brand: {name, logo_light, logo_dark}`.** Fetched server-side by `orion_brand_client.get_tenant_brand(orion_origin)`: a GET to `{S_ORION_INTELLIGENCE_INTERNAL_URL}/api/public` with `Host: <tenant host>` (so Intelligence resolves the right tenant by Host, same trick as `orion_identity_client`), reading `app_name`, `logo_wide_light`, `logo_wide_dark`. Results are cached in-memory per origin for 300s; any failure returns an empty brand (never blocks login) and is not cached, so it self-recovers.
- **Logos are inlined as `data:` URIs**, not URLs. The mail CSP is `img-src 'self' data:` (`content_security_policy_middleware.py`), so a cross-origin `<img>` pointing at the Intelligence host would be blocked. `get_tenant_brand` fetches each wide-logo's bytes (via the same internal URL + Host header) and base64-encodes them (capped at 256 KB each).
- **Client** (`navbar`): `brandName` / `logoLight` / `logoDark` computeds off `authService.currentUser().brand`, falling back to the bundled `logo-wide.svg` / `logo-wide-dark.svg` and "Orion Mail" when the brand is empty. An `effect` sets `document.title` to the brand name.
- **Known bare-min limitation:** `index.html` still ships `<title>Orion Mail</title>` and the baked-in Orion splash wordmark; those show briefly before Angular loads (pre-auth, no `orion_origin` yet). Making them per-tenant needs server-side HTML templating and is out of scope for this pass.

The Intelligence side (the `/api/public` brand keys) is documented in the Orion-Intelligence repo NOTES.

## Per-tenant sending domain

Each tenant's users send from `<username>@<tenant-slug>.mail.orionintelligence.org` instead of the single global `MAIL_DOMAIN`. The send path is already address-driven — `From:` and envelope MAIL FROM both come from `mailbox.mailbox_address` (`mail_manager.py:32,70`) — so making the mailbox address per-tenant makes sending per-tenant with no change to the send code.

**Tenant identity (authoritative, not spoofable).** The domain is derived from the tenant **slug**, which now travels in the SSO identity: Intelligence `sso_manager._identity_for_user` looks it up from the tenant record and adds `tenant_slug`; the mail side reads it in `orion_identity_manager._normalized_identity` (sanitized to `[a-z0-9-]+`), stores it as `db_user_model.orion_tenant_slug`, and `mailbox_manager._resolve_mail_domain` builds `<slug>.<S_MAIL_BASE_DOMAIN>` (fallback to `S_MAIL_DOMAIN` when no slug — default tenant). The `orion_origin` cookie is NOT used for this: it is user-supplied at login and only format-validated, so it must not decide the sending domain. `db_mailbox_model.mail_domain` persists the resolved domain. Disposables stay on the base `MAIL_DOMAIN` for now.

**Env:** `MAIL_BASE_DOMAIN` (default `mail.orionintelligence.org`) on both the `web` and `postfix` services; `S_MAIL_BASE_DOMAIN` in `constant.py`.

**Postfix — multi-domain inbound.** `virtual_mailbox_domains` was single-valued; it is now a pcre map written at boot by `postfix-entrypoint.sh` matching `/^(.*\.)?mail\.orionintelligence\.org$/` (base + every tenant subdomain). Requires the `postfix-pcre` package (added in `postfix_docker`). Real recipients are still gated by the app's exact-address lookup (`incoming_mail_manager.py:107`), so a permissive accept is safe.

**DKIM/SPF/DMARC — one org key, no per-tenant provisioning.** `rspamd/local.d/dkim_signing.conf` now sets `use_esld = true`, so every subdomain signs with the effective-SLD key `d=orionintelligence.org` (one key file `/var/lib/rspamd/dkim/orionintelligence.org.mail.key`, selector `mail`). DMARC passes for all `*.mail.orionintelligence.org` by **relaxed alignment** (shared org domain `orionintelligence.org`), and SPF passes/aligns via a wildcard TXT. This means zero per-tenant DKIM keys and zero per-tenant DNS. Trade-off: the DKIM `d=` is the shared org domain (invisible to recipients — the `From:` is the per-tenant subdomain); true per-tenant `d=` would need per-tenant keys + per-tenant DNS (a later upgrade).

### One-time operator steps (not automated)

DKIM key (run in the rspamd container so it lands in the `rspamd` volume — the web container has no access to it):

```
docker compose exec rspamd rspamadm dkim_keygen -s mail -d orionintelligence.org \
  -k /var/lib/rspamd/dkim/orionintelligence.org.mail.key
```

The command prints the public-key TXT to publish.

DNS (Cloudflare, one-time — no API automation):
- `*.mail.orionintelligence.org` MX → the MX host (inbound to tenant subdomains)
- `*.mail.orionintelligence.org` TXT SPF `v=spf1 ip4:<mx-ip> -all`
- `mail._domainkey.orionintelligence.org` TXT = the DKIM public key from keygen (covers all subdomains via eSLD)
- `_dmarc.orionintelligence.org` DMARC policy (relaxed alignment covers subdomains)
- The existing base `mail.orionintelligence.org` MX/SPF stay as-is.

MTA keeps opportunistic TLS (snakeoil) — mail still flows; a valid MX cert is hardening, not required.

### Clean slate (new feature, no migration)

Existing mailboxes are keyed on the old global domain; there is no migration. Drop the mail DB collections so everyone re-provisions under the new per-tenant domain on next mailbox setup:

```
docker compose exec mongo mongosh "$MONGODB_URL" --eval \
  'db.getSiblingDB("orion_mail").users.drop(); db.getSiblingDB("orion_mail").mailboxes.drop(); db.getSiblingDB("orion_mail").disposable_mailboxes.drop();'
```

## Per-tenant webmail host (`<slug>.mail.orionintelligence.org`) (2026-09-23)

The webmail is served to each tenant from its own subdomain (`intelysync.mail.orionintelligence.org/inbox`), not the shared `mail.orionintelligence.org`. It is still ONE deployment behind ONE wildcard — the Angular build uses a relative `apiBaseUrl: '/api'`, so the same SPA works from any host; nothing is per-tenant-built. Session/SSO cookies are all host-only (no `Domain=`), so each tenant subdomain has its own isolated session — no cross-tenant cookie collision.

Code (accepts the tenant host through the SSO round-trip):
- `constant.py` — `S_MAIL_TENANT_HOST_PATTERN` = `^[a-z0-9-]+\.<S_MAIL_BASE_DOMAIN>$`; `S_ALLOWED_HOSTS` now also carries `*.<S_MAIL_BASE_DOMAIN>` so `TrustedHostMiddleware` accepts the tenant Host header (the bare `mail.orionintelligence.org` stays listed — the `*.` wildcard does not match the apex).
- `auth_routes.allowed_mail_origin` — accepts the `origin` query param when it is `https://<slug>.<base>` (in addition to the `S_ORION_MAIL_PUBLIC_URLS` list). This is the origin used to build the redirect_uri.
- `auth_cookie.allowed_sso_redirect_uri` — accepts `https://<slug>.<base>/api/auth/callback` and returns it as-is instead of falling back to the shared host (the fallback would have sent the code to the wrong host).

Flow: Intelligence `intelysync.orionintelligence.org` → opens `intelysync.mail.orionintelligence.org/api/auth/login` → mail builds redirect_uri on the tenant host → Intelligence `/api/sso/mail/authorize` validates it (its `S_ALLOWED_REDIRECT_URI_PATTERN`) → code back to `intelysync.mail.orionintelligence.org/api/auth/callback` → session cookie set host-only on the tenant host → `/inbox`. End state: URL bar shows `intelysync.mail.orionintelligence.org/inbox`.

### One-time operator steps (infra — NOT in the repos, required for the tenant URL to load)

1. **DNS (Cloudflare, one wildcard):** `A *.mail.orionintelligence.org → 144.76.157.34` (proxied or DNS-only, matching how the base `mail` record is set). This is the only new DNS record for the webmail host, on top of the existing per-tenant sending records.
2. **Traefik wildcard TLS + router:** the reverse proxy in front of the mail `web` container must (a) present a cert valid for `*.mail.orionintelligence.org` (a wildcard cert — Let's Encrypt DNS-01, since HTTP-01 cannot issue wildcards), and (b) have a router rule matching `Host(`mail.orionintelligence.org`) || HostRegexp(`{sub:[a-z0-9-]+}.mail.orionintelligence.org`)` routed to the same mail web service. Without the cert+router the tenant URL will not resolve/serve — no code change substitutes for it.
3. No mail env change is required for hosts/origins (defaults derive the wildcard from `MAIL_BASE_DOMAIN`). `ORION_INTELLIGENCE_TENANT_BASE_DOMAIN=orionintelligence.org` must still be set (needed by `allowed_orion_origin` for the tenant `orion_origin`).

## Splash + passphrase-dialog white-label (2026-09-23)

Two remaining hardcoded-Orion spots in the connecting/unlock UI are now per-tenant.

**Splash logo (pre-Angular).** `client/src/index.html` no longer hardcodes the "Orion Mail" SVG wordmark — the splash logo slot is `<!--__SPLASH_LOGO__-->`, filled at serve time. `interface._frontend_index_response` (now async — same hook that already swaps `__CSP_NONCE__`) resolves the tenant from the request Host (`<slug>.mail.<parent>` → Intelligence origin `https://<slug>.<parent>`, else the base public URL), calls the existing `get_tenant_brand(...)` (cached 300s, returns light/dark logos as `data:` URIs), and injects two `<img>` (light/dark, toggled by `.dark-theme` CSS, mirroring the navbar). Empty brand (Intelligence unreachable) → no logo, never the raw placeholder. The tab `<title>` stays "Orion Mail" for the pre-boot instant; `BrandService`'s effect sets the real title once Angular boots. Note: this adds the brand fetch to index.html serves (same call already on `/api/auth/me`); the 300s cache keeps it cheap. In `ng serve` dev the placeholder isn't templated, so the dev splash shows no logo (cosmetic, dev-only).

**Passphrase dialog + e2e settings.** `e2e-unlock-dialog` (setup / recovery / forgot / reset / unlock) and `e2e-settings` hardcoded "Orion Mail" / "Orion account" / "Orion" throughout. Both now inject `BrandService` and use `{{ brand.name() }}` in the templates; the downloaded recovery-code text uses `this.brand.name()` and the file is `mail-recovery-code.txt` (was `orion-mail-recovery-code.txt`). `brand.name()` falls back to "Orion Mail" for the non-white-labeled base host.
