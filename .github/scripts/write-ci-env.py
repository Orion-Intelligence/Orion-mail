#!/usr/bin/env python3
"""Write the root .env file used by the CI workflows.

When the ENV_FILE secret is provided it is written verbatim. Otherwise a throwaway
configuration is derived from .env.example with freshly generated secrets, so the
pipeline also runs on forks and pull requests that cannot read repository secrets.

Set CI_ENV_OUTPUT to write the file somewhere other than <repo>/.env.
"""

from __future__ import annotations

import base64
import os
import pathlib
import secrets

ROOT = pathlib.Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / ".env.example"
TARGET = pathlib.Path(os.environ.get("CI_ENV_OUTPUT") or ROOT / ".env")


def mask(value: str) -> None:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::add-mask::{value}")


def generated_values() -> dict[str, str]:
    return {
        "MONGO_ROOT_USERNAME": "root",
        "MONGO_ROOT_PASSWORD": secrets.token_urlsafe(24),
        "ORION_MAIL_SSO_CLIENT_SECRET": secrets.token_urlsafe(48),
        "ENCRYPTION_KEY": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        "INCOMING_MAIL_TOKEN": secrets.token_urlsafe(32),
    }


def static_overrides() -> dict[str, str]:
    return {
        "COOKIE_SECURE": "false",
        "SEED_LOCAL_TEST_MAILBOXES": "true",
        "ALLOWED_HOSTS": "localhost,127.0.0.1",
        "CORS_ALLOWED_ORIGINS": "http://localhost:4300,http://127.0.0.1:4300",
    }


def main() -> int:
    provided = os.environ.get("ENV_FILE", "")
    if provided.strip():
        TARGET.write_text(provided.rstrip("\n") + "\n", encoding="utf-8")
        print(f"Wrote {TARGET} from the ENV_FILE secret")
        return 0

    generated = generated_values()
    values = {**generated, **static_overrides()}
    lines: list[str] = []
    seen: set[str] = set()
    for raw in TEMPLATE.read_text(encoding="utf-8").splitlines():
        key, separator, _ = raw.partition("=")
        key = key.strip()
        if separator and key in values:
            lines.append(f'{key}="{values[key]}"')
            seen.add(key)
        else:
            lines.append(raw)
    for key, value in values.items():
        if key not in seen:
            lines.append(f'{key}="{value}"')

    TARGET.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for key, value in generated.items():
        if key != "MONGO_ROOT_USERNAME":
            mask(value)
    print(f"Wrote {TARGET} from .env.example with generated secrets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
