from typing import Annotated

from pydantic import BaseModel, Field

from orion.api.interactive.e2e_key_manager.e2e_key_enums import E2E_KEY_LIMITS, E2E_KEY_PATTERNS, E2E_UNLOCK_KIND

Verifier = Annotated[str, Field(pattern=E2E_KEY_PATTERNS.VERIFIER)]


class E2eKeyBundleRequest(BaseModel):
    fingerprint: str = Field(pattern=E2E_KEY_PATTERNS.FINGERPRINT)
    public_key: str = Field(min_length=1, max_length=E2E_KEY_LIMITS.PUBLIC_KEY_MAX_LENGTH)
    locked_private_key: str = Field(min_length=1, max_length=E2E_KEY_LIMITS.PRIVATE_KEY_MAX_LENGTH)
    recovery_private_key: str | None = Field(default=None, min_length=1, max_length=E2E_KEY_LIMITS.PRIVATE_KEY_MAX_LENGTH)
    kdf_salt: str = Field(pattern=E2E_KEY_PATTERNS.SALT)
    verifier: Verifier
    recovery_verifier: Verifier | None = None
    proof: Verifier | None = None


class E2eKeyUnlockRequest(BaseModel):
    verifier: Verifier
    kind: E2E_UNLOCK_KIND = E2E_UNLOCK_KIND.PASSPHRASE


class E2eKeyLookupRequest(BaseModel):
    addresses: list[Annotated[str, Field(max_length=320)]] = Field(min_length=1, max_length=E2E_KEY_LIMITS.LOOKUP_MAX_ADDRESSES)
