from enum import Enum


class E2E_UNLOCK_KIND(str, Enum):
    PASSPHRASE = "passphrase"
    RECOVERY = "recovery"


class E2E_KEY_LIMITS:
    PUBLIC_KEY_MAX_LENGTH = 16 * 1024
    PRIVATE_KEY_MAX_LENGTH = 32 * 1024
    LOOKUP_MAX_ADDRESSES = 100
    MAX_FAILED_UNLOCKS = 10
    UNLOCK_BLOCK_MINUTES = 15
    TAB_SECRET_HOURS = 12


class E2E_KEY_PATTERNS:
    FINGERPRINT = r"^[0-9A-Fa-f]{40}$"
    SALT = r"^[A-Za-z0-9+/=]{16,64}$"
    VERIFIER = r"^[A-Za-z0-9+/]{43}=$"


class E2E_ARMOR:
    PUBLIC_KEY_HEADER = "-----BEGIN PGP PUBLIC KEY BLOCK-----"
    PRIVATE_KEY_HEADER = "-----BEGIN PGP PRIVATE KEY BLOCK-----"
    MESSAGE_HEADER = "-----BEGIN PGP MESSAGE-----"
    MESSAGE_FOOTER = "-----END PGP MESSAGE-----"
    MESSAGE_MARKER = "Comment: Orion Mail E2E v1"
