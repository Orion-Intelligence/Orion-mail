# Orion Mail — Notes

## Per-tenant white-label (brand from `orion_origin`)

Orion Mail is a single deployment. Each tenant SSOs in from its own Orion Intelligence origin, which the backend already captures and remembers as `orion_origin` (validated by `allowed_orion_origin`, stored in the httponly `orion_mail_orion_origin` cookie, 30 days). The mail UI is "white-labeled" per tenant by pulling that tenant's brand from its Intelligence origin.

- **`GET /api/auth/me` now returns `brand: {name, logo_light, logo_dark}`.** Fetched server-side by `orion_brand_client.get_tenant_brand(orion_origin)`: a GET to `{S_ORION_INTELLIGENCE_INTERNAL_URL}/api/public` with `Host: <tenant host>` (so Intelligence resolves the right tenant by Host, same trick as `orion_identity_client`), reading `app_name`, `logo_wide_light`, `logo_wide_dark`. Results are cached in-memory per origin for 300s; any failure returns an empty brand (never blocks login) and is not cached, so it self-recovers.
- **Logos are inlined as `data:` URIs**, not URLs. The mail CSP is `img-src 'self' data:` (`content_security_policy_middleware.py`), so a cross-origin `<img>` pointing at the Intelligence host would be blocked. `get_tenant_brand` fetches each wide-logo's bytes (via the same internal URL + Host header) and base64-encodes them (capped at 256 KB each).
- **Client** (`navbar`): `brandName` / `logoLight` / `logoDark` computeds off `authService.currentUser().brand`, falling back to the bundled `logo-wide.svg` / `logo-wide-dark.svg` and "Orion Mail" when the brand is empty. An `effect` sets `document.title` to the brand name.
- **Known bare-min limitation:** `index.html` still ships `<title>Orion Mail</title>` and the baked-in Orion splash wordmark; those show briefly before Angular loads (pre-auth, no `orion_origin` yet). Making them per-tenant needs server-side HTML templating and is out of scope for this pass.

The Intelligence side (the `/api/public` brand keys) is documented in the Orion-Intelligence repo NOTES.

## Mail address domain — always the shared base `MAIL_DOMAIN` (2026-09-24)

**Reverted to one shared domain.** Every mailbox is `<username>@mail.orionintelligence.org` regardless of tenant — `mailbox_manager._resolve_mail_domain` now just `return CONSTANTS.S_MAIL_DOMAIN` (was `<slug>.<S_MAIL_BASE_DOMAIN>`). Rationale: a per-tenant *email* domain (`<slug>.mail.…` or single-label `<slug>mail.…`) needs per-tenant MX/SPF DNS to be deliverable, and single-label can't even be a wildcard. Collapsing to the base means **zero per-tenant mail DNS**: the base already has MX (`mail → mx.orionintelligence.org` → 144.76.157.34), SPF, DKIM (org key via `use_esld`), DMARC, and Postfix `virtual_mailbox_domains` (`/^(.*\.)?mail\.orionintelligence\.org$/`) accepts it. The **webmail URL stays per-tenant** (`<slug>mail.orionintelligence.org`, single-label, CF-proxied) — browser host and email address deliberately differ.

`tenant_slug` still travels in the SSO identity and is stored as `db_user_model.orion_tenant_slug` (used for the webmail host / brand), but it no longer decides the email domain. `db_mailbox_model.mail_domain` persists the resolved domain (now always base). **Caveat:** one shared domain means usernames are globally unique — a second tenant's user with a colliding username hits the `mailbox_address` unique index (409 on mailbox create). **Existing** per-tenant mailboxes keep their stored `<slug>.mail.…` address; delete+recreate the mailbox to move it to the base domain.

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

## Per-tenant webmail host (`<slug>mail.orionintelligence.org`) (2026-09-23)

The webmail is served to each tenant from its own **single-label** subdomain (`intelysyncmail.orionintelligence.org/inbox`) — slug + literal `mail`, NOT the earlier three-level `<slug>.mail.…`. This was the whole point of the switch: a two-level host under `orionintelligence.org` is already covered by the existing Cloudflare **proxied** `*.orionintelligence.org` wildcard DNS + CF Universal SSL (`*.orionintelligence.org`), so it needs **no new DNS record, no new TLS cert, and no per-tenant anything**. The three-level `<slug>.mail.…` needed a dedicated `*.mail.…` wildcard cert (Let's Encrypt DNS-01) + DNS + edge block — all of that is now deleted (see cleanup below). Still ONE deployment: the Angular build uses relative `apiBaseUrl: '/api'`, so the same SPA works from any host. Session/SSO cookies are host-only (no `Domain=`), so each tenant host has its own isolated session.

Derivation is "insert `mail` with no dot": Intelligence host `intelysync.orionintelligence.org` → webmail host `intelysyncmail.orionintelligence.org`; reverse (mail → parent Intelligence origin) strips the trailing `mail` off the first label. **Caveat of the concatenated form:** a tenant whose slug itself ends in `mail` (e.g. `gmail`, `webmail`) collides with the mail-host regex — a `-mail` separator (`<slug>-mail.…`) would remove the ambiguity if that ever matters.

Code (accepts the tenant host through the SSO round-trip):
- `constant.py` — `S_MAIL_TENANT_HOST_PATTERN` = `^[a-z0-9-]+<S_MAIL_BASE_DOMAIN>$` (note: no `\.` before the base — the slug is glued straight onto `mail.orionintelligence.org`). `S_ALLOWED_HOSTS` now carries `*.orionintelligence.org` (the parent, derived as `S_MAIL_BASE_DOMAIN.split('.',1)[1]`) so `TrustedHostMiddleware` accepts the single-label mail Host — `*.mail.…` no longer matches `<slug>mail.…`. The edge nginx still gates which hosts actually reach the mail backend, so the broader TrustedHost value is only defence-in-depth.
- `auth_routes.allowed_mail_origin`, `auth_cookie.allowed_sso_redirect_uri`, `app_dependency.is_origin_allowed` — all match on `S_MAIL_TENANT_HOST_PATTERN`, so they picked up the new format automatically (no edit). `is_origin_allowed` is the CSRF/origin guard on every state-changing request; without a tenant-host match, POSTs (e.g. `POST /api/mailboxes/me/e2e-key/unlock`) 403 with `{"detail":"Origin not allowed"}` even though same-origin, and the e2e dialog mislabels it "That passphrase is not correct".
- `interface._tenant_orion_origin` — extracts the slug as `host.split('.',1)[0][:-len("mail")]` (strip the trailing `mail`) then rebuilds `https://<slug>.orionintelligence.org` for the brand/splash/favicon fetch.
- Intelligence side: `profile.openOrionMail` builds `${slug}${mailHost}` (glued, was `${slug}.${mailHost}`); `sso_constants.S_ALLOWED_REDIRECT_URI_PATTERN` = `^https://[a-z0-9-]+mail\.orionintelligence\.org/api/auth/callback$`.

Flow: `intelysync.orionintelligence.org` → opens `intelysyncmail.orionintelligence.org/api/auth/login` → mail builds redirect_uri on the tenant host → Intelligence `/api/sso/mail/authorize` validates it → code back to `intelysyncmail.orionintelligence.org/api/auth/callback` → host-only session cookie → `/inbox`.

### Edge routing (nginx — the one non-obvious piece)

`<slug>mail.orionintelligence.org` also matches the app's `*.orionintelligence.org` block, and nginx gives a **leading-wildcard higher priority than any regex**, so the app block would always win. The only fix is to make BOTH server_names regexes and rely on definition order (first matching regex wins): the mail block (`~*^[a-z0-9-]+mail\.orionintelligence\.org$`, on the existing `try.orionintelligence.org` cert) is defined **before** the app block (`~*^.+\.orionintelligence\.org$`), so `<slug>mail` peels off to `$mail_backend` and every other subdomain falls through to `$app_backend`. Both certs are the `try` origin cert — fine because CF terminates TLS for the browser with Universal SSL and connects to origin in Full (non-strict) mode (the same reason tenant Intelligence apps already work on the `try` origin cert). The port-80 block is left routing to the app; CF talks to the origin over 443, so it is not on the mail path.

### Cleanup done / operator teardown (the old three-level infra is now dead)

- Deleted in-repo: the edge `*.mail.orionintelligence.org` server block and its `mail-wildcard` cert reference; the mail app-nginx `*.mail.…` `server_name`.
- Cloudflare: the DNS-only `A *.mail.orionintelligence.org` (old 3-level webmail record) was **deleted 2026-09-23**; the `MX` + `TXT`(SPF) on `*.mail.…` were **kept** — those are the tenant email-sending infra for the `<slug>.mail.…` sending domain, NOT the webmail host. New tenant webmail hosts need **zero** DNS/cert work: the proxied `CNAME *.orionintelligence.org` wildcard + Universal SSL already cover `<slug>mail.…` (verified live). Remaining prod-box step: `certbot delete --cert-name mail-wildcard` (the DNS-01 wildcard cert is unused). `ORION_INTELLIGENCE_TENANT_BASE_DOMAIN=orionintelligence.org` must still be set (needed by `allowed_orion_origin`).

## Splash + passphrase-dialog white-label (2026-09-23)

Two remaining hardcoded-Orion spots in the connecting/unlock UI are now per-tenant.

**Splash logo (pre-Angular).** `client/src/index.html` no longer hardcodes the "Orion Mail" SVG wordmark — the splash logo slot is `<!--__SPLASH_LOGO__-->`, filled at serve time. `interface._frontend_index_response` (now async — same hook that already swaps `__CSP_NONCE__`) resolves the tenant from the request Host (`<slug>.mail.<parent>` → Intelligence origin `https://<slug>.<parent>`, else the base public URL), calls the existing `get_tenant_brand(...)` (cached 300s, returns light/dark logos as `data:` URIs), and injects two `<img>` (light/dark, toggled by `.dark-theme` CSS, mirroring the navbar). Empty brand (Intelligence unreachable) → no logo, never the raw placeholder. The tab `<title>` stays "Orion Mail" for the pre-boot instant; `BrandService`'s effect sets the real title once Angular boots. Note: this adds the brand fetch to index.html serves (same call already on `/api/auth/me`); the 300s cache keeps it cheap. In `ng serve` dev the placeholder isn't templated, so the dev splash shows no logo (cosmetic, dev-only).

**Passphrase dialog + e2e settings.** `e2e-unlock-dialog` (setup / recovery / forgot / reset / unlock) and `e2e-settings` hardcoded "Orion Mail" / "Orion account" / "Orion" throughout. Both now inject `BrandService` and use `{{ brand.name() }}` in the templates; the downloaded recovery-code text uses `this.brand.name()` and the file is `mail-recovery-code.txt` (was `orion-mail-recovery-code.txt`). `brand.name()` falls back to "Orion Mail" for the non-white-labeled base host.

**Favicon (browser tab icon).** The built `index.html` ships `<link rel="icon" href="favicon.ico">`; the same serve-time hook (`_frontend_index_response`) now swaps that href for the tenant's favicon. `get_tenant_brand` gained a `favicon` field: the bytes of Intelligence's public, Host-resolved `GET /api/s/static/favicon` (the tenant's square `logo_url_custom.png`, or the stock default), fetched via the existing `_fetch_logo` helper and inlined as a `data:` URI (same 256 KB cap + 300s cache as the wide logos). Backend-only — no mail-client rebuild: the swap targets the `favicon.ico` href already present in the deployed build. Empty/unreachable brand → the href is left as `favicon.ico` (stock icon), never broken.
